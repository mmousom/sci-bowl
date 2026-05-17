"use client";

/** Props for the ScoreDisplay badge component. */
interface ScoreDisplayProps {
  correct: number;
  total: number;
}

/**
 * Compact pill badge that shows the current session score as "correct / total".
 * Visible at all times during a practice session.
 */
export default function ScoreDisplay({ correct, total }: ScoreDisplayProps) {
  return (
    <span className="inline-flex items-center rounded-full bg-surface border border-primary px-3 py-1 text-sm font-semibold text-primary">
      {correct} / {total}
    </span>
  );
}
