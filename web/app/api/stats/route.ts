import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { QueryCommand } from "@aws-sdk/lib-dynamodb";
import { AUTH_OPTIONS } from "@/lib/auth";
import { getDynamoClient } from "@/lib/dynamo";
import {
  computeTotalMinutes,
  computeTopicBreakdown,
  selectRecentSessions,
} from "@/lib/statsAggregator";
import type { CompletedSession } from "@/lib/types";

const SESSIONS_TABLE = "StudentSessions";
const GSI_NAME = "GSI_StudentId_StartTime";
const RECENT_SESSIONS_LIMIT = 10;

/**
 * GET /api/stats
 * Returns aggregated session stats for the authenticated student.
 * Queries the GSI, filters completed sessions, and aggregates server-side.
 */
export async function GET(): Promise<NextResponse> {
  const session = await getServerSession(AUTH_OPTIONS);
  if (!session?.user?.googleId) {
    return NextResponse.json({ message: "Unauthenticated" }, { status: 401 });
  }

  const studentId = session.user.googleId;
  const client = getDynamoClient();

  try {
    const result = await client.send(
      new QueryCommand({
        TableName: SESSIONS_TABLE,
        IndexName: GSI_NAME,
        KeyConditionExpression: "studentId = :studentId",
        FilterExpression: "attribute_exists(endTime) AND endTime <> :nullVal",
        ExpressionAttributeValues: {
          ":studentId": studentId,
          ":nullVal": null,
        },
      })
    );

    const completedSessions = (result.Items ?? []).filter(
      (item) => item.endTime != null
    ) as CompletedSession[];

    const totalStudyTimeMinutes = computeTotalMinutes(completedSessions);
    const topicBreakdown = computeTopicBreakdown(completedSessions);
    const recentSessions = selectRecentSessions(completedSessions, RECENT_SESSIONS_LIMIT);

    return NextResponse.json(
      { totalStudyTimeMinutes, topicBreakdown, recentSessions },
      { status: 200 }
    );
  } catch (err) {
    console.error("[GET /api/stats] DynamoDB error:", err);
    return NextResponse.json(
      { message: "Failed to fetch stats" },
      { status: 500 }
    );
  }
}
