# Requirements Document

## Introduction

BowlPrep is a responsive web application that enables students to practice Science Bowl questions. The app reads questions from an existing DynamoDB table (`ScienceBowlQuestions`) and presents them in an interactive practice interface. Students can filter questions by category and answer format, receive immediate feedback on their answers, and track their session score. The application is built with Next.js 14 (App Router), TypeScript, and Tailwind CSS, with all DynamoDB access handled server-side via Next.js API routes.

## Glossary

- **App**: The BowlPrep Next.js web application.
- **API_Route**: A Next.js server-side API route handler that communicates with DynamoDB.
- **Question**: A Science Bowl question record stored in the `ScienceBowlQuestions` DynamoDB table.
- **Category**: A subject area attribute on a Question (e.g., Biology, Chemistry, Physics).
- **MatchType**: The competition role of a Question — either `TOSS-UP` or `BONUS`.
- **AnswerFormat**: The response type of a Question — either `Multiple Choice` or `Short Answer`.
- **QuestionWorkspace**: The UI region that displays the current Question and collects the student's answer.
- **AnswerFeedback**: The visual response shown after a student submits an answer, indicating correctness.
- **SessionScore**: An in-memory tally of correct and total answered questions for the current browser session, persisted to `localStorage`.
- **PracticeFilter**: The combination of Category and AnswerFormat selections used to fetch a Question.
- **Nav**: The navigation component — bottom bar on mobile, top bar on desktop.
- **DynamoDB_Client**: The AWS SDK v3 DynamoDB client used exclusively in server-side API routes.

---

## Requirements

### Requirement 1: Category and Format Filter Selection

**User Story:** As a student, I want to select a subject category and answer format before practicing, so that I can focus my study on specific topics or question types.

#### Acceptance Criteria

1. WHEN the App loads the practice page, THE App SHALL display a category selector populated with all distinct categories fetched from the `GET /api/categories` API route plus an "All Categories" option.
2. WHEN the App loads the practice page, THE App SHALL display an answer format selector with the options: All, Multiple Choice, Short Answer, TOSS-UP, and BONUS.
3. WHEN a student selects a category and answer format, THE App SHALL use those selections as the PracticeFilter for the next question fetch.
4. IF the `GET /api/categories` request fails, THEN THE App SHALL display an error message and present a retry button that re-issues the request; the retry option SHALL always be available regardless of the failure type.

---

### Requirement 2: Question Fetching via API Routes

**User Story:** As a student, I want the app to serve me a random question matching my filter, so that I get varied practice without manual browsing.

#### Acceptance Criteria

1. WHEN a student requests a new question, THE API_Route SHALL query DynamoDB using the active PracticeFilter and return one randomly selected matching Question.
2. WHEN the category filter is "All Categories", THE API_Route SHALL query across all categories without a category constraint.
3. WHEN the answer format filter is "All", THE API_Route SHALL return questions of any AnswerFormat and MatchType.
4. WHEN the answer format filter is "Multiple Choice" or "Short Answer", THE API_Route SHALL filter by the `answer_format` attribute.
5. WHEN the answer format filter is "TOSS-UP" or "BONUS", THE API_Route SHALL filter by the `MatchType` attribute.
6. THE API_Route SHALL access DynamoDB exclusively server-side using the DynamoDB_Client; no AWS credentials or SDK calls SHALL appear in browser-executed code.
7. IF no questions match the active PracticeFilter, THEN THE API_Route SHALL return a 404 response with a descriptive message.
8. IF the DynamoDB query fails, THEN THE API_Route SHALL return a 500 response with a descriptive error message regardless of any previously cached results.

---

### Requirement 3: Question Display in the QuestionWorkspace

**User Story:** As a student, I want to see the question clearly with appropriately formatted answer inputs, so that I can read and respond to it efficiently.

#### Acceptance Criteria

1. WHEN a Question with `answer_format` of `Multiple Choice` is displayed, THE QuestionWorkspace SHALL render the `question_stem` and each entry in `answer_choices` as a labeled, clickable card (W, X, Y, Z).
2. WHEN a Question with `answer_format` of `Short Answer` is displayed, THE QuestionWorkspace SHALL render the `question_stem` and an auto-focused text input with a Submit button.
3. THE QuestionWorkspace SHALL display the Question's `Category` and `MatchType` as metadata labels; THE QuestionWorkspace SHALL render only the answer input appropriate for the Question's `answer_format` — Multiple Choice cards for `Multiple Choice` questions and a text input for `Short Answer` questions — never both simultaneously.
4. WHEN a Multiple Choice answer card receives hover or active interaction, THE QuestionWorkspace SHALL apply a distinct visual state to that card.
5. WHEN a new Question is loaded, THE QuestionWorkspace SHALL clear any previous answer input or selection state.

---

### Requirement 4: Answer Submission and Feedback

**User Story:** As a student, I want immediate feedback on my answer, so that I can learn from both correct and incorrect responses.

#### Acceptance Criteria

1. WHEN a student selects a Multiple Choice option, THE App SHALL immediately evaluate the selection against the stored `answer` without requiring a separate submit action.
2. WHEN a student submits a Short Answer, THE App SHALL compare the trimmed, lowercased input against the trimmed, lowercased stored `answer`.
3. WHEN the submitted answer is correct, THE AnswerFeedback SHALL highlight the selected option or input in the success color (`#10b981`) and display a success message; IF the feedback display fails, THEN THE App SHALL fall back to a plain-text success indicator.
4. WHEN the submitted answer is incorrect, THE AnswerFeedback SHALL highlight the selected option or input in the error color (`#ef4444`) and display the correct answer; IF the feedback display fails, THEN THE App SHALL fall back to a plain-text error indicator showing the correct answer.
5. WHEN AnswerFeedback is shown, THE App SHALL display a "Next Question" button that fetches a new question using the current PracticeFilter.
6. WHEN a student clicks "Skip", THE App SHALL fetch a new question using the current PracticeFilter without recording the skipped question in the SessionScore; IF a student clicks "Skip" while an answer submission is still being processed, THE App SHALL treat the interaction as a skip and discard the in-flight submission.

---

### Requirement 5: Session Score Tracking

**User Story:** As a student, I want to see my running score for the current session, so that I can gauge my performance.

#### Acceptance Criteria

1. THE App SHALL maintain a SessionScore consisting of a correct-answer count and a total-answered count.
2. WHEN a student submits a correct answer, THE App SHALL increment both the correct count and the total count of the SessionScore.
3. WHEN a student submits an incorrect answer, THE App SHALL increment only the total count of the SessionScore.
4. WHEN a student skips a question, THE App SHALL leave the SessionScore unchanged.
5. THE App SHALL persist the SessionScore to `localStorage` so that it survives page refreshes within the same browser session.
6. THE App SHALL display the current SessionScore (e.g., "7 / 10") in the UI at all times during practice.

---

### Requirement 6: Responsive Layout and Navigation

**User Story:** As a student, I want the app to work well on both my phone and my laptop, so that I can practice anywhere.

#### Acceptance Criteria

1. WHILE the viewport width is less than 768px, THE App SHALL render a single-column layout with a bottom Nav containing icons for Practice, Stats (placeholder), and Profile (placeholder).
2. WHILE the viewport width is 768px or greater, THE App SHALL render a top Nav bar with the BowlPrep brand logo on the left and nav links (Practice active, Simulation placeholder, Stats placeholder) centered; a viewport width of exactly 768px SHALL use the desktop layout.
3. WHILE the viewport width is 768px or greater, THE Nav SHALL remain sticky at the top of the viewport during scroll.
4. THE App SHALL apply a 16px horizontal margin on mobile viewports and a 40px horizontal margin on desktop viewports.
5. THE App SHALL use the BowlPrep design tokens: primary color `#1a56db`, success `#10b981`, error `#ef4444`, surface `#faf8ff`, and Inter font for UI text.

---

### Requirement 7: API Route — Categories Endpoint

**User Story:** As a developer, I want a dedicated API route that returns all available categories, so that the frontend can populate the category selector without embedding data-access logic in components.

#### Acceptance Criteria

1. THE API_Route at `GET /api/categories` SHALL return a JSON array of distinct category strings derived from the `ScienceBowlQuestions` DynamoDB table.
2. THE API_Route SHALL use the DynamoDB_Client with the `onasmmon` AWS profile when running locally and an IAM role in production.
3. IF the DynamoDB scan for categories fails, THEN THE API_Route SHALL return a 500 response with a descriptive error message.

---

### Requirement 8: API Route — Question Endpoint

**User Story:** As a developer, I want a dedicated API route that returns a single random question matching the given filters, so that the frontend can fetch questions without embedding data-access logic in components.

#### Acceptance Criteria

1. THE API_Route at `GET /api/question` SHALL accept optional query parameters `category` and `format`.
2. WHEN `category` is provided and is not "All Categories", THE API_Route SHALL use the `GSI_Category_MatchType` GSI to query by `Category`.
3. WHEN `format` corresponds to `MatchType` ("TOSS-UP" or "BONUS"), THE API_Route SHALL include a `MatchType` condition in the DynamoDB query.
4. WHEN `format` corresponds to `AnswerFormat` ("Multiple Choice" or "Short Answer"), THE API_Route SHALL apply a filter expression on the `answer_format` attribute.
5. THE API_Route SHALL select one item at random from the result set and return it as a JSON object.
6. THE API_Route SHALL return a response containing: `Set_Round`, `Question_Id`, `Category`, `MatchType`, `question_stem`, `answer_choices`, `answer`, and `answer_format`.
7. IF no matching questions are found, THEN THE API_Route SHALL return a 404 JSON response with a `message` field.
8. IF the DynamoDB operation fails, THEN THE API_Route SHALL return a 500 JSON response with a `message` field regardless of whether questions would otherwise have been found.
