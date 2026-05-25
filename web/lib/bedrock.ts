import "server-only";

import { BedrockRuntimeClient } from "@aws-sdk/client-bedrock-runtime";
import { fromIni } from "@aws-sdk/credential-providers";

const REGION = process.env.AWS_REGION ?? "us-east-1";

/**
 * Returns a BedrockRuntimeClient configured for the current environment.
 *
 * - When AWS_PROFILE is set (local dev): uses the named profile via fromIni.
 * - Otherwise (production with IAM role): uses the default credential chain.
 */
export function getBedrockClient(): BedrockRuntimeClient {
  const profile = process.env.AWS_PROFILE;

  return profile
    ? new BedrockRuntimeClient({
        region: REGION,
        credentials: fromIni({ profile }),
      })
    : new BedrockRuntimeClient({ region: REGION });
}
