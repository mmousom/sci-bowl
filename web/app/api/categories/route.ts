import { NextResponse } from "next/server";
import { ScanCommand } from "@aws-sdk/lib-dynamodb";

import { getDynamoClient } from "@/lib/dynamo";

const TABLE_NAME = "ScienceBowlQuestions";

/**
 * GET /api/categories
 *
 * Scans the ScienceBowlQuestions table for all Category values,
 * deduplicates them, sorts alphabetically, and returns the result.
 */
export async function GET(): Promise<NextResponse> {
  try {
    const client = getDynamoClient();
    const command = new ScanCommand({
      TableName: TABLE_NAME,
      ProjectionExpression: "Category",
    });

    const response = await client.send(command);
    const items = response.Items ?? [];

    const categories = Array.from(
      new Set(items.map((item) => item.Category as string).filter(Boolean))
    ).sort();

    return NextResponse.json(categories);
  } catch (error) {
    console.error("[GET /api/categories] DynamoDB error:", error);
    return NextResponse.json(
      { message: "Failed to fetch categories" },
      { status: 500 }
    );
  }
}
