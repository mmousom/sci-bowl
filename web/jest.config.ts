import type { Config } from "jest";
import nextJest from "next/jest.js";

const createJestConfig = nextJest({
  /** Path to the Next.js app — loads next.config.js and .env files. */
  dir: "./",
});

/** Jest configuration for BowlPrep frontend. */
const config: Config = {
  coverageProvider: "v8",
  testEnvironment: "jsdom",
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/$1",
  },
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
};

export default createJestConfig(config);
