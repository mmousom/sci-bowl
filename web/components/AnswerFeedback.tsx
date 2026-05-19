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
    <div className={`rounded-lg border-2 ${borderColor} ${bgColor} p-4 flex flex-col gap-3`}>
      <p className={`text-lg font-semibold ${textColor}`}>
        {isCorrect ? (
          "Correct!"
        ) : (
          <>Incorrect — the correct answer is: <MathText text={correctAnswer} /></>
        )}
      </p>
      <button
        onClick={onNext}
        className="self-start rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity"
      >
        Next Question
      </button>
    </div>
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
