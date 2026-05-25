"use client";

import MathText from "@/components/MathText";

/** Possible states for the explanation fetch. */
type ExplainState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "loaded"; explanation: string }
  | { status: "error" };

interface ExplanationPanelProps {
  state: ExplainState;
  onDismiss: () => void;
  onRetry: () => void;
}

/** Skeleton loader shown while the explanation is being fetched. */
function ExplanationSkeleton() {
  return (
    <div className="flex flex-col gap-2 animate-pulse" aria-label="Loading explanation">
      <div className="h-3 w-full rounded bg-primary/10" />
      <div className="h-3 w-5/6 rounded bg-primary/10" />
      <div className="h-3 w-4/6 rounded bg-primary/10" />
    </div>
  );
}

/**
 * Displays a Bedrock-generated explanation for the current question.
 *
 * Renders a loading skeleton while fetching, the explanation text (via MathText)
 * on success, or an error message with a "Try Again" button on failure.
 * Always shows a dismiss button to hide the panel.
 */
export default function ExplanationPanel({
  state,
  onDismiss,
  onRetry,
}: ExplanationPanelProps) {
  return (
    <div className="rounded-xl border border-primary/20 bg-primary/5 dark:bg-primary/10 dark:border-primary/30 p-5 shadow-sm">
      {/* Header row */}
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-primary dark:text-blue-300">
          Topic Explanation
        </span>
        <button
          onClick={onDismiss}
          aria-label="Dismiss explanation"
          className="rounded-md p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors focus:outline-none focus:ring-2 focus:ring-primary/30"
        >
          ✕
        </button>
      </div>

      {/* Content */}
      {state.status === "loading" && <ExplanationSkeleton />}

      {state.status === "loaded" && (
        <MathText
          text={state.explanation}
          className="text-sm leading-relaxed text-gray-700 dark:text-gray-200"
        />
      )}

      {state.status === "error" && (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-error">
            Could not load the explanation. Please try again.
          </p>
          <button
            onClick={onRetry}
            className="self-start rounded-md bg-error px-4 py-2 text-sm font-medium text-white hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-error focus:ring-offset-1"
          >
            Try Again
          </button>
        </div>
      )}    </div>
  );
}
