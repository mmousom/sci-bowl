import { SessionScore } from "@/lib/types";

const SESSION_SCORE_KEY = "bowlprep_session_score";

const ZERO_SCORE: SessionScore = { correct: 0, total: 0 };

/**
 * Reads the current session score from localStorage.
 * Returns `{ correct: 0, total: 0 }` if the key is missing, the value is
 * malformed, or localStorage is unavailable (e.g. during SSR).
 */
export function readScore(): SessionScore {
  try {
    const raw = localStorage.getItem(SESSION_SCORE_KEY);
    if (raw === null) return { ...ZERO_SCORE };
    const parsed = JSON.parse(raw) as SessionScore;
    return { correct: parsed.correct ?? 0, total: parsed.total ?? 0 };
  } catch {
    return { ...ZERO_SCORE };
  }
}

/**
 * Persists the given session score to localStorage.
 * Silently does nothing if localStorage is unavailable (e.g. during SSR).
 */
export function writeScore(score: SessionScore): void {
  try {
    localStorage.setItem(SESSION_SCORE_KEY, JSON.stringify(score));
  } catch {
    // no-op when localStorage is unavailable
  }
}

/**
 * Resets the session score to `{ correct: 0, total: 0 }`, writes it to
 * localStorage, and returns the reset value.
 */
export function initScore(): SessionScore {
  const fresh: SessionScore = { ...ZERO_SCORE };
  writeScore(fresh);
  return fresh;
}
