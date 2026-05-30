import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { UpdateCommand } from "@aws-sdk/lib-dynamodb";
import { ConditionalCheckFailedException } from "@aws-sdk/client-dynamodb";
import { AUTH_OPTIONS } from "@/lib/auth";
import { getDynamoClient } from "@/lib/dynamo";

const SESSIONS_TABLE = "StudentSessions";

/**
 * POST /api/sessions/increment
 * Atomically increments questionCount by 1 for the given session.
 * Returns 404 if sessionId not found.
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

  const client = getDynamoClient();

  try {
    await client.send(
      new UpdateCommand({
        TableName: SESSIONS_TABLE,
        Key: { studentId: studentId ?? session.user.googleId, sessionId },
        UpdateExpression: "ADD questionCount :one",
        ConditionExpression: "attribute_exists(sessionId)",
        ExpressionAttributeValues: { ":one": 1 },
      })
    );
    return NextResponse.json({ ok: true }, { status: 200 });
  } catch (err) {
    if (err instanceof ConditionalCheckFailedException) {
      return NextResponse.json({ message: "Session not found" }, { status: 404 });
    }
    throw err;
  }
}
