# Requirements Document

## Introduction

This feature implements an ETL (Extract, Transform, Load) pipeline that processes Science Bowl question PDFs stored in S3 and loads structured question data into DynamoDB. The pipeline uses an Orchestrator Lambda to fan out work via SQS, and Worker Lambdas to process each PDF end-to-end: extracting text with pdfplumber, chunking questions with regex, and using an LLM (via Amazon Bedrock) only for free-text fields. The system targets ~250 PDFs across three PDF format variants, producing ~11,500 structured question records.

## Glossary

- **Orchestrator_Lambda**: AWS Lambda function that lists all PDFs in S3 and enqueues one SQS message per PDF.
- **Worker_Lambda**: AWS Lambda function triggered by SQS that processes a single PDF end-to-end.
- **SQS_Queue**: Amazon SQS queue used to fan out PDF processing tasks from the Orchestrator to Workers.
- **DLQ**: Dead Letter Queue that receives SQS messages that fail processing after the maximum receive count.
- **PDF_Chunk**: A contiguous block of text from a PDF corresponding to a single TOSS-UP or BONUS question, including its header line and all text up to the next header or end of input.
- **Set_Round**: The DynamoDB partition key, derived deterministically from the S3 path (e.g., `Sample-Set-13_Round-10A`).
- **Question_Id**: The DynamoDB sort key identifying a question within a round (e.g., `Q_01_TOSS-UP`, `Q_02_BONUS`).
- **Match_Type**: Whether a question is a `TOSS-UP` or `BONUS`.
- **Answer_Format**: Whether a question requires a `Short Answer` or `Multiple Choice` response.
- **Category**: The science subject of a question (e.g., `Life Science`, `Mathematics`, `Earth and Space`).
- **LLM**: Large Language Model accessed via Amazon Bedrock (Claude Haiku or Nova Micro) used to extract free-text fields.
- **Bedrock**: Amazon Bedrock service used to invoke the LLM.
- **pdfplumber**: Python library used to extract raw text from PDF pages.
- **New_Format**: PDF format used in Set-13 and later, with headers like `MIDDLE SCHOOL - ROUND 10A` and category lines like `1) Earth and Space – Short Answer`.
- **Old_Format**: PDF format used in Set-1 through approximately Set-10, with headers like `ROUND 1` and category lines like `1) LIFE SCIENCE Short Answer`.
- **Double_Elimination_Format**: PDF format with headers like `DOUBLE ELIMINATION ROUND 1` and category lines like `1) GENERAL SCIENCE Short Answer`.

---

## Requirements

### Requirement 1: S3 PDF Discovery

**User Story:** As a pipeline operator, I want the system to discover all Science Bowl PDFs in S3, so that no PDF is missed and processing can be triggered automatically.

#### Acceptance Criteria

1. WHEN the Orchestrator_Lambda is invoked, THE Orchestrator_Lambda SHALL list all objects under the S3 path prefix `raw-pdf-vault/middle-school/` in the bucket `eshaan-sci-bowl-paper`, using paginated listing to retrieve all keys regardless of total count.
2. WHEN listing S3 objects, THE Orchestrator_Lambda SHALL filter for keys whose suffix matches `.pdf` (case-insensitive).
3. WHEN a `.pdf` key is discovered, THE Orchestrator_Lambda SHALL enqueue exactly one SQS message to the SQS_Queue with a message body containing the full S3 key as a JSON string field `s3_key`.
4. WHEN all PDFs have been enqueued, THE Orchestrator_Lambda SHALL return a summary count of messages enqueued.
5. IF the S3 listing operation fails for any page, THEN THE Orchestrator_Lambda SHALL log the S3 key prefix and error details and raise the exception.
6. IF an individual SQS `send_message` call fails, THEN THE Orchestrator_Lambda SHALL log the affected S3 key and exception details and raise the exception without silently skipping the key.

---

### Requirement 2: SQS Fan-Out and Retry

**User Story:** As a pipeline operator, I want each PDF to be processed independently via SQS, so that failures are isolated and retries do not reprocess successful PDFs.

#### Acceptance Criteria

1. THE SQS_Queue SHALL have a DLQ configured with `maxReceiveCount` set to 3.
2. WHEN a Worker_Lambda invocation returns an error or times out (non-success response to SQS), THE SQS_Queue SHALL retry delivery up to 3 times before routing the message to the DLQ.
3. WHEN a message is routed to the DLQ, THE DLQ SHALL retain the message for at least 14 days.
4. THE Worker_Lambda SHALL have a reserved concurrency set to an inclusive value between 20 and 30 to limit parallel Bedrock invocations.
5. THE SQS_Queue SHALL have a visibility timeout of at least 6 minutes to prevent premature redelivery before a Worker_Lambda invocation can complete.

---

### Requirement 3: PDF Text Extraction

**User Story:** As a pipeline engineer, I want raw text extracted from each PDF, so that question content can be parsed downstream.

#### Acceptance Criteria

1. WHEN a Worker_Lambda receives an SQS message, THE Worker_Lambda SHALL download the PDF binary from S3 using the `s3_key` field in the message body; IF the S3 download fails, THEN THE Worker_Lambda SHALL log the S3 key and exception details and raise the exception to trigger SQS retry.
2. WHEN a PDF is downloaded, THE Worker_Lambda SHALL extract text from all pages using pdfplumber's `extract_text()` method, treating any page that returns `None` or an empty string as an empty string, and concatenate all page results in page order.
3. IF pdfplumber raises an exception during extraction, THEN THE Worker_Lambda SHALL log the S3 key and exception details and raise the exception to trigger SQS retry.
4. THE Worker_Lambda SHALL process each PDF as a single-column text document without multi-column layout handling.

---

### Requirement 4: Set_Round Key Derivation

**User Story:** As a data consumer, I want the DynamoDB partition key derived deterministically from the S3 path, so that records are consistently addressable without additional metadata.

#### Acceptance Criteria

1. WHEN processing a PDF, THE Worker_Lambda SHALL derive `Set_Round` by extracting the 3rd forward-slash-delimited segment (0-indexed) of the S3 key as `{Set-Name}` and the filename stem (the portion of the 4th segment before `.pdf`) as the round identifier, then combining them as `{Set-Name}_{Round-Identifier}`.
2. THE Worker_Lambda SHALL produce Set_Round values in the format `{Set-Name}_{Round-Identifier}` (e.g., `Sample-Set-13_Round-10A`, `Sample-Set-1_m_round01`).
3. IF the S3 key does not contain exactly 4 forward-slash-delimited segments matching the pattern `raw-pdf-vault/middle-school/{non-empty-string}/{non-empty-string}.pdf`, THEN THE Worker_Lambda SHALL log the malformed key and raise a `ValueError` to trigger SQS retry.

---

### Requirement 5: Question Chunking

**User Story:** As a pipeline engineer, I want the extracted PDF text split into individual question chunks, so that each question can be processed independently.

#### Acceptance Criteria

1. WHEN full PDF text is available, THE Worker_Lambda SHALL split the text into PDF_Chunks by matching `TOSS-UP` or `BONUS` at the start of a line; each PDF_Chunk SHALL include its matching header line and all subsequent text up to (but not including) the next matching header or end of input.
2. THE Worker_Lambda SHALL produce at least one PDF_Chunk from any input text that contains at least one line starting with `TOSS-UP` or `BONUS`, across all three PDF format variants: New_Format, Old_Format, and Double_Elimination_Format.
3. IF the extracted text contains at least one non-whitespace character but chunking produces zero PDF_Chunks, THEN THE Worker_Lambda SHALL log the S3 key and raise a `ValueError` to trigger SQS retry.
4. THE Worker_Lambda SHALL preserve the original text of each PDF_Chunk without modification before passing it to regex extraction.
5. IF the extracted text contains no lines starting with `TOSS-UP` or `BONUS` and no non-whitespace characters, THE Worker_Lambda SHALL log the S3 key as producing an unrecognized format and raise a `ValueError` to trigger SQS retry.

---

### Requirement 6: Structural Field Extraction via Regex

**User Story:** As a pipeline engineer, I want structural question fields extracted deterministically via regex, so that LLM calls are minimized and extraction is fast and reliable.

#### Acceptance Criteria

1. WHEN processing a PDF_Chunk, THE Worker_Lambda SHALL extract `question_number` as one or more consecutive digit characters using regex, without invoking the LLM.
2. WHEN processing a PDF_Chunk, THE Worker_Lambda SHALL extract `category` using regex without invoking the LLM.
3. WHEN processing a PDF_Chunk, THE Worker_Lambda SHALL extract `match_type` using regex; IF the extracted value is not exactly `TOSS-UP` or `BONUS`, THEN THE Worker_Lambda SHALL treat it as an extraction failure per criterion 6.
4. WHEN processing a PDF_Chunk, THE Worker_Lambda SHALL extract `answer_format` using regex; IF the extracted value is not exactly `Short Answer` or `Multiple Choice`, THEN THE Worker_Lambda SHALL treat it as an extraction failure per criterion 6.
5. THE Worker_Lambda SHALL normalize category strings to title-case canonical values from the set: `Life Science`, `Earth and Space`, `Physical Science`, `Mathematics`, `Energy`, `Earth Science`, `General Science`, `Math`, `Chemistry`; IF the normalized value does not match any canonical value, THEN THE Worker_Lambda SHALL treat it as an extraction failure per criterion 6.
6. IF any of the four required structural fields (`question_number`, `category`, `match_type`, `answer_format`) cannot be extracted from a PDF_Chunk, THEN THE Worker_Lambda SHALL log the field name and the first 500 characters of the chunk text and raise a `ValueError` to trigger SQS retry.

---

### Requirement 7: Free-Text Field Extraction via LLM

**User Story:** As a data consumer, I want question stems, answer choices, and answers extracted accurately from free-text, so that the structured records are complete and usable.

#### Acceptance Criteria

1. WHEN structural fields have been extracted from a PDF_Chunk, THE Worker_Lambda SHALL invoke the LLM via Bedrock to extract `question_stem`, `answer_choices`, and `answer`; a valid extraction requires all three fields to be non-null and non-empty strings or lists.
2. THE Worker_Lambda SHALL use the AWS profile `onasmmon` when initializing the Bedrock client.
3. IF the `answer_format` for a PDF_Chunk is `Multiple Choice`, THEN THE Worker_Lambda SHALL instruct the LLM to return `answer_choices` as an ordered list of 2 to 26 non-empty strings.
4. IF the `answer_format` for a PDF_Chunk is `Short Answer`, THEN THE Worker_Lambda SHALL instruct the LLM to return `answer_choices` as an empty list.
5. IF the Bedrock invocation fails with a throttling error, THEN THE Worker_Lambda SHALL raise the exception to trigger SQS retry with backoff.
6. IF the Bedrock invocation fails with a non-throttling error, THEN THE Worker_Lambda SHALL log the S3 key, chunk index, and exception details and raise the exception to trigger SQS retry.
7. IF the LLM response does not contain all three required fields (`question_stem`, `answer_choices`, `answer`) as non-null and non-empty values, THEN THE Worker_Lambda SHALL log the raw response and raise a `ValueError` to trigger SQS retry.

---

### Requirement 8: DynamoDB Write

**User Story:** As a data consumer, I want each extracted question written to DynamoDB with a consistent schema, so that questions are queryable by set, round, category, and match type.

#### Acceptance Criteria

1. IF all required fields (`Set_Round`, `Question_Id`, `Category`, `MatchType`, `question_stem`, `answer_choices`, `answer`, `answer_format`, `source_s3_key`) have been successfully extracted, THEN THE Worker_Lambda SHALL write a DynamoDB item containing exactly those attributes to the `ScienceBowlQuestions` table.
2. THE Worker_Lambda SHALL construct `Set_Round` in the format `{Set-Name}_{Round-Identifier}` (e.g., `Sample-Set-13_Round-10A`) and `Question_Id` in the format `Q_{question_number:02d}_{match_type}` (e.g., `Q_01_TOSS-UP`).
3. THE Worker_Lambda SHALL write items using an unconditional `put_item` (overwrite semantics) to ensure idempotency on retry.
4. THE Worker_Lambda SHALL use the AWS profile `onasmmon` when initializing the DynamoDB client.
5. IF the DynamoDB `put_item` call fails, THEN THE Worker_Lambda SHALL log the `Set_Round`, `Question_Id`, and exception details and raise the exception to trigger SQS retry.
6. WHEN the `answer_format` is `Short Answer`, THE Worker_Lambda SHALL write `answer_choices` as an empty list attribute rather than omitting the attribute.
7. IF any required field is missing or null at write time, THEN THE Worker_Lambda SHALL log the missing field name and the `Set_Round` and `Question_Id` values and raise a `ValueError` without attempting the DynamoDB write.

---

### Requirement 9: Multi-Format PDF Compatibility

**User Story:** As a pipeline operator, I want all three PDF format variants parsed correctly, so that the full corpus of ~250 PDFs can be processed without manual intervention.

#### Acceptance Criteria

1. WHEN processing a New_Format PDF, THE Worker_Lambda SHALL extract the round identifier as the literal text captured by the pattern `MIDDLE SCHOOL - ROUND ([A-Za-z0-9 ]+)` from the first page header.
2. WHEN processing an Old_Format PDF, THE Worker_Lambda SHALL extract the round identifier as the literal text captured by the pattern `^ROUND ([A-Za-z0-9 ]+)$` from the first page header.
3. WHEN processing a Double_Elimination_Format PDF, THE Worker_Lambda SHALL extract the round identifier as the literal text captured by the pattern `DOUBLE ELIMINATION ROUND ([A-Za-z0-9 ]+)` from the first page header.
4. THE Worker_Lambda SHALL extract the category name and answer format from category lines using both separator styles: the hyphenated style (`{category} – {answer_format}`) and the space-separated style (`{CATEGORY} {answer_format}`).
5. IF the first page header does not match any of the three recognized patterns, THEN THE Worker_Lambda SHALL log the S3 key and the unrecognized header text and raise a `ValueError` to trigger SQS retry.

---

### Requirement 10: Observability and Idempotency

**User Story:** As a pipeline operator, I want the pipeline to be observable and safe to re-run, so that I can diagnose failures and reprocess PDFs without creating duplicate records.

#### Acceptance Criteria

1. THE Worker_Lambda SHALL log the S3 key at the start of each invocation.
2. THE Worker_Lambda SHALL log the number of PDF_Chunks extracted per PDF.
3. THE Worker_Lambda SHALL log the Set_Round and Question_Id for each DynamoDB item written; IF no items are written for a PDF, THE Worker_Lambda SHALL log the S3 key and a count of zero items written.
4. WHEN the same SQS message is delivered more than once, THE Worker_Lambda SHALL produce exactly one DynamoDB item keyed on the same `Set_Round` (PK) and `Question_Id` (SK) derived from the message, with the last write winning via overwrite semantics.
5. THE Orchestrator_Lambda SHALL log the total number of PDFs discovered and messages enqueued per invocation.
6. IF a PDF produces zero PDF_Chunks after text extraction, THE Worker_Lambda SHALL log the S3 key with a warning indicating zero chunks were produced before raising a `ValueError`.
