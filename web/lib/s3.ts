import "server-only";

import { S3Client } from "@aws-sdk/client-s3";
import { fromIni } from "@aws-sdk/credential-providers";

const REGION = process.env.AWS_REGION ?? "us-east-1";

/** S3 bucket that holds the raw PDF files. */
export const PDF_BUCKET = "eshaan-sci-bowl-paper";

/** S3 key prefix under which all PDFs are stored. */
export const PDF_PREFIX = "raw-pdf-vault/middle-school/";

/**
 * Returns an S3Client configured for the current environment.
 * Uses the named AWS profile locally (via AWS_PROFILE env var) and
 * falls back to the default credential chain in production.
 */
export function getS3Client(): S3Client {
  const profile = process.env.AWS_PROFILE;
  return profile
    ? new S3Client({ region: REGION, credentials: fromIni({ profile }) })
    : new S3Client({ region: REGION });
}
