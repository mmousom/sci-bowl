"use client";

import { useEffect, useRef, useState } from "react";
import type { QuestionResponse } from "@/lib/types";
import MathText, { normalizeForComparison } from "@/components/MathText";
import ExplanationPanel from "@/components/ExplanationPanel";

/** Labels for the four multiple choice answer slots. */
const MC_LABELS = ["W", "X", "Y", "Z"] as const;

/**
 * Parses a Science Bowl answer string into a list of accepted values.
 *
 * Handles the common format: `CsF (ACCEPT: CESIUM FLUORIDE)`
 * Returns the primary answer plus any alternatives listed after "ACCEPT:".
 */
function parseAcceptedAnswers(raw: string): string[] {
  const acceptMatch = raw.match(/^(.*?)\s*\(ACCEPT:\s*(.*?)\)\s*$/i);
  if (!acceptMatch) return [raw.trim()];

  const primary = acceptMatch[1].trim();
  const alternatives = acceptMatch[2]
    .split(/\s*(?:OR|;)\s*/i)
    .map((s) => s.trim())
    .filter(Boolean);

  return [primary, ...alternatives];
}

/** Returns true if the user's input matches any accepted answer (case-insensitive, LaTeX-stripped). */
function isAnswerCorrect(userInput: string, storedAnswer: string): boolean {
  const normalized = normalizeForComparison(userInput);
  return parseAcceptedAnswers(storedAnswer).some(
    (accepted) => normalizeForComparison(accepted) === normalized
  );
}

/** Props for the QuestionWorkspace component. */
interface QuestionWorkspaceProps {
  question: QuestionResponse;
  onAnswerSubmit: (isCorrect: boolean) => void;
  isAnswered: boolean;
}

/** Metadata pill showing a single label/value pair. */
function MetaLabel({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-primary/30 bg-surface dark:bg-white/10 px-3 py-0.5 text-xs font-medium text-primary dark:text-blue-300">
      <span className="opacity-60">{label}:</span>
      {value}
    </span>
  );
}

/** Renders four labeled clickable cards for a Multiple Choice question. */
function MultipleChoiceInput({
  choices,
  onSelect,
  isAnswered,
}: {
  choices: string[];
  onSelect: (index: number) => void;
  isAnswered: boolean;
}) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {choices.map((choice, i) => (
        <button
          key={i}
          disabled={isAnswered}
          onClick={() => onSelect(i)}
          className="flex items-start gap-3 rounded-lg border border-primary/20 bg-white dark:bg-white/5 dark:border-white/10 p-4 text-left
            text-gray-800 dark:text-gray-100
            transition-colors hover:border-primary hover:bg-primary/5 dark:hover:bg-primary/20
            active:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 dark:bg-primary/30 text-sm font-bold text-primary dark:text-blue-300">
            {MC_LABELS[i]}
          </span>
          <MathText text={choice} className="text-sm leading-snug" />
        </button>
      ))}
    </div>
  );
}

/** Renders an auto-focused text input and Submit button for a Short Answer question. */
function ShortAnswerInput({
  value,
  onChange,
  onSubmit,
  isAnswered,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  isAnswered: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !isAnswered) onSubmit();
  };

  /** Wrap the raw input in $...$ so MathText renders it as inline math. */
  const hasLatex = value.trim().length > 0 && value.includes("\\");
  const previewText = hasLatex ? `$${value}$` : "";

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isAnswered}
          placeholder="Type your answer… (LaTeX ok, e.g. \pi)"
          className="flex-1 rounded-lg border border-primary/30 bg-white dark:bg-white/5 dark:border-white/10
            px-4 py-2.5 text-sm text-gray-800 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500
            outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/20
            disabled:cursor-not-allowed disabled:opacity-60"
        />
        <button
          onClick={onSubmit}
          disabled={isAnswered || value.trim() === ""}
          className="rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-white
            transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Submit
        </button>
      </div>

      {/* Live LaTeX preview — only shown when input contains a backslash */}
      {hasLatex && (
        <div className="flex items-center gap-2 rounded-md border border-primary/20 bg-primary/5 dark:bg-primary/10 px-3 py-1.5">
          <span className="text-xs text-gray-500 dark:text-gray-400 shrink-0">Preview:</span>
          <MathText text={previewText} className="text-sm text-gray-800 dark:text-gray-100" />
        </div>
      )}
    </div>
  );
}

/** Possible states for the explanation fetch. */
type ExplainState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "loaded"; explanation: string }
  | { status: "error" };

/**
 * Displays the current question and collects the student's answer.
 *
 * Renders the question stem, Category and MatchType metadata labels, and
 * exactly one answer input — Multiple Choice cards (W/X/Y/Z) or a Short
 * Answer text input — based on `question.answer_format`. All answer state
 * is cleared whenever the `question` prop changes. Calls `onAnswerSubmit`
 * with a boolean indicating correctness after evaluation.
 *
 * Also renders a "Learn More" button that fetches a Bedrock-generated
 * explanation for the current question on demand.
 */
export default function QuestionWorkspace({
  question,
  onAnswerSubmit,
  isAnswered,
}: QuestionWorkspaceProps) {
  const [shortAnswerText, setShortAnswerText] = useState("");
  const [explainState, setExplainState] = useState<ExplainState>({ status: "idle" });
  const explainAbortRef = useRef<AbortController | null>(null);

  // Clear answer state and explanation whenever the question changes
  useEffect(() => {
    setShortAnswerText("");
    explainAbortRef.current?.abort();
    explainAbortRef.current = null;
    setExplainState({ status: "idle" });
  }, [question]);

  // Cleanup on unmount
  useEffect(() => {
    return () => { explainAbortRef.current?.abort(); };
  }, []);

  const fetchExplanation = () => {
    explainAbortRef.current?.abort();
    const controller = new AbortController();
    explainAbortRef.current = controller;
    setExplainState({ status: "loading" });

    fetch("/api/explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question_stem: question.question_stem,
        answer: question.answer,
        Category: question.Category,
        MatchType: question.MatchType,
      }),
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as { explanation: string };
        setExplainState({ status: "loaded", explanation: data.explanation });
      })
      .catch((err: unknown) => {
        if (err instanceof Error && err.name === "AbortError") return;
        setExplainState({ status: "error" });
      });
  };

  const handleLearnMore = () => {
    if (explainState.status === "loading") return;
    // Toggle: if panel is visible, dismiss it
    if (explainState.status === "loaded" || explainState.status === "error") {
      setExplainState({ status: "idle" });
      return;
    }
    fetchExplanation();
  };

  const handleDismiss = () => {
    explainAbortRef.current?.abort();
    explainAbortRef.current = null;
    setExplainState({ status: "idle" });
  };

  const evaluateShortAnswer = () => {
    onAnswerSubmit(isAnswerCorrect(shortAnswerText, question.answer));
  };

  const evaluateMultipleChoice = (index: number) => {
    const selected = question.answer_choices[index];
    onAnswerSubmit(isAnswerCorrect(selected, question.answer));
  };

  const isPanelVisible =
    explainState.status === "loading" ||
    explainState.status === "loaded" ||
    explainState.status === "error";

  const isLearnMoreLoading = explainState.status === "loading";

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-5 rounded-xl border border-primary/10 dark:border-white/10 bg-white dark:bg-white/5 p-6 shadow-sm">
        {/* Metadata labels */}
        <div className="flex flex-wrap gap-2">
          <MetaLabel label="Category" value={question.Category} />
          <MetaLabel label="Type" value={question.MatchType} />
        </div>

        {/* Question stem */}
        <MathText
          text={question.question_stem}
          className="text-base font-medium leading-relaxed text-gray-800 dark:text-gray-100"
        />

        {/* Answer input — exactly one type rendered at a time */}
        {question.answer_format === "Multiple Choice" ? (
          <MultipleChoiceInput
            choices={question.answer_choices}
            onSelect={evaluateMultipleChoice}
            isAnswered={isAnswered}
          />
        ) : (
          <ShortAnswerInput
            value={shortAnswerText}
            onChange={setShortAnswerText}
            onSubmit={evaluateShortAnswer}
            isAnswered={isAnswered}
          />
        )}

        {/* Learn More button */}
        <div className="flex justify-start">
          <button
            onClick={handleLearnMore}
            disabled={isLearnMoreLoading}
            aria-label={isPanelVisible && !isLearnMoreLoading ? "Hide explanation" : "Learn more about this topic"}
            className="inline-flex items-center gap-2 rounded-md border border-primary/30 px-4 py-2 text-sm font-medium text-primary
              hover:bg-primary/5 dark:hover:bg-primary/20 transition-colors
              disabled:cursor-not-allowed disabled:opacity-60
              focus:outline-none focus:ring-2 focus:ring-primary/30"
          >
            {isLearnMoreLoading ? (
              <>
                <span
                  className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-primary border-t-transparent"
                  aria-hidden="true"
                />
                Loading…
              </>
            ) : (
              "Learn More"
            )}
          </button>
        </div>
      </div>

      {/* Explanation panel — rendered below the workspace card */}
      {isPanelVisible && (
        <ExplanationPanel
          state={explainState}
          onDismiss={handleDismiss}
          onRetry={fetchExplanation}
        />
      )}
    </div>
  );
}
