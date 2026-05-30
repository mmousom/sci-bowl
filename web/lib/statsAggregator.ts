import type { CompletedSession, TopicStat } from "@/lib/types";

const MS_PER_MINUTE = 60_000;
const MINUTES_PER_HOUR = 60;

/**
 * Computes total study time in whole minutes from a list of completed sessions.
 * Each session's duration is floored to the nearest minute.
 */
export function computeTotalMinutes(sessions: CompletedSession[]): number {
  return sessions.reduce((total, session) => {
    const durationMs =
      Date.parse(session.endTime) - Date.parse(session.startTime);
    return total + Math.floor(durationMs / MS_PER_MINUTE);
  }, 0);
}

/**
 * Groups sessions by topic, sums duration per group, and returns a sorted list.
 * Topics with zero total minutes are excluded.
 * Sorted descending by minutes, then alphabetically by topic name.
 */
export function computeTopicBreakdown(sessions: CompletedSession[]): TopicStat[] {
  const minutesByTopic = new Map<string, number>();

  for (const session of sessions) {
    const durationMs =
      Date.parse(session.endTime) - Date.parse(session.startTime);
    const minutes = Math.floor(durationMs / MS_PER_MINUTE);
    minutesByTopic.set(session.topic, (minutesByTopic.get(session.topic) ?? 0) + minutes);
  }

  return Array.from(minutesByTopic.entries())
    .filter(([, totalMinutes]) => totalMinutes > 0)
    .map(([topic, totalMinutes]) => ({ topic, totalMinutes }))
    .sort((a, b) => b.totalMinutes - a.totalMinutes || a.topic.localeCompare(b.topic));
}

/**
 * Returns the N most recent sessions ordered by startTime descending.
 * ISO 8601 strings sort correctly lexicographically, so string comparison is used.
 */
export function selectRecentSessions(
  sessions: CompletedSession[],
  limit: number
): CompletedSession[] {
  return [...sessions]
    .sort((a, b) => (a.startTime < b.startTime ? 1 : a.startTime > b.startTime ? -1 : 0))
    .slice(0, limit);
}

/**
 * Formats a total-minutes value as a human-readable duration string.
 * Returns "0m" for zero, "Ym" for values under an hour, and "Xh Ym" for an hour or more.
 */
export function formatDuration(totalMinutes: number): string {
  if (totalMinutes === 0) return "0m";
  if (totalMinutes < MINUTES_PER_HOUR) return `${totalMinutes}m`;
  const hours = Math.floor(totalMinutes / MINUTES_PER_HOUR);
  const minutes = totalMinutes % MINUTES_PER_HOUR;
  return `${hours}h ${minutes}m`;
}
