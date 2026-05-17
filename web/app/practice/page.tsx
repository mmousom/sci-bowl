"use client";

import { useEffect, useRef, useState } from "react";
import FilterBar from "@/components/FilterBar";
import QuestionWorkspace from "@/components/QuestionWorkspace";
import AnswerFeedback from "@/components/AnswerFeedback";
import ScoreDisplay from "@/components/ScoreDisplay";
import { readScore, writeScore } from "@/lib/score";
import type {
  AnswerFormatFilter,
  PracticeFilter,
  QuestionResponse,
  SessionScore,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_FILTER: PracticeFilter = {
  category: "All Categories",
  format: "All",
  setRound: "All Rounds",
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type QuestionState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "loaded"; question: QuestionResponse }
  | { status: "not_found" }
  | { status: "error" };

type CategoriesState =
  | { status: "loading" }
  | { status: "loaded"; categories: string[] }
  | { status: "error" };

type RoundsState =
  | { status: "loading" }
  | { status: "loaded"; rounds: string[] }
  | { status: "error" };

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/** Fetches the category list on mount; exposes a retry function. */
function useCategories(): { state: CategoriesState; retry: () => void } {
  const [state, setState] = useState<CategoriesState>({ status: "loading" });

  const load = async () => {
    setState({ status: "loading" });
    try {
      const res = await fetch("/api/categories");
      if (!res.ok) throw new Error("categories fetch failed");
      const categories = (await res.json()) as string[];
      setState({ status: "loaded", categories });
    } catch {
      setState({ status: "error" });
    }
  };

  useEffect(() => { load(); }, []);
  return { state, retry: load };
}

/** Fetches the rounds list on mount; exposes a retry function. */
function useRounds(): { state: RoundsState; retry: () => void } {
  const [state, setState] = useState<RoundsState>({ status: "loading" });

  const load = async () => {
    setState({ status: "loading" });
    try {
      const res = await fetch("/api/rounds");
      if (!res.ok) throw new Error("rounds fetch failed");
      const rounds = (await res.json()) as string[];
      setState({ status: "loaded", rounds });
    } catch {
      setState({ status: "error" });
    }
  };

  useEffect(() => { load(); }, []);
  return { state, retry: load };
}

/** How many questions to fetch per batch. */
const BATCH_SIZE = 50;

/** Refetch when the local queue drops to this many remaining. */
const REFETCH_THRESHOLD = 5;

/** Builds the batch fetch URL for a given filter. */
function buildBatchUrl(filter: PracticeFilter): string {
  const params = new URLSearchParams({
    category: filter.category,
    format: filter.format,
    setRound: filter.setRound,
    batch: "1",
  });
  return `/api/question?${params.toString()}`;
}

/** Fetches a shuffled batch of questions for the given filter. */
async function fetchBatch(
  filter: PracticeFilter,
  signal: AbortSignal
): Promise<QuestionResponse[]> {
  const res = await fetch(buildBatchUrl(filter), { signal });
  if (res.status === 404) return [];
  if (!res.ok) throw new Error("batch fetch failed");
  return (await res.json()) as QuestionResponse[];
}

/**
 * Manages a local question queue.
 * Fetches a batch of up to 50 shuffled questions on load/filter change,
 * serves them in sequence (no repeats within a batch), and refetches
 * in the background when the queue drops below REFETCH_THRESHOLD.
 */
function useQuestion(): {
  state: QuestionState;
  load: (filter: PracticeFilter) => void;
  advance: () => void;
} {
  const [state, setState] = useState<QuestionState>({ status: "idle" });
  const queueRef = useRef<QuestionResponse[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const filterRef = useRef<PracticeFilter | null>(null);

  /** Pops the next question from the queue and updates state. */
  const popNext = () => {
    const next = queueRef.current.shift();
    if (next) {
      setState({ status: "loaded", question: next });
    } else {
      setState({ status: "not_found" });
    }
  };

  /** Fetches a fresh batch, fills the queue, then pops the first item. */
  const fetchAndPop = (filter: PracticeFilter, signal: AbortSignal) => {
    setState({ status: "loading" });
    fetchBatch(filter, signal)
      .then((batch) => {
        if (signal.aborted) return;
        if (batch.length === 0) { setState({ status: "not_found" }); return; }
        queueRef.current = batch;
        popNext();
      })
      .catch((err: unknown) => {
        if (err instanceof Error && err.name === "AbortError") return;
        if (!signal.aborted) setState({ status: "error" });
      });
  };

  const load = (filter: PracticeFilter) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    filterRef.current = filter;
    queueRef.current = []; // clear stale queue on filter change
    fetchAndPop(filter, controller.signal);
  };

  /** Called by the page on Next/Skip — pops from queue, refetches if low. */
  const advance = () => {
    if (queueRef.current.length === 0 && filterRef.current) {
      // Queue exhausted — fetch a new batch
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      fetchAndPop(filterRef.current, controller.signal);
      return;
    }
    popNext();
    // Background refetch when queue is running low
    if (
      queueRef.current.length <= REFETCH_THRESHOLD &&
      filterRef.current
    ) {
      const filter = filterRef.current;
      const bgController = new AbortController();
      fetchBatch(filter, bgController.signal)
        .then((batch) => {
          if (batch.length > 0) queueRef.current.push(...batch);
        })
        .catch(() => { /* silent background failure */ });
    }
  };

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  return { state, load: (filter) => { load(filter); }, advance };
}

// ---------------------------------------------------------------------------
// Score helpers
// ---------------------------------------------------------------------------

/** Returns an updated score after a correct answer. */
function applyCorrect(score: SessionScore): SessionScore {
  return { correct: score.correct + 1, total: score.total + 1 };
}

/** Returns an updated score after an incorrect answer. */
function applyIncorrect(score: SessionScore): SessionScore {
  return { correct: score.correct, total: score.total + 1 };
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Shown while a question is loading. */
function LoadingPlaceholder() {
  return (
    <div className="flex items-center justify-center rounded-xl border border-primary/10 bg-white p-10 shadow-sm">
      <span className="text-sm text-gray-500">Loading question…</span>
    </div>
  );
}

/** Shown when no questions match the current filter. */
function NoQuestionsMessage() {
  return (
    <div className="rounded-xl border border-primary/10 bg-white p-8 text-center shadow-sm">
      <p className="text-sm text-gray-600">
        No questions found for this filter. Try a different category or format.
      </p>
    </div>
  );
}

/** Shown when the question fetch returns a 500. */
function QuestionErrorMessage({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-error bg-red-50 p-6 shadow-sm">
      <span className="flex-1 text-sm text-error">
        Failed to load question. Please try again.
      </span>
      <button
        onClick={onRetry}
        className="rounded-md bg-error px-4 py-2 text-sm font-medium text-white hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-error focus:ring-offset-1"
      >
        Retry
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Practice page
// ---------------------------------------------------------------------------

/**
 * Client Component for the /practice route.
 *
 * Orchestrates category loading, question fetching, answer evaluation,
 * session score tracking, and skip/next navigation.
 */
export default function PracticePage() {
  const [filter, setFilter] = useState<PracticeFilter>(DEFAULT_FILTER);
  const [score, setScore] = useState<SessionScore>({ correct: 0, total: 0 });
  const [isAnswered, setIsAnswered] = useState(false);
  const [lastCorrect, setLastCorrect] = useState<boolean | null>(null);

  const { state: catState, retry: retryCategories } = useCategories();
  const { state: roundsState } = useRounds();
  const { state: qState, load: loadQuestion, advance } = useQuestion();

  // Fetch a new question whenever the filter changes (including on mount)
  useEffect(() => {
    setIsAnswered(false);
    setLastCorrect(null);
    loadQuestion(filter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  // Read persisted score from localStorage on mount
  useEffect(() => {
    setScore(readScore());
  }, []);

  const handleCategoryChange = (category: string) => {
    setFilter((prev) => ({ ...prev, category }));
  };

  const handleFormatChange = (format: AnswerFormatFilter) => {
    setFilter((prev) => ({ ...prev, format }));
  };

  const handleRoundChange = (setRound: string) => {
    setFilter((prev) => ({ ...prev, setRound }));
  };

  const handleAnswerSubmit = (isCorrect: boolean) => {
    const updated = isCorrect ? applyCorrect(score) : applyIncorrect(score);
    setScore(updated);
    writeScore(updated);
    setIsAnswered(true);
    setLastCorrect(isCorrect);
  };

  const handleNext = () => {
    setIsAnswered(false);
    setLastCorrect(null);
    advance();
  };

  const handleSkip = () => {
    setIsAnswered(false);
    setLastCorrect(null);
    advance();
  };

  const categories = catState.status === "loaded" ? catState.categories : [];
  const rounds = roundsState.status === "loaded" ? roundsState.rounds : [];

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 py-6">
      {/* Score */}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-primary">Practice</h1>
        <ScoreDisplay correct={score.correct} total={score.total} />
      </div>

      {/* Filters */}
      <FilterBar
        categories={categories}
        rounds={rounds}
        selectedCategory={filter.category}
        selectedFormat={filter.format}
        selectedRound={filter.setRound}
        onCategoryChange={handleCategoryChange}
        onFormatChange={handleFormatChange}
        onRoundChange={handleRoundChange}
        isLoading={catState.status === "error"}
      />

      {/* Category error retry */}
      {catState.status === "error" && (
        <button
          onClick={retryCategories}
          className="self-start text-sm text-primary underline hover:opacity-80"
        >
          Retry loading categories
        </button>
      )}

      {/* Question area */}
      {qState.status === "loading" && <LoadingPlaceholder />}
      {qState.status === "not_found" && <NoQuestionsMessage />}
      {qState.status === "error" && (
        <QuestionErrorMessage onRetry={() => loadQuestion(filter)} />
      )}
      {qState.status === "loaded" && (
        <QuestionWorkspace
          question={qState.question}
          onAnswerSubmit={handleAnswerSubmit}
          isAnswered={isAnswered}
        />
      )}

      {/* Answer feedback */}
      {isAnswered && lastCorrect !== null && qState.status === "loaded" && (
        <AnswerFeedback
          isCorrect={lastCorrect}
          correctAnswer={qState.question.answer}
          onNext={handleNext}
        />
      )}

      {/* Skip button — always visible when a question is loaded and not yet answered */}
      {qState.status === "loaded" && !isAnswered && (
        <div className="flex justify-end">
          <button
            onClick={handleSkip}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary/30"
          >
            Skip
          </button>
        </div>
      )}
    </div>
  );
}
