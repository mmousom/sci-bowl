# Implementation Plan: sci-bowl-pdf-etl

## Overview

Implement the two-Lambda ETL pipeline that extracts Science Bowl questions from S3 PDFs and loads them into DynamoDB. The build proceeds bottom-up: shared utilities first, then the Worker Lambda stages, then the Orchestrator Lambda, and finally the SAM template and smoke-test script. Property-based tests (Hypothesis) are placed immediately after the code they validate so regressions are caught early.

---

## Tasks

- [x] 1. Scaffold project structure and pin dependencies
  - Create `src/orchestrator/`, `src/worker/`, and `tests/unit/` directories with `__init__.py` files
  - Write `requirements.txt` with pinned versions: `pdfplumber`, `boto3`, `hypothesis==6.112.2`, `pytest==8.3.3`, `pytest-mock==3.14.0`, `moto==5.0.16`
  - Add a `pytest.ini` (or `pyproject.toml` `[tool.pytest.ini_options]`) that sets `testpaths = tests/unit`
  - _Requirements: 2.4 (reserved concurrency), 3.1 (pdfplumber dependency)_

- [x] 2. Implement `pdf_extractor.py`
  - [x] 2.1 Write `src/worker/pdf_extractor.py`
    - Implement `downloadPdf(s3Client, bucket: str, key: str) -> bytes` — calls `get_object`, returns `Body.read()`; logs key + error and re-raises on failure
    - Implement `extractText(pdfBytes: bytes) -> str` — opens PDF with `pdfplumber.open(io.BytesIO(pdfBytes))`, iterates pages, treats `None`/empty as `""`, concatenates in page order; logs key + error and re-raises on pdfplumber exception
    - All public functions must have docstrings and full type hints
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ]* 2.2 Write property test for `extractText` page concatenation
    - **Property 3: Page Text Concatenation**
    - **Validates: Requirements 3.2**
    - File: `tests/unit/test_pdf_extractor.py`
    - Use `@given(st.lists(st.one_of(st.none(), st.text())))` to verify concatenation order and `None`-as-empty behaviour

  - [ ]* 2.3 Write unit tests for `pdf_extractor.py`
    - Mock `pdfplumber.open` and `s3Client.get_object`; test None pages, empty pages, multi-page concatenation, S3 failure propagation
    - _Requirements: 3.1, 3.2, 3.3_

- [x] 3. Implement `chunker.py`
  - [x] 3.1 Write `src/worker/chunker.py`
    - Implement `chunkQuestions(text: str) -> list[str]` using `re.split(r'(?m)^(?=TOSS-UP|BONUS)', text)`
    - Filter out empty/whitespace-only leading segments
    - Raise `ValueError` (with log) when non-empty text produces zero chunks
    - Full type hints and docstring
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 3.2 Write property test for chunker partitioning
    - **Property 6: Chunker Partitions Text Correctly**
    - **Validates: Requirements 5.1, 5.4**
    - Use `@given(st.lists(st.text(min_size=1), min_size=1))` — prepend `TOSS-UP\n` or `BONUS\n` to each block, concatenate, assert `len(chunks) == N` and `"".join(chunks) == original`

  - [ ]* 3.3 Write property test for non-empty input producing at least one chunk
    - **Property 7: Non-Empty Input Produces At Least One Chunk**
    - **Validates: Requirements 5.2**
    - Use `@given(st.text())` filtered to contain at least one `TOSS-UP`/`BONUS` line; assert `len(chunkQuestions(text)) >= 1`

  - [ ]* 3.4 Write unit tests for `chunker.py`
    - Cover: New Format, Old Format, Double Elimination Format, single chunk, empty text, whitespace-only text, ValueError on non-empty with no headers
    - _Requirements: 5.1, 5.2, 5.3, 5.5_

- [x] 4. Implement `regex_parser.py`
  - [x] 4.1 Write `src/worker/regex_parser.py` — structural field extraction
    - Define `CANONICAL_CATEGORIES: frozenset[str]` constant
    - Implement `parseStructuralFields(chunk: str) -> dict[str, str]` — extracts `question_number`, `category`, `match_type`, `answer_format` via the regex patterns in the design; raises `ValueError` (with log of field name + chunk[:500]) on any missing/invalid field
    - Implement `normalizeCategory(raw: str) -> str` — title-case + canonical lookup; raises `ValueError` on unknown category
    - Full type hints and docstrings
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 9.1, 9.2, 9.3, 9.4_

  - [x] 4.2 Write `deriveSetRound` and `buildQuestionId` in `regex_parser.py`
    - Implement `deriveSetRound(s3Key: str) -> str` — splits on `/`, validates 4-segment pattern, returns `segments[2] + "_" + Path(segments[3]).stem`; raises `ValueError` on malformed key
    - Implement `buildQuestionId(questionNumber: str, matchType: str) -> str` — returns `f"Q_{int(questionNumber):02d}_{matchType}"`
    - Full type hints and docstrings
    - _Requirements: 4.1, 4.2, 4.3, 8.2_

  - [ ]* 4.3 Write property test for `Set_Round` derivation round-trip
    - **Property 4: Set_Round Derivation Round-Trip**
    - **Validates: Requirements 4.1, 4.2**
    - Use `@given(st.from_regex(r'[A-Za-z0-9-]+', fullmatch=True), st.from_regex(r'[A-Za-z0-9-]+', fullmatch=True))` for set-name and filename; assert `deriveSetRound(key) == f"{setName}_{filename}"`

  - [ ]* 4.4 Write property test for malformed S3 key rejection
    - **Property 5: Malformed S3 Key Rejection**
    - **Validates: Requirements 4.3**
    - Use `@given(st.text())` filtered to not match the valid 4-segment pattern; assert `deriveSetRound` raises `ValueError`

  - [ ]* 4.5 Write property test for structural field extraction across all formats
    - **Property 8: Structural Field Extraction Across All Formats**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 9.1, 9.2, 9.3, 9.4**
    - Use `@given(st.sampled_from(FORMAT_VARIANTS))` × random valid field values; assert all four fields returned match input

  - [ ]* 4.6 Write property test for category normalization
    - **Property 9: Category Normalization**
    - **Validates: Requirements 6.5**
    - Use `@given(st.sampled_from(list(CANONICAL_CATEGORIES)))` with random casing applied; assert canonical form returned. Use `@given(st.text())` filtered to not match any canonical; assert `ValueError` raised

  - [ ]* 4.7 Write property test for `Question_Id` format
    - **Property 14: Question_Id Format**
    - **Validates: Requirements 8.2**
    - Use `@given(st.integers(1, 99), st.sampled_from(["TOSS-UP", "BONUS"]))` ; assert result matches `r'^Q_\d{2}_(TOSS-UP|BONUS)$'`

  - [ ]* 4.8 Write unit tests for `regex_parser.py`
    - Cover all three format variants, category normalization, `Set_Round` derivation, malformed key, missing fields, `buildQuestionId` zero-padding
    - _Requirements: 4.1, 4.2, 4.3, 6.1–6.6, 9.1–9.5_

- [x] 5. Checkpoint — core utilities
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement `llm_client.py`
  - [x] 6.1 Write `src/worker/llm_client.py`
    - Implement `buildPrompt(chunk: str, answerFormat: str) -> str` — constructs Bedrock prompt; for `Multiple Choice` instructs model to return `answer_choices` as ordered list of 2–26 non-empty strings; for `Short Answer` instructs model to return `answer_choices` as `[]`
    - Implement `parseBedrockResponse(responseBody: str) -> dict[str, str | list[str]]` — parses JSON; raises `ValueError` (with log of raw response) if any of `question_stem`, `answer_choices`, `answer` is missing, null, or empty
    - Implement `extractFreeTextFields(bedrockClient, chunk: str, answerFormat: str) -> dict[str, str | list[str]]` — calls `buildPrompt`, invokes Bedrock, calls `parseBedrockResponse`; re-raises `ThrottlingException` directly; logs key + chunk index + error and re-raises on other exceptions
    - Full type hints and docstrings
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

  - [ ]* 6.2 Write property test for Multiple Choice prompt instruction
    - **Property 11: Multiple Choice Prompt Instruction**
    - **Validates: Requirements 7.3**
    - Use `@given(st.text())` as chunk; assert `buildPrompt(chunk, "Multiple Choice")` contains instruction for ordered list of 2–26 non-empty strings

  - [ ]* 6.3 Write property test for Short Answer prompt instruction
    - **Property 12: Short Answer Prompt Instruction**
    - **Validates: Requirements 7.4**
    - Use `@given(st.text())` as chunk; assert `buildPrompt(chunk, "Short Answer")` instructs model to return `answer_choices` as empty list

  - [ ]* 6.4 Write property test for LLM response validation
    - **Property 10: LLM Response Validation**
    - **Validates: Requirements 7.1, 7.7**
    - Use `@given(st.fixed_dictionaries({...}))` with one or more of the three required fields set to `None` or omitted; assert `parseBedrockResponse` raises `ValueError`

  - [ ]* 6.5 Write unit tests for `llm_client.py`
    - Mock `bedrockClient.invoke_model`; test MC prompt, SA prompt, valid response parsing, missing field raises, `ThrottlingException` re-raise, generic exception re-raise
    - _Requirements: 7.1–7.7_

- [x] 7. Implement `dynamo_writer.py`
  - [x] 7.1 Write `src/worker/dynamo_writer.py`
    - Define `REQUIRED_FIELDS: tuple[str, ...]` constant with all nine attribute names
    - Implement `writeQuestion(dynamoClient, tableName: str, item: dict) -> None` — validates all required fields present and non-None (raises `ValueError` with log before any write attempt); calls unconditional `put_item` (no `ConditionExpression`); logs `Set_Round` + `Question_Id` + error and re-raises on `put_item` failure
    - Full type hints and docstring
    - _Requirements: 8.1, 8.3, 8.4, 8.5, 8.6, 8.7, 10.3, 10.4_

  - [ ]* 7.2 Write property test for DynamoDB item completeness
    - **Property 13: DynamoDB Item Completeness**
    - **Validates: Requirements 8.1, 8.3, 10.4**
    - Use `@given(st.fixed_dictionaries({field: st.text(min_size=1) for field in REQUIRED_FIELDS}))` ; assert `put_item` called with all nine attributes and no `ConditionExpression`

  - [ ]* 7.3 Write property test for Short Answer `answer_choices` written as empty list
    - **Property 15: Short Answer answer_choices Written as Empty List**
    - **Validates: Requirements 8.6**
    - Use `@given(...)` with `answer_format="Short Answer"` and `answer_choices=[]`; assert `put_item` receives `answer_choices = []`

  - [ ]* 7.4 Write property test for missing required field preventing write
    - **Property 16: Missing Required Field Prevents Write**
    - **Validates: Requirements 8.7**
    - Use `@given(st.fixed_dictionaries({...}))` with one field set to `None`; assert `ValueError` raised and `put_item` never called

  - [ ]* 7.5 Write unit tests for `dynamo_writer.py`
    - Mock `dynamoClient.put_item`; test complete item write, missing field raises without write, SA empty list, no `ConditionExpression`, `put_item` failure propagation
    - _Requirements: 8.1, 8.3, 8.5, 8.6, 8.7_

- [x] 8. Checkpoint — all module-level tests
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement `src/worker/handler.py`
  - [x] 9.1 Write `src/worker/handler.py`
    - Implement `processRecord(record: dict, s3Client, bedrockClient, dynamoClient) -> int` — orchestrates the four pipeline stages: download → extract → chunk → (for each chunk: `deriveSetRound`, `parseStructuralFields`, `extractFreeTextFields`, assemble item, `writeQuestion`); logs S3 key at start, chunk count after chunking, `Set_Round`/`Question_Id` per write; returns count of items written
    - Implement `handler(event: dict, context: object) -> None` — creates `boto3.Session(profile_name='onasmmon')`, builds clients, iterates `event["Records"]` (batch size 1), calls `processRecord`; raises on any failure to trigger SQS retry
    - Full type hints and docstrings
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 5.1–5.5, 6.1–6.6, 7.1–7.7, 8.1–8.7, 10.1, 10.2, 10.3, 10.6_

  - [ ]* 9.2 Write unit tests for `src/worker/handler.py`
    - Mock all sub-module functions and AWS clients; test happy path (returns item count), S3 download failure raises, chunking failure raises, structural parse failure raises, Bedrock failure raises, DynamoDB write failure raises, zero-chunk ValueError raises
    - _Requirements: 2.2, 3.1, 3.3, 5.3, 6.6, 7.5, 7.6, 8.5, 8.7_

- [ ] 10. Implement `src/orchestrator/handler.py`
  - [x] 10.1 Write `src/orchestrator/handler.py`
    - Implement `listPdfKeys(s3Client, bucket: str, prefix: str) -> list[str]` — paginates `list_objects_v2`, filters keys ending in `.pdf` (case-insensitive); logs prefix + error and re-raises on paginator failure
    - Implement `enqueueKeys(sqsClient, queueUrl: str, keys: list[str]) -> int` — calls `send_message` once per key with body `{"s3_key": key}`; logs key + error and re-raises on `send_message` failure; returns count
    - Implement `handler(event: dict, context: object) -> dict` — creates `boto3.Session(profile_name='onasmmon')`, calls `listPdfKeys`, calls `enqueueKeys`, logs total discovered + enqueued, returns `{"enqueued": count}`
    - Full type hints and docstrings
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 10.5_

  - [ ]* 10.2 Write property test for S3 pagination completeness
    - **Property 1: S3 Pagination Completeness**
    - **Validates: Requirements 1.1, 1.2**
    - Use `@given(st.lists(st.text()))` for keys with random page splits; mock paginator to return pages; assert returned list equals exactly the `.pdf`-suffixed subset

  - [ ]* 10.3 Write property test for orchestrator enqueue count
    - **Property 2: Orchestrator Enqueue Count**
    - **Validates: Requirements 1.3, 1.4**
    - Use `@given(st.lists(st.from_regex(r'[\w/]+\.pdf', fullmatch=True)))` ; mock `sqsClient.send_message`; assert called exactly N times and return value equals N

  - [ ]* 10.4 Write unit tests for `src/orchestrator/handler.py`
    - Mock S3 paginator and SQS client; test pagination across multiple pages, `.pdf` filter (case-insensitive), enqueue count, S3 failure propagation, SQS failure propagation, return value shape
    - _Requirements: 1.1–1.6, 10.5_

- [x] 11. Checkpoint — all handler tests
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Write `template.yaml` (SAM infrastructure)
  - [x] 12.1 Define SQS queue, DLQ, and Worker Lambda in `template.yaml`
    - SQS queue with `VisibilityTimeout: 360`, DLQ `maxReceiveCount: 3`, DLQ `MessageRetentionPeriod: 1209600` (14 days)
    - Worker Lambda with `ReservedConcurrentExecutions: 20`, `Timeout: 360`, SQS event source with `BatchSize: 1`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 12.2 Define Orchestrator Lambda and DynamoDB table in `template.yaml`
    - Orchestrator Lambda with environment variables for bucket name, prefix, and queue URL
    - `ScienceBowlQuestions` DynamoDB table with `Set_Round` (PK), `Question_Id` (SK), and GSI on `Category` (PK) / `MatchType` (SK)
    - IAM policies granting Lambdas least-privilege access to S3, SQS, DynamoDB, and Bedrock
    - _Requirements: 1.1, 8.1, 8.4_

- [x] 13. Write integration smoke-test script
  - [x] 13.1 Write `tests/integration/smoke_test.py`
    - Script uses `boto3.Session(profile_name='onasmmon')` throughout
    - Test 1 — Orchestrator discovery: invoke Orchestrator Lambda directly, assert `enqueued > 0`
    - Test 2 — Worker end-to-end: send a single known S3 key to SQS, wait for Worker to process, query DynamoDB for the expected `Set_Round` + `Question_Id`, assert item exists with all nine required fields
    - Test 3 — DLQ routing: send a deliberately malformed message (empty body) three times, assert message appears in DLQ
    - Print pass/fail summary; exit with non-zero code on any failure
    - _Requirements: 1.1, 1.4, 2.1, 2.2, 2.3, 8.1, 10.4_

- [x] 14. Final checkpoint — full suite
  - Ensure all unit and property tests pass (`pytest tests/unit/`), ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP; all property and unit test sub-tasks carry this marker.
- Each task references specific requirements for traceability back to `/Users/mousommondal/projects/sci-bowl/.kiro/specs/sci-bowl-pdf-etl/requirements.md`.
- All AWS clients must use `boto3.Session(profile_name='onasmmon')` — never the default credential chain.
- Property tests use `hypothesis==6.112.2`; each test is tagged with a comment `# Feature: sci-bowl-pdf-etl, Property N: <title>`.
- No real AWS calls in unit tests — mock everything with `pytest-mock` / `moto`.
- The smoke-test script (`tests/integration/smoke_test.py`) is excluded from the default `pytest` run; invoke it manually with `AWS_PROFILE=onasmmon python tests/integration/smoke_test.py`.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1", "3.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "3.2", "3.3", "3.4", "4.1"] },
    { "id": 3, "tasks": ["4.2", "4.3", "4.4", "4.8"] },
    { "id": 4, "tasks": ["4.5", "4.6", "4.7", "6.1", "7.1"] },
    { "id": 5, "tasks": ["6.2", "6.3", "6.4", "6.5", "7.2", "7.3", "7.4", "7.5"] },
    { "id": 6, "tasks": ["9.1"] },
    { "id": 7, "tasks": ["9.2", "10.1"] },
    { "id": 8, "tasks": ["10.2", "10.3", "10.4"] },
    { "id": 9, "tasks": ["12.1"] },
    { "id": 10, "tasks": ["12.2"] },
    { "id": 11, "tasks": ["13.1"] }
  ]
}
```
