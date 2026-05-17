# Implementation Plan: BowlPrep Frontend

## Overview

Build the BowlPrep Next.js 14 (App Router) web application incrementally: start with project scaffolding and shared types, then the server-side data layer and API routes, then the UI components, and finally wire everything together into the practice page. Property-based tests (fast-check) are added alongside each logical unit they validate.

## Tasks

- [x] 1. Scaffold project structure and shared types
  - Initialize a Next.js 14 App Router project in `web/` with TypeScript and Tailwind CSS
  - Configure `tailwind.config.ts` with the BowlPrep design tokens: primary `#1a56db`, success `#10b981`, error `#ef4444`, surface `#faf8ff`, and Inter font
  - Create `web/lib/types.ts` defining `DynamoQuestion`, `QuestionResponse`, `SessionScore`, `PracticeFilter`, and `AnswerFormatFilter`
  - Create `web/jest.config.ts` and install Jest + React Testing Library + fast-check (exact versions pinned in `package.json`)
  - _Requirements: 6.5, 8.6_

- [x] 2. Implement the DynamoDB client factory and score utility
  - [x] 2.1 Create `web/lib/dynamo.ts` — server-only DynamoDB client factory using `fromIni({ profile: 'onasmmon' })` for local dev and the default credential chain in production
    - Export a single `getDynamoClient()` function (≤ 25 lines)
    - _Requirements: 2.6, 7.2_

  - [x] 2.2 Create `web/lib/score.ts` — `readScore()`, `writeScore()`, and `initScore()` functions that read/write `SessionScore` from `localStorage` under the key `bowlprep_session_score`; operations are no-ops when `localStorage` is unavailable
    - _Requirements: 5.1, 5.5_

  - [ ]* 2.3 Write property tests for `lib/score.ts`
    - **Property 8: Skip leaves SessionScore unchanged** — Validates: Requirements 4.6, 5.4
    - **Property 9: Correct answer increments both counts** — Validates: Requirements 5.2
    - **Property 10: Incorrect answer increments only total** — Validates: Requirements 5.3
    - **Property 11: SessionScore localStorage round-trip** — Validates: Requirements 5.5
    - Test file: `web/__tests__/properties/score.property.test.ts`
    - Use `fc.record({ correct: fc.nat(), total: fc.nat() })` arbitraries; `{ numRuns: 100 }`

- [x] 3. Implement the `/api/categories` route
  - [x] 3.1 Create `web/app/api/categories/route.ts`
    - `ScanCommand` with `ProjectionExpression: "Category"`, deduplicate with `Set`, sort alphabetically, return `NextResponse.json(categories)`
    - Return `{ status: 500 }` with a safe `message` on DynamoDB error; log error server-side
    - _Requirements: 7.1, 7.2, 7.3_

  - [ ]* 3.2 Write property tests for `/api/categories`
    - **Property 13: Categories API returns distinct values** — Validates: Requirements 7.1
    - Test file: `web/__tests__/properties/categoriesApi.property.test.ts`
    - Use `fc.array(fc.constantFrom(...sampleCategories))` with injected duplicates; mock DynamoDB client

- [x] 4. Implement the `/api/question` route
  - [x] 4.1 Create `web/app/api/question/route.ts`
    - Parse `category` and `format` query params; implement the six query-strategy branches from the design (Scan vs. GSI Query, with optional filter expressions)
    - Pick one item at random: `items[Math.floor(Math.random() * items.length)]`
    - Return 404 `{ message }` when result set is empty; return 500 `{ message }` on DynamoDB error
    - Strip `source_s3_key` before returning; include all eight required fields
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8_

  - [ ]* 4.2 Write property tests for `/api/question`
    - **Property 3: Random selection is always a member of the result set** — Validates: Requirements 2.1, 8.5
    - **Property 14: Question API response contains all required fields** — Validates: Requirements 8.6
    - Test file: `web/__tests__/properties/questionApi.property.test.ts`
    - Use `fc.array(fc.record({ Set_Round: fc.string(), Question_Id: fc.string(), ... }), { minLength: 1 })`; mock DynamoDB client

- [x] 5. Checkpoint — API layer complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement shared UI components
  - [x] 6.1 Create `web/components/ScoreDisplay.tsx`
    - Renders `"{correct} / {total}"` from `ScoreDisplayProps`; functional component, no class components
    - _Requirements: 5.6_

  - [ ]* 6.2 Write property tests for `ScoreDisplay`
    - **Property 12: Score display reflects current state** — Validates: Requirements 5.6
    - Test file: `web/__tests__/properties/scoreDisplay.property.test.ts`
    - Use `fc.record({ correct: fc.nat(), total: fc.nat() })`

  - [x] 6.3 Create `web/components/Nav.tsx`
    - Bottom bar on mobile (`< 768px`): icons for Practice, Stats (placeholder), Profile (placeholder)
    - Sticky top bar on desktop (`≥ 768px`): BowlPrep brand logo left, nav links (Practice active, Simulation placeholder, Stats placeholder) centered
    - Use Tailwind responsive prefixes (`md:`) only; no class components
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 6.4 Create `web/components/FilterBar.tsx`
    - Renders category `<select>` (options: "All Categories" + each category from props) and format `<select>` (All, Multiple Choice, Short Answer, TOSS-UP, BONUS)
    - Fires `onCategoryChange` / `onFormatChange` callbacks; shows error message + retry button when `isLoading` prop signals a fetch failure
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ]* 6.5 Write property tests for `FilterBar`
    - **Property 1: Category selector completeness** — Validates: Requirements 1.1
    - Test file: `web/__tests__/properties/filterBar.property.test.ts`
    - Use `fc.array(fc.string())` for categories array

  - [x] 6.6 Create `web/components/AnswerFeedback.tsx`
    - Shows success color (`#10b981`) + success message on correct; shows error color (`#ef4444`) + correct answer on incorrect
    - Renders "Next Question" button that calls `onNext`; falls back to plain-text indicator on render failure
    - _Requirements: 4.3, 4.4, 4.5_

  - [x] 6.7 Create `web/components/QuestionWorkspace.tsx`
    - Renders `question_stem`, `Category`, and `MatchType` metadata labels for every question
    - For `Multiple Choice`: renders four labeled clickable cards (W/X/Y/Z) with hover/active visual state; evaluates immediately on card click (no separate submit)
    - For `Short Answer`: renders auto-focused text input + Submit button; compares `input.trim().toLowerCase()` against `answer.trim().toLowerCase()`
    - Never renders both input types simultaneously; clears all answer state when `question` prop changes
    - Calls `onAnswerSubmit(isCorrect)` after evaluation
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2_

  - [ ]* 6.8 Write property tests for `QuestionWorkspace`
    - **Property 4: QuestionWorkspace renders all question data** — Validates: Requirements 3.1, 3.2, 3.3
    - **Property 5: Answer state is cleared on new question load** — Validates: Requirements 3.5
    - **Property 6: Short answer comparison is case- and whitespace-insensitive** — Validates: Requirements 4.2
    - **Property 7: Multiple choice evaluation is immediate** — Validates: Requirements 4.1
    - Test file: `web/__tests__/properties/questionWorkspace.property.test.ts`

- [x] 7. Checkpoint — Components complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement the root layout and practice page
  - [x] 8.1 Create `web/app/layout.tsx`
    - Root layout: apply Inter font, surface background (`#faf8ff`), render `<Nav />`, apply 16px horizontal margin on mobile and 40px on desktop
    - _Requirements: 6.4, 6.5_

  - [x] 8.2 Create `web/app/page.tsx`
    - Redirects to `/practice` using `next/navigation` `redirect()`
    - _Requirements: (routing)_

  - [x] 8.3 Create `web/app/practice/page.tsx` — Client Component (`"use client"`)
    - On mount: call `GET /api/categories`, populate `FilterBar`; read `SessionScore` from `localStorage` via `lib/score.ts`
    - On filter change: update `PracticeFilter` state; fetch next question via `GET /api/question?category=&format=`
    - On answer submit: evaluate correctness, update `SessionScore` via `lib/score.ts`, show `AnswerFeedback`
    - On "Next Question": fetch new question with current `PracticeFilter`
    - On "Skip": abort any in-flight fetch via `AbortController`, fetch new question, leave `SessionScore` unchanged
    - Show "No questions found" message on 404; show error + retry on 500
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 4.5, 4.6, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ]* 8.4 Write property tests for the practice page filter-to-fetch URL propagation
    - **Property 2: Filter parameters propagate to fetch URL** — Validates: Requirements 1.3
    - Test file: `web/__tests__/properties/practicePage.property.test.ts`
    - Use `fc.record({ category: fc.string(), format: fc.constantFrom('All', 'Multiple Choice', 'Short Answer', 'TOSS-UP', 'BONUS') })`

- [x] 9. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- All DynamoDB access is strictly server-side; no AWS credentials or SDK calls in browser-executed code
- Property tests use `fast-check` with `{ numRuns: 100 }` minimum; located in `web/__tests__/properties/`
- Unit tests use Jest + React Testing Library; located in `web/__tests__/`
- AWS profile `onasmmon` is used for local DynamoDB access; IAM role is used in production

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["2.1", "2.2"] },
    { "id": 1, "tasks": ["2.3", "3.1"] },
    { "id": 2, "tasks": ["3.2", "4.1"] },
    { "id": 3, "tasks": ["4.2", "6.1", "6.3", "6.4", "6.6", "6.7"] },
    { "id": 4, "tasks": ["6.2", "6.5", "6.8"] },
    { "id": 5, "tasks": ["8.1", "8.2", "8.3"] },
    { "id": 6, "tasks": ["8.4"] }
  ]
}
```
