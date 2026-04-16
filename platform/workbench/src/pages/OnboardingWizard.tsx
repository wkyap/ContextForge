import { useState } from "react";

interface WizardState {
  domainName: string;
  domainDescription: string;
  files: File[];
  proposedSchema: any | null;
  schemaApproved: boolean;
}

const STEP_LABELS = [
  "Domain Description",
  "Document Upload",
  "Schema Review",
  "Launch",
];

export default function OnboardingWizard() {
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [launched, setLaunched] = useState(false);
  const [state, setState] = useState<WizardState>({
    domainName: "",
    domainDescription: "",
    files: [],
    proposedSchema: null,
    schemaApproved: false,
  });

  const next = () => setStep((s) => Math.min(s + 1, 3));
  const back = () => setStep((s) => Math.max(s - 1, 0));

  // ---------- Step 1: Domain Description ----------
  const StepDomainDescription = () => (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Domain Name
        </label>
        <input
          type="text"
          value={state.domainName}
          onChange={(e) => setState({ ...state, domainName: e.target.value })}
          placeholder="e.g. Customer Support, Legal Docs"
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Description
        </label>
        <textarea
          value={state.domainDescription}
          onChange={(e) =>
            setState({ ...state, domainDescription: e.target.value })
          }
          placeholder="Describe what this domain covers, the types of documents, and the questions users will ask..."
          rows={5}
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
      </div>
    </div>
  );

  // ---------- Step 2: Document Upload ----------
  const StepDocumentUpload = () => {
    const [dragOver, setDragOver] = useState(false);

    const addFiles = (files: FileList | File[]) => {
      setState((prev) => ({
        ...prev,
        files: [...prev.files, ...Array.from(files)],
      }));
    };

    return (
      <div className="space-y-4">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            addFiles(e.dataTransfer.files);
          }}
          className={`border-2 border-dashed rounded-lg p-10 text-center transition ${
            dragOver
              ? "border-brand-500 bg-brand-50"
              : "border-gray-300 bg-white"
          }`}
        >
          <p className="text-sm text-gray-500">
            Drag and drop files here, or{" "}
            <label className="text-brand-600 cursor-pointer hover:underline">
              browse
              <input
                type="file"
                multiple
                className="hidden"
                onChange={(e) => e.target.files && addFiles(e.target.files)}
              />
            </label>
          </p>
          <p className="text-xs text-gray-400 mt-1">
            PDF, DOCX, TXT, MD, JSON supported
          </p>
        </div>

        {state.files.length > 0 && (
          <ul className="space-y-1">
            {state.files.map((f, i) => (
              <li
                key={i}
                className="flex items-center justify-between rounded-md bg-gray-50 px-3 py-2 text-sm"
              >
                <span className="text-gray-700 truncate">{f.name}</span>
                <button
                  onClick={() =>
                    setState((prev) => ({
                      ...prev,
                      files: prev.files.filter((_, idx) => idx !== i),
                    }))
                  }
                  className="text-xs text-red-500 hover:underline ml-3"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  };

  // ---------- Step 3: Schema Review ----------
  const StepSchemaReview = () => {
    const generateSchema = async () => {
      setLoading(true);
      setError(null);
      try {
        const formData = new FormData();
        formData.append("domain_name", state.domainName);
        formData.append("domain_description", state.domainDescription);
        state.files.forEach((f) => formData.append("files", f));

        const res = await fetch("/api/v1/onboard/propose-schema", {
          method: "POST",
          body: formData,
        });
        if (!res.ok) throw new Error("Failed to generate schema");
        const data = await res.json();
        setState((prev) => ({ ...prev, proposedSchema: data.schema }));
      } catch (err: any) {
        setError(err.message || "Schema generation failed.");
      } finally {
        setLoading(false);
      }
    };

    return (
      <div className="space-y-4">
        {!state.proposedSchema && !loading && (
          <button
            onClick={generateSchema}
            className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
          >
            Generate Schema
          </button>
        )}

        {loading && (
          <p className="text-sm text-gray-500 animate-pulse">
            Analyzing documents and generating schema...
          </p>
        )}

        {error && <p className="text-sm text-red-500">{error}</p>}

        {state.proposedSchema && (
          <>
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 overflow-auto max-h-80">
              <pre className="text-xs text-gray-700 whitespace-pre-wrap">
                {JSON.stringify(state.proposedSchema, null, 2)}
              </pre>
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={state.schemaApproved}
                onChange={(e) =>
                  setState((prev) => ({
                    ...prev,
                    schemaApproved: e.target.checked,
                  }))
                }
                className="rounded border-gray-300 text-brand-600 focus:ring-brand-500"
              />
              I approve this schema
            </label>
          </>
        )}
      </div>
    );
  };

  // ---------- Step 4: Launch Confirmation ----------
  const StepLaunchConfirmation = () => {
    const launch = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch("/api/v1/onboard/launch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            domain_name: state.domainName,
            domain_description: state.domainDescription,
            schema: state.proposedSchema,
          }),
        });
        if (!res.ok) throw new Error("Launch failed");
        setLaunched(true);
      } catch (err: any) {
        setError(err.message || "Launch failed.");
      } finally {
        setLoading(false);
      }
    };

    if (launched) {
      return (
        <div className="text-center py-8">
          <div className="text-3xl mb-3">&#10003;</div>
          <h3 className="text-lg font-semibold text-gray-900">
            Domain Launched Successfully
          </h3>
          <p className="text-sm text-gray-500 mt-1">
            Your domain "{state.domainName}" is now being processed. You can
            monitor the pipeline in the Pipeline Manager.
          </p>
        </div>
      );
    }

    return (
      <div className="space-y-4">
        <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-2 text-sm">
          <div>
            <span className="font-medium text-gray-600">Domain:</span>{" "}
            <span className="text-gray-900">{state.domainName}</span>
          </div>
          <div>
            <span className="font-medium text-gray-600">Description:</span>{" "}
            <span className="text-gray-900">{state.domainDescription}</span>
          </div>
          <div>
            <span className="font-medium text-gray-600">Documents:</span>{" "}
            <span className="text-gray-900">{state.files.length} file(s)</span>
          </div>
          <div>
            <span className="font-medium text-gray-600">Schema:</span>{" "}
            <span className="text-green-600">Approved</span>
          </div>
        </div>

        {error && <p className="text-sm text-red-500">{error}</p>}

        <button
          onClick={launch}
          disabled={loading}
          className="rounded-md bg-green-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
        >
          {loading ? "Launching..." : "Launch Domain"}
        </button>
      </div>
    );
  };

  const canAdvance = (): boolean => {
    switch (step) {
      case 0:
        return !!state.domainName.trim() && !!state.domainDescription.trim();
      case 1:
        return state.files.length > 0;
      case 2:
        return state.schemaApproved;
      default:
        return false;
    }
  };

  const renderStep = () => {
    switch (step) {
      case 0:
        return <StepDomainDescription />;
      case 1:
        return <StepDocumentUpload />;
      case 2:
        return <StepSchemaReview />;
      case 3:
        return <StepLaunchConfirmation />;
      default:
        return null;
    }
  };

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Onboarding Wizard</h1>
        <p className="text-sm text-gray-500 mt-1">
          Set up a new domain in a few steps.
        </p>
      </div>

      {/* Step Indicator */}
      <nav className="flex items-center gap-2">
        {STEP_LABELS.map((label, i) => (
          <div key={i} className="flex items-center gap-2">
            <div
              className={`flex items-center justify-center w-7 h-7 rounded-full text-xs font-semibold ${
                i < step
                  ? "bg-brand-600 text-white"
                  : i === step
                    ? "bg-brand-100 text-brand-700 ring-2 ring-brand-500"
                    : "bg-gray-100 text-gray-400"
              }`}
            >
              {i + 1}
            </div>
            <span
              className={`text-xs font-medium ${
                i <= step ? "text-gray-700" : "text-gray-400"
              }`}
            >
              {label}
            </span>
            {i < STEP_LABELS.length - 1 && (
              <div
                className={`w-8 h-px ${
                  i < step ? "bg-brand-400" : "bg-gray-200"
                }`}
              />
            )}
          </div>
        ))}
      </nav>

      {/* Step Content */}
      <div className="min-h-[240px]">{renderStep()}</div>

      {/* Navigation */}
      {!launched && (
        <div className="flex justify-between pt-4 border-t border-gray-200">
          <button
            onClick={back}
            disabled={step === 0}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-30"
          >
            Back
          </button>
          {step < 3 && (
            <button
              onClick={next}
              disabled={!canAdvance()}
              className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
            >
              Next
            </button>
          )}
        </div>
      )}
    </div>
  );
}
