import { NextResponse } from "next/server";
import { ListObjectsV2Command } from "@aws-sdk/client-s3";

import { getS3Client, PDF_BUCKET, PDF_PREFIX } from "@/lib/s3";

/** A single PDF entry returned by this route. */
export interface PdfEntry {
  /** Full S3 key, e.g. "raw-pdf-vault/middle-school/Sample-Set-13/2019-NSB-MSR-Round-1A.pdf" */
  key: string;
  /** Set folder name, e.g. "Sample-Set-13" */
  set: string;
  /** Filename without extension, e.g. "2019-NSB-MSR-Round-1A" */
  round: string;
  /** Four-digit year extracted from the filename, or null if not found */
  year: number | null;
}

/** Regex that matches a four-digit year between 2000 and 2099. */
const YEAR_RE = /\b(20\d{2})\b/;

/** Extracts a year from a filename stem, or returns null. */
function extractYear(stem: string): number | null {
  const match = YEAR_RE.exec(stem);
  return match ? parseInt(match[1], 10) : null;
}

/** Parses a full S3 key into a PdfEntry. Returns null for non-PDF keys. */
function parseKey(key: string): PdfEntry | null {
  // Key format: raw-pdf-vault/middle-school/{set}/{filename}.pdf
  const relative = key.slice(PDF_PREFIX.length);
  const slashIdx = relative.indexOf("/");
  if (slashIdx === -1) return null;

  const set = relative.slice(0, slashIdx);
  const filename = relative.slice(slashIdx + 1);
  if (!filename.endsWith(".pdf")) return null;

  const round = filename.slice(0, -4); // strip .pdf
  return { key, set, round, year: extractYear(round) };
}

/**
 * GET /api/pdf/list
 *
 * Lists all PDF objects under the S3 prefix, extracts year from each
 * filename, and returns a structured array sorted by set then round.
 */
export async function GET(): Promise<NextResponse> {
  try {
    const client = getS3Client();
    const entries: PdfEntry[] = [];
    let continuationToken: string | undefined;

    do {
      const command = new ListObjectsV2Command({
        Bucket: PDF_BUCKET,
        Prefix: PDF_PREFIX,
        ContinuationToken: continuationToken,
      });
      const response = await client.send(command);

      for (const obj of response.Contents ?? []) {
        if (!obj.Key) continue;
        const entry = parseKey(obj.Key);
        if (entry) entries.push(entry);
      }

      continuationToken = response.NextContinuationToken;
    } while (continuationToken);

    entries.sort((a, b) =>
      a.set.localeCompare(b.set) || a.round.localeCompare(b.round)
    );

    return NextResponse.json(entries);
  } catch (error) {
    console.error("[GET /api/pdf/list] S3 error:", error);
    return NextResponse.json(
      { message: "Failed to list PDFs" },
      { status: 500 }
    );
  }
}
