"use client";

import MathText from "@/components/MathText";

/** Props for the AnswerFeedback overlay component. */
interface AnswerFeedbackProps {
  isCorrect: boolean;
  correctAnswer: string;
  onNext: () => void;
}

/** Plain-text fallback rendered when styled output cannot be produced. */
function PlainFeedback({ isCorrect, correctAnswer, onNext }: AnswerFeedbackProps) {
  return (
    <div>
      <p>{isCorrect ? "Correct!" : `Incorrect. Correct answer: ${correctAnswer}`}</p>
      <button onClick={onNext}>Next Question</button>
    </div>
  );
}

/** Styled feedback panel shown after an answer is submitted. */
function StyledFeedback({ isCorrect, correctAnswer, onNext }: AnswerFeedbackProps) {
  const borderColor = isCorrect ? "border-success" : "border-error";
  const textColor = isCorrect ? "text-success dark:text-emerald-400" : "text-error dark:text-red-400";
  const bgColor = isCorrect ? "bg-success/10 dark:bg-emerald-900/30" : "bg-error/10 dark:bg-red-900/30";

  return (
    <>
      {/* Inline feedback panel — result text */}
      <div className={`rounded-lg border-2 ${borderColor} ${bgColor} p-4`}>
        <p className={`text-base font-semibold ${textColor}`}>
          {isCorrect ? (
            "Correct!"
          ) : (
            <>Incorrect — the correct answer is: <MathText text={correctAnswer} /></>
          )}
        </p>
      </div>

      {/* Sticky Next Question bar on mobile, inline button on desktop */}
      <div className="md:hidden fixed bottom-14 inset-x-0 z-40 px-4 pb-3 pt-2 bg-surface dark:bg-[#0f0f14] border-t border-gray-200 dark:border-gray-800">
        <button
          onClick={onNext}
          className="w-full rounded-lg bg-primary py-3 text-sm font-semibold text-white hover:opacity-90 active:opacity-80 transition-opacity"
        >
          Next Question →
        </button>
      </div>

      {/* Desktop inline button */}
      <div className="hidden md:block">
        <button
          onClick={onNext}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity"
        >
          Next Question
        </button>
      </div>
    </>
  );
}

/**
 * Displays correct/incorrect feedback after an answer is submitted.
 * Shows a green highlight and "Correct!" on success, or a red highlight
 * with the correct answer on failure. Always renders a "Next Question" button.
 * Falls back to a plain-text indicator if styled rendering throws.
 */
export default function AnswerFeedback(props: AnswerFeedbackProps) {
  try {
    return <StyledFeedback {...props} />;
  } catch {
    return <PlainFeedback {...props} />;
  }
}
