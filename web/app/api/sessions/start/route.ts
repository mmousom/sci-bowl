import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { PutCommand } from "@aws-sdk/lib-dynamodb";
import { AUTH_OPTIONS } from "@/lib/auth";
import { getDynamoClient } from "@/lib/dynamo";

const SESSIONS_TABLE = "StudentSessions";

/**
 * POST /api/sessions/start
 * Creates a new Session_Record in DynamoDB for the authenticated student.
 * Returns { sessionId } on success.
 */
export async function POST(request: Request): Promise<NextResponse> {
  const session = await getServerSession(AUTH_OPTIONS);
  if (!session?.user?.googleId) {
    return NextResponse.json({ message: "Unauthenticated" }, { status: 401 });
  }

  const body = await request.json().catch(() => ({}));
  const { studentId, topic } = body as { studentId?: string; topic?: string };

  if (!studentId?.trim() || !topic?.trim()) {
    return NextResponse.json(
      { message: "studentId and topic are required" },
      { status: 400 }
    );
  }

  const sessionId = crypto.randomUUID();
  const startTime = new Date().toISOString();

  const client = getDynamoClient();
  await client.send(
    new PutCommand({
      TableName: SESSIONS_TABLE,
      Item: { studentId, sessionId, topic, startTime, endTime: null, questionCount: 0 },
    })
  );

  return NextResponse.json({ sessionId }, { status: 200 });
}
