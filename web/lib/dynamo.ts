import "server-only";

import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient } from "@aws-sdk/lib-dynamodb";
import { fromIni } from "@aws-sdk/credential-providers";

const REGION = process.env.AWS_REGION ?? "us-east-1";

/**
 * Returns a DynamoDBDocumentClient configured for the current environment.
 *
 * - When AWS_PROFILE is set (local dev via .env.local): uses the named
 *   profile via fromIni so no credentials need to be hardcoded.
 * - Otherwise (production / CI with IAM role): uses the default credential
 *   chain (env vars, instance metadata, etc.).
 */
export function getDynamoClient(): DynamoDBDocumentClient {
  const profile = process.env.AWS_PROFILE;

  const baseClient = profile
    ? new DynamoDBClient({ region: REGION, credentials: fromIni({ profile }) })
    : new DynamoDBClient({ region: REGION });

  return DynamoDBDocumentClient.from(baseClient);
}
