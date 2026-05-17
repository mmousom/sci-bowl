"use client";

import { useEffect, useMemo, useState } from "react";
import type { PdfEntry } from "@/app/api/pdf/list/route";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ListState =
  | { status: "loading" }
  | { status: "loaded"; entries: PdfEntry[] }
  | { status: "error" };

type ViewerState =
  | { status: "closed" }
  | { status: "loading"; entry: PdfEntry }
  | { status: "open"; entry: PdfEntry; url: string }
  | { status: "error"; entry: PdfEntry };

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ALL = "All";

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/** Fetches the full PDF list on mount. */
function usePdfList(): { state: ListState; retry: () => void } {
  const [state, setState] = useState<ListState>({ status: "loading" });

  const load = async () => {
    setState({ status: "loading" });
    try {
      const res = await fetch("/api/pdf/list");
      if (!res.ok) throw new Error("list fetch failed");
      const entries = (await res.json()) as PdfEntry[];
      setState({ status: "loaded", entries });
    } catch {
      setState({ status: "error" });
    }
  };

  useEffect(() => { load(); }, []);
  return { state, retry: load };
}

/** Fetches a pre-signed URL for a given S3 key and disposition. */
async function fetchPresignedUrl(
  key: string,
  disposition: "inline" | "attachment"
): Promise<string> {
  const params = new URLSearchParams({ key, disposition });
  const res = await fetch(`/api/pdf/url?${params}`);
  if (!res.ok) throw new Error("url fetch failed");
  const { url } = (await res.json()) as { url: string };
  return url;
}

// ---------------------------------------------------------------------------
// Filter helpers
// ---------------------------------------------------------------------------

/** Extracts sorted unique years from entries; null years are excluded. */
function extractYears(entries: PdfEntry[]): number[] {
  return Array.from(
    new Set(entries.map((e) => e.year).filter((y): y is number => y !== null))
  ).sort((a, b) => a - b);
}

/** Extracts sorted unique set names from entries. */
function extractSets(entries: PdfEntry[]): string[] {
  return Array.from(new Set(entries.map((e) => e.set))).sort();
}

/** Applies year and set filters to the entry list. */
function applyFilters(
  entries: PdfEntry[],
  year: string,
  set: string
): PdfEntry[] {
  return entries.filter((e) => {
    const yearMatch = year === ALL || String(e.year) === year;
    const setMatch = set === ALL || e.set === set;
    return yearMatch && setMatch;
  });
}

/** Groups a flat entry list by set name. */
function groupBySet(entries: PdfEntry[]): Map<string, PdfEntry[]> {
  const map = new Map<string, PdfEntry[]>();
  for (const e of entries) {
    const existing = map.get(e.set) ?? [];
    existing.push(e);
    map.set(e.set, existing);
  }
  return map;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Year filter pill buttons. */
function YearFilter({
  years,
  selected,
  onChange,
}: {
  years: number[];
  selected: string;
  onChange: (y: string) => void;
}) {
  const pillClass = (active: boolean) =>
    [
      "rounded-full px-3 py-1 text-sm font-medium transition-colors",
      active
        ? "bg-primary text-white"
        : "bg-white dark:bg-white/10 border border-gray-300 dark:border-white/20 text-gray-700 dark:text-gray-300 hover:border-primary hover:text-primary",
    ].join(" ");

  return (
    <div className="flex flex-wrap gap-2">
      <button className={pillClass(selected === ALL)} onClick={() => onChange(ALL)}>
        All Years
      </button>
      {years.map((y) => (
        <button
          key={y}
          className={pillClass(selected === String(y))}
          onClick={() => onChange(String(y))}
        >
          {y}
        </button>
      ))}
      <button
        className={pillClass(selected === "other")}
        onClick={() => onChange("other")}
      >
        Other
      </button>
    </div>
  );
}

/** Set dropdown filter. */
function SetFilter({
  sets,
  selected,
  onChange,
}: {
  sets: string[];
  selected: string;
  onChange: (s: string) => void;
}) {
  return (
    <select
      aria-label="Filter by set"
      value={selected}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-md border border-gray-300 dark:border-white/20 bg-white dark:bg-white/10 px-3 py-2 text-sm text-gray-800 dark:text-gray-100 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
    >
      <option value={ALL}>All Sets</option>
      {sets.map((s) => (
        <option key={s} value={s}>
          {s}
        </option>
      ))}
    </select>
  );
}

/** A single PDF row with View and Download buttons. */
function PdfRow({
  entry,
  onView,
  onDownload,
}: {
  entry: PdfEntry;
  onView: (entry: PdfEntry) => void;
  onDownload: (entry: PdfEntry) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 px-4 py-3">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-gray-800 dark:text-gray-100">
          {entry.round}
        </p>
        {entry.year && (
          <p className="text-xs text-gray-500 dark:text-gray-400">{entry.year}</p>
        )}
      </div>
      <div className="flex shrink-0 gap-2">
        <button
          onClick={() => onView(entry)}
          className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 transition-opacity"
        >
          View
        </button>
        <button
          onClick={() => onDownload(entry)}
          className="rounded-md border border-gray-300 dark:border-white/20 px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-300 hover:border-primary hover:text-primary transition-colors"
        >
          ↓ PDF
        </button>
      </div>
    </div>
  );
}

/** Grouped list of PDF rows under a set heading. */
function SetGroup({
  set,
  entries,
  onView,
  onDownload,
}: {
  set: string;
  entries: PdfEntry[];
  onView: (entry: PdfEntry) => void;
  onDownload: (entry: PdfEntry) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold text-primary dark:text-blue-300 uppercase tracking-wide">
        {set}
      </h2>
      {entries.map((e) => (
        <PdfRow key={e.key} entry={e} onView={onView} onDownload={onDownload} />
      ))}
    </div>
  );
}

/** Inline PDF viewer modal. */
function PdfViewerModal({
  state,
  onClose,
}: {
  state: ViewerState;
  onClose: () => void;
}) {
  if (state.status === "closed") return null;

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col bg-black/70"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="flex items-center justify-between bg-gray-900 px-4 py-2">
        <span className="truncate text-sm font-medium text-white">
          {"entry" in state ? state.entry.round : ""}
        </span>
        <button
          onClick={onClose}
          className="ml-4 shrink-0 rounded-md px-3 py-1 text-sm text-gray-300 hover:text-white transition-colors"
        >
          ✕ Close
        </button>
      </div>

      <div className="flex-1 overflow-hidden">
        {state.status === "loading" && (
          <div className="flex h-full items-center justify-center">
            <span className="text-sm text-gray-400">Loading PDF…</span>
          </div>
        )}
        {state.status === "error" && (
          <div className="flex h-full items-center justify-center">
            <span className="text-sm text-red-400">Failed to load PDF.</span>
          </div>
        )}
        {state.status === "open" && (
          <iframe
            src={state.url}
            className="h-full w-full border-0"
            title={state.entry.round}
          />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

/**
 * Simulation page — PDF browser.
 * Lists all PDFs from S3, supports year and set filtering,
 * inline viewing via pre-signed URL, and direct download.
 */
export default function SimulationPage() {
  const { state: listState, retry } = usePdfList();
  const [yearFilter, setYearFilter] = useState<string>(ALL);
  const [setFilter, setSetFilter] = useState<string>(ALL);
  const [viewer, setViewer] = useState<ViewerState>({ status: "closed" });

  const entries = listState.status === "loaded" ? listState.entries : [];
  const years = useMemo(() => extractYears(entries), [entries]);
  const sets = useMemo(() => extractSets(entries), [entries]);

  const filtered = useMemo(() => {
    if (yearFilter === "other") {
      const withYear = entries.filter((e) => e.year !== null);
      const knownYears = new Set(withYear.map((e) => String(e.year)));
      return entries.filter(
        (e) => e.year === null || !knownYears.has(String(e.year))
      );
    }
    return applyFilters(entries, yearFilter, setFilter);
  }, [entries, yearFilter, setFilter]);

  const grouped = useMemo(() => groupBySet(filtered), [filtered]);

  const handleView = async (entry: PdfEntry) => {
    setViewer({ status: "loading", entry });
    try {
      const url = await fetchPresignedUrl(entry.key, "inline");
      setViewer({ status: "open", entry, url });
    } catch {
      setViewer({ status: "error", entry });
    }
  };

  const handleDownload = async (entry: PdfEntry) => {
    try {
      const url = await fetchPresignedUrl(entry.key, "attachment");
      const a = document.createElement("a");
      a.href = url;
      a.download = `${entry.round}.pdf`;
      a.click();
    } catch {
      alert("Failed to generate download link. Please try again.");
    }
  };

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 py-6">
      <div>
        <h1 className="text-xl font-semibold text-primary">Browse PDFs</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          View or download original Science Bowl round PDFs.
        </p>
      </div>

      {/* Loading / error states */}
      {listState.status === "loading" && (
        <p className="text-sm text-gray-500 dark:text-gray-400">Loading PDF list…</p>
      )}
      {listState.status === "error" && (
        <div className="flex items-center gap-3 rounded-lg border border-error bg-red-50 dark:bg-red-900/20 px-4 py-3 text-sm text-error">
          <span>Failed to load PDF list.</span>
          <button
            onClick={retry}
            className="rounded-md bg-error px-3 py-1 text-sm font-medium text-white hover:bg-red-600"
          >
            Retry
          </button>
        </div>
      )}

      {listState.status === "loaded" && (
        <>
          {/* Filters */}
          <div className="flex flex-col gap-3">
            <YearFilter years={years} selected={yearFilter} onChange={setYearFilter} />
            <SetFilter sets={sets} selected={setFilter} onChange={setSetFilter} />
          </div>

          {/* Result count */}
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {filtered.length} PDF{filtered.length !== 1 ? "s" : ""} found
          </p>

          {/* Grouped results */}
          {filtered.length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              No PDFs match the selected filters.
            </p>
          ) : (
            <div className="flex flex-col gap-6">
              {Array.from(grouped.entries()).map(([set, setEntries]) => (
                <SetGroup
                  key={set}
                  set={set}
                  entries={setEntries}
                  onView={handleView}
                  onDownload={handleDownload}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* PDF viewer modal */}
      <PdfViewerModal state={viewer} onClose={() => setViewer({ status: "closed" })} />
    </div>
  );
}
