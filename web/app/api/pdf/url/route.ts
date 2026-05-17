import { NextResponse } from "next/server";
import { GetObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

import { getS3Client, PDF_BUCKET, PDF_PREFIX } from "@/lib/s3";

/** Pre-signed URL TTL in seconds (15 minutes). */
const URL_TTL_SECONDS = 900;

/**
 * GET /api/pdf/url?key={s3Key}&disposition=inline|attachment
 *
 * Generates a pre-signed S3 URL for the given key.
 * - disposition=inline  → for in-browser viewing (default)
 * - disposition=attachment → for download (sets Content-Disposition header)
 *
 * Returns { url: string }.
 */
export async function GET(request: Request): Promise<NextResponse> {
  const { searchParams } = new URL(request.url);
  const key = searchParams.get("key") ?? "";
  const disposition = searchParams.get("disposition") === "attachment"
    ? "attachment"
    : "inline";

  if (!key) {
    return NextResponse.json({ message: "Missing key parameter" }, { status: 400 });
  }

  // Validate the key is within the expected prefix to prevent path traversal
  if (!key.startsWith(PDF_PREFIX) || !key.endsWith(".pdf")) {
    return NextResponse.json({ message: "Invalid key" }, { status: 400 });
  }

  try {
    const client = getS3Client();
    const filename = key.split("/").pop() ?? "document.pdf";

    const command = new GetObjectCommand({
      Bucket: PDF_BUCKET,
      Key: key,
      ResponseContentDisposition: `${disposition}; filename="${filename}"`,
      ResponseContentType: "application/pdf",
    });

    const url = await getSignedUrl(client, command, { expiresIn: URL_TTL_SECONDS });
    return NextResponse.json({ url });
  } catch (error) {
    console.error("[GET /api/pdf/url] S3 error:", error);
    return NextResponse.json(
      { message: "Failed to generate URL" },
      { status: 500 }
    );
  }
}
