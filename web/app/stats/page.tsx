import { getServerSession } from "next-auth";
import { QueryCommand } from "@aws-sdk/lib-dynamodb";
import { AUTH_OPTIONS } from "@/lib/auth";
import { getDynamoClient } from "@/lib/dynamo";
import {
  computeTotalMinutes,
  computeTopicBreakdown,
  selectRecentSessions,
  formatDuration,
} from "@/lib/statsAggregator";
import type { CompletedSession, StatsPayload } from "@/lib/types";

const SESSIONS_TABLE = "StudentSessions";
const GSI_NAME = "GSI_StudentId_StartTime";
const RECENT_SESSIONS_LIMIT = 10;

/** Formats an ISO 8601 date string as "MMM D, YYYY" (e.g., "Jan 5, 2025"). */
function formatDate(isoString: string): string {
  return new Date(isoString).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/** Queries DynamoDB directly and aggregates stats for the authenticated student. */
async function loadStats(studentId: string): Promise<StatsPayload> {
  const client = getDynamoClient();
  const result = await client.send(
    new QueryCommand({
      TableName: SESSIONS_TABLE,
      IndexName: GSI_NAME,
      KeyConditionExpression: "studentId = :studentId",
      ExpressionAttributeValues: { ":studentId": studentId },
    })
  );

  const completedSessions = (result.Items ?? []).filter(
    (item) => item.endTime != null && typeof item.endTime === "string"
  ) as CompletedSession[];

  return {
    totalStudyTimeMinutes: computeTotalMinutes(completedSessions),
    topicBreakdown: computeTopicBreakdown(completedSessions),
    recentSessions: selectRecentSessions(completedSessions, RECENT_SESSIONS_LIMIT),
  };
}

/**
 * Stats dashboard page at /stats.
 * Server Component — queries DynamoDB directly, no self-fetch needed.
 */
export default async function StatsPage() {
  const session = await getServerSession(AUTH_OPTIONS);

  // Middleware protects this route, but guard defensively
  if (!session?.user?.googleId) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-8 py-6">
        <h1 className="text-lg font-semibold text-primary">Stats</h1>
        <p className="text-sm text-gray-500">Please sign in to view your stats.</p>
      </div>
    );
  }

  let stats: StatsPayload | null = null;
  let errorMessage = "";
  try {
    stats = await loadStats(session.user.googleId);
  } catch (err) {
    errorMessage = err instanceof Error ? err.message : String(err);
    console.error("[StatsPage] Failed to load stats:", err);
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-8 py-6">
      <h1 className="text-lg font-semibold text-primary">Stats</h1>

      {/* Error state */}
      {stats === null && (
        <div className="rounded-xl border border-error bg-red-50 p-6 text-sm text-error">
          <p className="font-medium">Could not load your stats.</p>
          {errorMessage && (
            <p className="mt-2 font-mono text-xs opacity-75">{errorMessage}</p>
          )}
        </div>
      )}

      {stats !== null && (
        <>
          {/* Total Study Time */}
          <section className="rounded-xl border border-primary/10 bg-white p-6 shadow-sm dark:bg-[#1a1a24]">
            <h2 className="mb-1 text-sm font-medium text-gray-500">Total Study Time</h2>
            <p className="text-3xl font-bold text-primary">
              {formatDuration(stats.totalStudyTimeMinutes)}
            </p>
          </section>

          {/* Topic Breakdown */}
          <section className="rounded-xl border border-primary/10 bg-white p-6 shadow-sm dark:bg-[#1a1a24]">
            <h2 className="mb-4 text-sm font-medium text-gray-500">Time by Topic</h2>
            {stats.topicBreakdown.length === 0 ? (
              <p className="text-sm text-gray-400">No completed sessions yet.</p>
            ) : (
              <ul className="flex flex-col gap-3">
                {stats.topicBreakdown.map(({ topic, totalMinutes }) => (
                  <li key={topic} className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      {topic}
                    </span>
                    <span className="text-sm text-gray-500">
                      {formatDuration(totalMinutes)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Recent Activity */}
          <section className="rounded-xl border border-primary/10 bg-white p-6 shadow-sm dark:bg-[#1a1a24]">
            <h2 className="mb-4 text-sm font-medium text-gray-500">Recent Activity</h2>
            {stats.recentSessions.length === 0 ? (
              <p className="text-sm text-gray-400">No activity recorded yet.</p>
            ) : (
              <ul className="flex flex-col divide-y divide-gray-100 dark:divide-gray-800">
                {stats.recentSessions.map((s) => {
                  const durationMs =
                    new Date(s.endTime).getTime() - new Date(s.startTime).getTime();
                  const durationMin = Math.floor(durationMs / 60_000);
                  return (
                    <li
                      key={s.sessionId}
                      className="flex items-center justify-between py-3"
                    >
                      <div>
                        <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                          {s.topic}
                        </p>
                        <p className="text-xs text-gray-400">{formatDate(s.startTime)}</p>
                      </div>
                      <span className="text-sm text-gray-500">{durationMin}m</span>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
