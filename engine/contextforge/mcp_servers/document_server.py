"""MCP tool server — Document processing operations."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class DocumentTools:
    """Tool definitions for document processing, exposed to agents."""

    def __init__(
        self,
        litellm_model: str = "gpt-4o-mini",
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ) -> None:
        self._litellm_model = litellm_model
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    def tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "extract_text",
                    "description": (
                        "Extract plain text from a document (PDF, DOCX, or HTML). "
                        "Accepts either a file path or raw bytes reference."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to the document file",
                            },
                            "file_type": {
                                "type": "string",
                                "enum": ["pdf", "docx", "html"],
                                "description": "Document format (inferred from extension if omitted)",
                            },
                        },
                        "required": ["file_path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "chunk_document",
                    "description": (
                        "Split text into semantic chunks with configurable size and overlap, "
                        "suitable for embedding or retrieval"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "The text to chunk",
                            },
                            "chunk_size": {
                                "type": "integer",
                                "default": 512,
                                "description": "Target number of tokens per chunk",
                            },
                            "chunk_overlap": {
                                "type": "integer",
                                "default": 64,
                                "description": "Number of overlapping tokens between consecutive chunks",
                            },
                        },
                        "required": ["text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "summarize_document",
                    "description": (
                        "Generate a concise summary of a document using an LLM via LiteLLM"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "The document text to summarize",
                            },
                            "max_length": {
                                "type": "integer",
                                "default": 300,
                                "description": "Approximate maximum summary length in words",
                            },
                            "style": {
                                "type": "string",
                                "enum": ["brief", "detailed", "bullet_points"],
                                "default": "brief",
                                "description": "Summary style",
                            },
                        },
                        "required": ["text"],
                    },
                },
            },
        ]

    async def execute(self, tool_name: str, args: dict[str, Any]) -> Any:
        if tool_name == "extract_text":
            return await self._extract_text(args)
        elif tool_name == "chunk_document":
            return self._chunk_document(args)
        elif tool_name == "summarize_document":
            return await self._summarize_document(args)
        raise ValueError(f"Unknown tool: {tool_name}")

    # ------------------------------------------------------------------
    # extract_text
    # ------------------------------------------------------------------

    async def _extract_text(self, args: dict[str, Any]) -> dict[str, Any]:
        file_path: str = args["file_path"]
        file_type: str | None = args.get("file_type")

        if file_type is None:
            ext = file_path.rsplit(".", 1)[-1].lower()
            file_type = ext if ext in ("pdf", "docx", "html") else "pdf"

        try:
            if file_type == "pdf":
                text = await self._extract_pdf(file_path)
            elif file_type == "docx":
                text = await self._extract_docx(file_path)
            elif file_type == "html":
                text = await self._extract_html(file_path)
            else:
                return {"error": f"Unsupported file type: {file_type}"}

            logger.info("extract_text: %s (%s) -> %d chars", file_path, file_type, len(text))
            return {"text": text, "file_path": file_path, "file_type": file_type, "char_count": len(text)}
        except FileNotFoundError:
            return {"error": f"File not found: {file_path}"}
        except Exception as exc:
            logger.warning("extract_text failed for %s: %s", file_path, exc)
            return {"error": str(exc), "file_path": file_path}

    async def _extract_pdf(self, file_path: str) -> str:
        import pypdf  # lazy import

        reader = pypdf.PdfReader(file_path)
        pages: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                pages.append(page_text)
        return "\n\n".join(pages)

    async def _extract_docx(self, file_path: str) -> str:
        import docx  # lazy import (python-docx)

        doc = docx.Document(file_path)
        return "\n\n".join(para.text for para in doc.paragraphs if para.text.strip())

    async def _extract_html(self, file_path: str) -> str:
        from bs4 import BeautifulSoup  # lazy import

        with open(file_path, encoding="utf-8") as fh:
            soup = BeautifulSoup(fh.read(), "html.parser")
        # Remove script and style elements
        for tag in soup(["script", "style"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)

    # ------------------------------------------------------------------
    # chunk_document
    # ------------------------------------------------------------------

    def _chunk_document(self, args: dict[str, Any]) -> dict[str, Any]:
        text: str = args["text"]
        chunk_size: int = args.get("chunk_size", self._chunk_size)
        chunk_overlap: int = args.get("chunk_overlap", self._chunk_overlap)

        # Simple word-level chunking with overlap
        words = text.split()
        chunks: list[dict[str, Any]] = []
        start = 0

        while start < len(words):
            end = start + chunk_size
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words)
            chunks.append({
                "index": len(chunks),
                "text": chunk_text,
                "word_count": len(chunk_words),
                "start_word": start,
                "end_word": min(end, len(words)),
            })

            if end >= len(words):
                break
            start = end - chunk_overlap

        logger.info(
            "chunk_document: %d words -> %d chunks (size=%d, overlap=%d)",
            len(words), len(chunks), chunk_size, chunk_overlap,
        )
        return {
            "chunks": chunks,
            "total_chunks": len(chunks),
            "total_words": len(words),
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
        }

    # ------------------------------------------------------------------
    # summarize_document
    # ------------------------------------------------------------------

    async def _summarize_document(self, args: dict[str, Any]) -> dict[str, Any]:
        import litellm  # lazy import

        text: str = args["text"]
        max_length: int = args.get("max_length", 300)
        style: str = args.get("style", "brief")

        style_instructions = {
            "brief": f"Provide a brief summary in approximately {max_length} words.",
            "detailed": (
                f"Provide a detailed summary covering all key points, "
                f"in approximately {max_length} words."
            ),
            "bullet_points": (
                f"Provide a summary as bullet points, "
                f"with approximately {max_length} words total."
            ),
        }

        prompt = (
            f"{style_instructions.get(style, style_instructions['brief'])}\n\n"
            f"Document text:\n{text}"
        )

        try:
            response = await litellm.acompletion(
                model=self._litellm_model,
                messages=[
                    {"role": "system", "content": "You are a document summarization assistant."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_length * 2,  # rough token budget
            )

            summary = response.choices[0].message.content
            logger.info(
                "summarize_document: %d chars -> %d char summary (%s)",
                len(text), len(summary), style,
            )
            return {
                "summary": summary,
                "style": style,
                "input_char_count": len(text),
                "model": self._litellm_model,
            }
        except Exception as exc:
            logger.warning("summarize_document failed: %s", exc)
            return {"error": str(exc)}
