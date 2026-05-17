import { NextResponse } from "next/server";
import { ScanCommand } from "@aws-sdk/lib-dynamodb";

import { getDynamoClient } from "@/lib/dynamo";

const TABLE_NAME = "ScienceBowlQuestions";

/**
 * GET /api/rounds
 *
 * Scans the table for all Set_Round values, deduplicates, sorts
 * alphabetically, and returns the full list.
 */
export async function GET(): Promise<NextResponse> {
  try {
    const client = getDynamoClient();
    const command = new ScanCommand({
      TableName: TABLE_NAME,
      ProjectionExpression: "Set_Round",
    });

    const response = await client.send(command);
    const items = response.Items ?? [];

    const rounds = Array.from(
      new Set(items.map((item) => item.Set_Round as string).filter(Boolean))
    ).sort();

    return NextResponse.json(rounds);
  } catch (error) {
    console.error("[GET /api/rounds] DynamoDB error:", error);
    return NextResponse.json(
      { message: "Failed to fetch rounds" },
      { status: 500 }
    );
  }
}
