"use client";

import katex from "katex";
import "katex/dist/katex.min.css";

/**
 * Splits a string on LaTeX delimiters into alternating plain/math segments.
 *
 * Supports:
 *   - Block math:  $$...$$ → rendered as display math
 *   - Inline math: $...$   → rendered as inline math
 *
 * Returns an array of segments, each tagged as "text" or "math".
 */
interface TextSegment { type: "text"; value: string }
interface MathSegment { type: "math"; value: string; display: boolean }
type Segment = TextSegment | MathSegment;

/** Regex that matches $$...$$ (display) or $...$ (inline) LaTeX delimiters. */
const MATH_RE = /(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)/g;

function parseSegments(text: string): Segment[] {
  const segments: Segment[] = [];
  let lastIndex = 0;

  const matches = Array.from(text.matchAll(MATH_RE));
  for (const match of matches) {
    const start = match.index ?? 0;
    if (start > lastIndex) {
      segments.push({ type: "text", value: text.slice(lastIndex, start) });
    }
    const raw = match[0];
    const isDisplay = raw.startsWith("$$");
    const inner = isDisplay ? raw.slice(2, -2) : raw.slice(1, -1);
    segments.push({ type: "math", value: inner, display: isDisplay });
    lastIndex = start + raw.length;
  }

  if (lastIndex < text.length) {
    segments.push({ type: "text", value: text.slice(lastIndex) });
  }

  return segments;
}

/** Renders a single LaTeX math segment using KaTeX. Falls back to raw text on error. */
function MathSegment({ value, display }: { value: string; display: boolean }) {
  try {
    const html = katex.renderToString(value, {
      displayMode: display,
      throwOnError: false,
      strict: false,
    });
    return (
      <span
        className={display ? "block my-2" : "inline"}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    );
  } catch {
    // Fallback: show the raw delimited string rather than crashing
    return <span>{display ? `$$${value}$$` : `$${value}$`}</span>;
  }
}

/** Props for MathText. */
interface MathTextProps {
  /** The string to render — may contain $...$ or $$...$$ LaTeX delimiters. */
  text: string;
  /** Optional extra className applied to the wrapper span. */
  className?: string;
}

/**
 * Renders a mixed plain-text / LaTeX string.
 *
 * Plain text segments are rendered as-is. Segments wrapped in `$...$` are
 * rendered as inline KaTeX math. Segments wrapped in `$$...$$` are rendered
 * as display (block) KaTeX math. Falls back to raw text if KaTeX throws.
 */
export default function MathText({ text, className }: MathTextProps) {
  const segments = parseSegments(text);

  return (
    <span className={className}>
      {segments.map((seg, i) =>
        seg.type === "text" ? (
          <span key={i}>{seg.value}</span>
        ) : (
          <MathSegment key={i} value={seg.value} display={seg.display} />
        )
      )}
    </span>
  );
}

/**
 * Strips LaTeX delimiters and normalises whitespace for answer comparison.
 * Handles both delimited LaTeX ($\pi$) and raw LaTeX commands (\pi)
 * typed by the user in the short answer input.
 */
export function normalizeForComparison(s: string): string {
  return s
    .replace(/\$\$[\s\S]+?\$\$/g, (m) => m.slice(2, -2))  // strip $$ delimiters
    .replace(/\$[^$\n]+?\$/g, (m) => m.slice(1, -1))       // strip $ delimiters
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}
