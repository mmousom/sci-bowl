"use client";

import { AnswerFormatFilter } from "@/lib/types";

/** Format options available in the practice UI. */
const FORMAT_OPTIONS: AnswerFormatFilter[] = [
  "All",
  "Multiple Choice",
  "Short Answer",
  "TOSS-UP",
  "BONUS",
];

const ALL_ROUNDS = "All Rounds";

/** Props for the FilterBar component. */
interface FilterBarProps {
  categories: string[];
  rounds: string[];
  selectedCategory: string;
  selectedFormat: AnswerFormatFilter;
  selectedRound: string;
  onCategoryChange: (category: string) => void;
  onFormatChange: (format: AnswerFormatFilter) => void;
  onRoundChange: (round: string) => void;
  isLoading: boolean;
}

/**
 * Renders category, answer-format, and set/round selectors for the practice page.
 * Shows an error message with a retry button when `isLoading` signals a fetch failure.
 */
export default function FilterBar({
  categories,
  rounds,
  selectedCategory,
  selectedFormat,
  selectedRound,
  onCategoryChange,
  onFormatChange,
  onRoundChange,
  isLoading,
}: FilterBarProps) {
  if (isLoading) {
    return <FilterError onRetry={() => onCategoryChange(selectedCategory)} />;
  }

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
      <CategorySelect
        categories={categories}
        selectedCategory={selectedCategory}
        onChange={onCategoryChange}
      />
      <FormatSelect selectedFormat={selectedFormat} onChange={onFormatChange} />
      <RoundSelect
        rounds={rounds}
        selectedRound={selectedRound}
        onChange={onRoundChange}
      />
    </div>
  );
}

/** Props for the CategorySelect sub-component. */
interface CategorySelectProps {
  categories: string[];
  selectedCategory: string;
  onChange: (category: string) => void;
}

/**
 * Renders the category `<select>` with "All Categories" as the first option.
 */
function CategorySelect({ categories, selectedCategory, onChange }: CategorySelectProps) {
  return (
    <select
      aria-label="Category"
      value={selectedCategory}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-md border border-gray-300 dark:border-white/20 bg-surface dark:bg-white/10 px-3 py-2 text-sm text-gray-800 dark:text-gray-100 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
    >
      <option value="All Categories">All Categories</option>
      {categories.map((cat) => (
        <option key={cat} value={cat}>
          {cat}
        </option>
      ))}
    </select>
  );
}

/** Props for the FormatSelect sub-component. */
interface FormatSelectProps {
  selectedFormat: AnswerFormatFilter;
  onChange: (format: AnswerFormatFilter) => void;
}

/**
 * Renders the answer-format `<select>` with all valid format options.
 */
function FormatSelect({ selectedFormat, onChange }: FormatSelectProps) {
  return (
    <select
      aria-label="Answer format"
      value={selectedFormat}
      onChange={(e) => onChange(e.target.value as AnswerFormatFilter)}
      className="rounded-md border border-gray-300 dark:border-white/20 bg-surface dark:bg-white/10 px-3 py-2 text-sm text-gray-800 dark:text-gray-100 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
    >
      {FORMAT_OPTIONS.map((fmt) => (
        <option key={fmt} value={fmt}>
          {fmt}
        </option>
      ))}
    </select>
  );
}

/** Props for the RoundSelect sub-component. */
interface RoundSelectProps {
  rounds: string[];
  selectedRound: string;
  onChange: (round: string) => void;
}

/**
 * Groups Set_Round values by their set prefix (the part before the first `_`)
 * and renders them as `<optgroup>` sections inside a `<select>`.
 */
function RoundSelect({ rounds, selectedRound, onChange }: RoundSelectProps) {
  const groups = groupRoundsBySet(rounds);

  return (
    <select
      aria-label="Set / Round"
      value={selectedRound}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-md border border-gray-300 dark:border-white/20 bg-surface dark:bg-white/10 px-3 py-2 text-sm text-gray-800 dark:text-gray-100 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
    >
      <option value={ALL_ROUNDS}>{ALL_ROUNDS}</option>
      {groups.map(({ set, rounds: setRounds }) => (
        <optgroup key={set} label={set}>
          {setRounds.map((r) => (
            <option key={r} value={r}>
              {roundLabel(r)}
            </option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}

/** Extracts the set prefix from a Set_Round value (part before the first `_`). */
function setPrefix(setRound: string): string {
  const idx = setRound.indexOf("_");
  return idx === -1 ? setRound : setRound.slice(0, idx);
}

/** Returns a short display label for a Set_Round value (part after the first `_`). */
function roundLabel(setRound: string): string {
  const idx = setRound.indexOf("_");
  return idx === -1 ? setRound : setRound.slice(idx + 1);
}

interface RoundGroup {
  set: string;
  rounds: string[];
}

/** Groups a flat list of Set_Round strings by their set prefix. */
function groupRoundsBySet(rounds: string[]): RoundGroup[] {
  const map = new Map<string, string[]>();
  for (const r of rounds) {
    const key = setPrefix(r);
    const existing = map.get(key) ?? [];
    existing.push(r);
    map.set(key, existing);
  }
  return Array.from(map.entries()).map(([set, rs]) => ({ set, rounds: rs }));
}

/** Props for the FilterError sub-component. */
interface FilterErrorProps {
  onRetry: () => void;
}

/**
 * Shown when the categories fetch fails; provides a retry button.
 */
function FilterError({ onRetry }: FilterErrorProps) {
  return (
    <div className="flex items-center gap-3 rounded-md border border-error bg-red-50 px-4 py-3 text-sm text-error">
      <span>Failed to load filters.</span>
      <button
        onClick={onRetry}
        className="rounded-md bg-error px-3 py-1 text-sm font-medium text-white hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-error focus:ring-offset-1"
      >
        Retry
      </button>
    </div>
  );
}
