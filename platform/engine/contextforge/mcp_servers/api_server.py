"""MCP tool server — External API gateway operations."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Default allowlist of external endpoint prefixes.  Deployments should
# override via constructor parameter.
_DEFAULT_ALLOWLIST: list[str] = [
    "https://api.example.com/",
]


class ApiTools:
    """Tool definitions for external API calls, exposed to agents."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        allowed_prefixes: list[str] | None = None,
        fhir_base_url: str | None = None,
    ) -> None:
        self._http = http_client
        self._allowed_prefixes = allowed_prefixes or _DEFAULT_ALLOWLIST
        self._fhir_base_url = fhir_base_url

    def tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "call_external_api",
                    "description": (
                        "Make an HTTP request to a whitelisted external API endpoint. "
                        "Supports GET and POST methods."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "Full URL of the external endpoint",
                            },
                            "method": {
                                "type": "string",
                                "enum": ["GET", "POST"],
                                "default": "GET",
                                "description": "HTTP method",
                            },
                            "headers": {
                                "type": "object",
                                "description": "Optional HTTP headers",
                                "additionalProperties": {"type": "string"},
                            },
                            "body": {
                                "type": "object",
                                "description": "Optional JSON body for POST requests",
                            },
                            "timeout": {
                                "type": "number",
                                "default": 30,
                                "description": "Request timeout in seconds",
                            },
                        },
                        "required": ["url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fhir_query",
                    "description": (
                        "Query a FHIR R4 REST API. Builds the request URL from "
                        "resource type and search parameters."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "resource_type": {
                                "type": "string",
                                "description": (
                                "FHIR resource type, e.g. Patient, "
                                "Observation, Encounter"
                            ),
                            },
                            "resource_id": {
                                "type": "string",
                                "description": "Optional specific resource ID for a read operation",
                            },
                            "search_params": {
                                "type": "object",
                                "description": "FHIR search parameters as key-value pairs",
                                "additionalProperties": {"type": "string"},
                            },
                            "headers": {
                                "type": "object",
                                "description": "Optional extra HTTP headers (e.g. Authorization)",
                                "additionalProperties": {"type": "string"},
                            },
                        },
                        "required": ["resource_type"],
                    },
                },
            },
        ]

    async def execute(self, tool_name: str, args: dict[str, Any]) -> Any:
        if tool_name == "call_external_api":
            return await self._call_external_api(args)
        elif tool_name == "fhir_query":
            return await self._fhir_query(args)
        raise ValueError(f"Unknown tool: {tool_name}")

    # ------------------------------------------------------------------
    # call_external_api
    # ------------------------------------------------------------------

    def _is_url_allowed(self, url: str) -> bool:
        """Check whether *url* starts with any allowed prefix."""
        return any(url.startswith(prefix) for prefix in self._allowed_prefixes)

    async def _call_external_api(self, args: dict[str, Any]) -> dict[str, Any]:
        url: str = args["url"]
        method: str = args.get("method", "GET").upper()
        headers: dict[str, str] = args.get("headers", {})
        body: dict[str, Any] | None = args.get("body")
        timeout: float = args.get("timeout", 30)

        if not self._is_url_allowed(url):
            logger.warning("Blocked request to non-whitelisted URL: %s", url)
            return {
                "error": "URL not in allowlist",
                "url": url,
                "allowed_prefixes": self._allowed_prefixes,
            }

        try:
            if method == "POST":
                response = await self._http.post(
                    url, headers=headers, json=body, timeout=timeout
                )
            else:
                response = await self._http.get(
                    url, headers=headers, timeout=timeout
                )

            logger.info(
                "call_external_api %s %s -> %d", method, url, response.status_code
            )

            # Attempt JSON, fall back to text
            try:
                response_body = response.json()
            except Exception:
                response_body = response.text

            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response_body,
            }
        except httpx.TimeoutException:
            logger.warning("Timeout calling %s", url)
            return {"error": "Request timed out", "url": url}
        except httpx.HTTPError as exc:
            logger.warning("HTTP error calling %s: %s", url, exc)
            return {"error": str(exc), "url": url}

    # ------------------------------------------------------------------
    # fhir_query
    # ------------------------------------------------------------------

    async def _fhir_query(self, args: dict[str, Any]) -> dict[str, Any]:
        if not self._fhir_base_url:
            return {"error": "FHIR base URL not configured"}

        resource_type: str = args["resource_type"]
        resource_id: str | None = args.get("resource_id")
        search_params: dict[str, str] = args.get("search_params", {})
        headers: dict[str, str] = args.get("headers", {})

        # Build URL
        if resource_id:
            url = f"{self._fhir_base_url.rstrip('/')}/{resource_type}/{resource_id}"
        else:
            url = f"{self._fhir_base_url.rstrip('/')}/{resource_type}"

        # Default FHIR headers
        request_headers = {"Accept": "application/fhir+json"}
        request_headers.update(headers)

        try:
            response = await self._http.get(
                url, headers=request_headers, params=search_params, timeout=30
            )

            logger.info("fhir_query %s -> %d", url, response.status_code)

            try:
                body = response.json()
            except Exception:
                body = response.text

            return {
                "status_code": response.status_code,
                "resource_type": resource_type,
                "body": body,
            }
        except httpx.TimeoutException:
            logger.warning("FHIR query timeout: %s", url)
            return {"error": "FHIR request timed out", "url": url}
        except httpx.HTTPError as exc:
            logger.warning("FHIR query error: %s: %s", url, exc)
            return {"error": str(exc), "url": url}
