import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { UpdateCommand } from "@aws-sdk/lib-dynamodb";
import { ConditionalCheckFailedException } from "@aws-sdk/client-dynamodb";
import { AUTH_OPTIONS } from "@/lib/auth";
import { getDynamoClient } from "@/lib/dynamo";

const SESSIONS_TABLE = "StudentSessions";

/**
 * POST /api/sessions/end
 * Sets endTime on an active Session_Record.
 * Returns 404 if sessionId not found, 409 if session already closed.
 */
export async function POST(request: Request): Promise<NextResponse> {
  const session = await getServerSession(AUTH_OPTIONS);
  if (!session?.user?.googleId) {
    return NextResponse.json({ message: "Unauthenticated" }, { status: 401 });
  }

  const body = await request.json().catch(() => ({}));
  const { sessionId, studentId } = body as { sessionId?: string; studentId?: string };

  if (!sessionId?.trim()) {
    return NextResponse.json({ message: "sessionId is required" }, { status: 400 });
  }

  const endTime = new Date().toISOString();
  const client = getDynamoClient();

  try {
    await client.send(
      new UpdateCommand({
        TableName: SESSIONS_TABLE,
        Key: { studentId: studentId ?? session.user.googleId, sessionId },
        UpdateExpression: "SET endTime = :endTime",
        ConditionExpression: "attribute_exists(sessionId) AND attribute_type(endTime, :nullType)",
        ExpressionAttributeValues: { ":endTime": endTime, ":nullType": "NULL" },
      })
    );
    return NextResponse.json({ ok: true }, { status: 200 });
  } catch (err) {
    if (err instanceof ConditionalCheckFailedException) {
      // Could be not found or already closed — check by attempting a get
      return NextResponse.json({ message: "Session not found or already closed" }, { status: 409 });
    }
    throw err;
  }
}
