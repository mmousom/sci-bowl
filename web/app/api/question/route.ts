import { NextResponse } from "next/server";
import { QueryCommand, ScanCommand } from "@aws-sdk/lib-dynamodb";
import type {
  QueryCommandInput,
  ScanCommandInput,
} from "@aws-sdk/lib-dynamodb";

import { getDynamoClient } from "@/lib/dynamo";
import type { DynamoQuestion, QuestionResponse } from "@/lib/types";

const TABLE_NAME = "ScienceBowlQuestions";
const GSI_NAME = "GSI_Category_MatchType";
const ALL_CATEGORIES = "All Categories";
const ALL_ROUNDS = "All Rounds";

/** Fetches all pages from a ScanCommand, returning the full item list. */
async function scanAll(input: ScanCommandInput): Promise<DynamoQuestion[]> {
  const client = getDynamoClient();
  const items: DynamoQuestion[] = [];
  let lastKey: Record<string, unknown> | undefined;

  do {
    const command = new ScanCommand({ ...input, ExclusiveStartKey: lastKey });
    const response = await client.send(command);
    items.push(...((response.Items ?? []) as DynamoQuestion[]));
    lastKey = response.LastEvaluatedKey as Record<string, unknown> | undefined;
  } while (lastKey !== undefined);

  return items;
}

/** Fetches all pages from a QueryCommand, returning the full item list. */
async function queryAll(input: QueryCommandInput): Promise<DynamoQuestion[]> {
  const client = getDynamoClient();
  const items: DynamoQuestion[] = [];
  let lastKey: Record<string, unknown> | undefined;

  do {
    const command = new QueryCommand({ ...input, ExclusiveStartKey: lastKey });
    const response = await client.send(command);
    items.push(...((response.Items ?? []) as DynamoQuestion[]));
    lastKey = response.LastEvaluatedKey as Record<string, unknown> | undefined;
  } while (lastKey !== undefined);

  return items;
}

/** Number of questions to fetch per batch. */
const BATCH_SIZE = 200;

/** Shuffles an array in-place using Fisher-Yates. */
function shuffle<T>(arr: T[]): T[] {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

/** Picks one item at random from a non-empty array. */
function pickRandom<T>(items: T[]): T {
  return items[Math.floor(Math.random() * items.length)];
}

/** Strips source_s3_key and returns only the required response fields. */
function toQuestionResponse(item: DynamoQuestion): QuestionResponse {
  return {
    Set_Round: item.Set_Round,
    Question_Id: item.Question_Id,
    Category: item.Category,
    MatchType: item.MatchType,
    question_stem: item.question_stem,
    answer_choices: item.answer_choices,
    answer: item.answer,
    answer_format: item.answer_format,
  };
}

/**
 * GET /api/question?category=&format=&setRound=&batch=1
 *
 * Returns one or more randomly selected questions matching the given filters.
 * - batch=1 → returns a JSON array of up to BATCH_SIZE shuffled questions
 * - batch omitted / batch=0 → returns a single QuestionResponse object (legacy)
 *
 * Implements all 6 query branches based on category and format params,
 * with an optional Set_Round filter applied as a post-scan/query filter.
 */
export async function GET(request: Request): Promise<NextResponse> {
  const { searchParams } = new URL(request.url);
  const category = searchParams.get("category") ?? "";
  const format = searchParams.get("format") ?? "";
  const setRound = searchParams.get("setRound") ?? "";
  const batchMode = searchParams.get("batch") === "1";

  const isAllCategories = !category || category === ALL_CATEGORIES;
  const isAllRounds = !setRound || setRound === ALL_ROUNDS;
  const isMatchTypeFilter = format === "TOSS-UP" || format === "BONUS";
  const isAnswerFormatFilter =
    format === "Multiple Choice" || format === "Short Answer";

  try {
    let items: DynamoQuestion[];

    if (isAllCategories) {
      items = await fetchAllCategories(format, isMatchTypeFilter, isAnswerFormatFilter);
    } else {
      items = await fetchSpecificCategory(
        category,
        format,
        isMatchTypeFilter,
        isAnswerFormatFilter
      );
    }

    // Apply Set_Round filter in-memory after the primary query/scan
    if (!isAllRounds) {
      items = items.filter((item) => item.Set_Round === setRound);
    }

    if (items.length === 0) {
      return NextResponse.json(
        { message: "No questions found for this filter" },
        { status: 404 }
      );
    }

    if (batchMode) {
      const pool = shuffle(items).slice(0, BATCH_SIZE);
      return NextResponse.json(pool.map(toQuestionResponse));
    }

    return NextResponse.json(toQuestionResponse(pickRandom(items)));
  } catch (error) {
    console.error("[GET /api/question] DynamoDB error:", error);
    return NextResponse.json(
      { message: "Failed to fetch question" },
      { status: 500 }
    );
  }
}

/** Handles all branches where category is "All Categories" or omitted. */
async function fetchAllCategories(
  format: string,
  isMatchTypeFilter: boolean,
  isAnswerFormatFilter: boolean
): Promise<DynamoQuestion[]> {
  if (isMatchTypeFilter) {
    return scanAll({
      TableName: TABLE_NAME,
      FilterExpression: "MatchType = :mt",
      ExpressionAttributeValues: { ":mt": format },
    });
  }

  if (isAnswerFormatFilter) {
    return scanAll({
      TableName: TABLE_NAME,
      FilterExpression: "answer_format = :af",
      ExpressionAttributeValues: { ":af": format },
    });
  }

  return scanAll({ TableName: TABLE_NAME });
}

/** Handles all branches where a specific category is selected. */
async function fetchSpecificCategory(
  category: string,
  format: string,
  isMatchTypeFilter: boolean,
  isAnswerFormatFilter: boolean
): Promise<DynamoQuestion[]> {
  if (isMatchTypeFilter) {
    return queryAll({
      TableName: TABLE_NAME,
      IndexName: GSI_NAME,
      KeyConditionExpression: "Category = :cat AND MatchType = :mt",
      ExpressionAttributeValues: { ":cat": category, ":mt": format },
    });
  }

  if (isAnswerFormatFilter) {
    return queryAll({
      TableName: TABLE_NAME,
      IndexName: GSI_NAME,
      KeyConditionExpression: "Category = :cat",
      FilterExpression: "answer_format = :af",
      ExpressionAttributeValues: { ":cat": category, ":af": format },
    });
  }

  return queryAll({
    TableName: TABLE_NAME,
    IndexName: GSI_NAME,
    KeyConditionExpression: "Category = :cat",
    ExpressionAttributeValues: { ":cat": category },
  });
}
