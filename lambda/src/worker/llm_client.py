"""Bedrock LLM invocation and response parsing for free-text field extraction."""

import json
import logging

logger = logging.getLogger(__name__)

_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

_MC_ANSWER_CHOICES_INSTRUCTION = (
    "Return `answer_choices` as an ordered JSON array of 2 to 26 non-empty strings "
    "representing the W, X, Y, Z (and any additional) answer options exactly as they "
    "appear in the text, preserving their label prefixes (e.g. \"W) ...\")."
)
_SA_ANSWER_CHOICES_INSTRUCTION = (
    "Return `answer_choices` as an empty JSON array `[]` because this is a Short Answer question."
)


def buildPrompt(chunk: str, answerFormat: str) -> str:
    """Construct a Bedrock prompt for extracting free-text fields from a question chunk.

    The prompt instructs the model to return a JSON object with three keys:
    ``question_stem``, ``answer_choices``, and ``answer``.

    For ``"Multiple Choice"``, ``answer_choices`` must be an ordered list of
    2–26 non-empty strings.  For ``"Short Answer"``, ``answer_choices`` must
    be an empty list.

    Args:
        chunk: The raw question block text from the PDF.
        answerFormat: Either ``"Multiple Choice"`` or ``"Short Answer"``.

    Returns:
        A prompt string ready to send to the Bedrock model.
    """
    if answerFormat == "Multiple Choice":
        answerChoicesInstruction = _MC_ANSWER_CHOICES_INSTRUCTION
    else:
        answerChoicesInstruction = _SA_ANSWER_CHOICES_INSTRUCTION

    return (
        "You are a data extraction assistant. Extract the following fields from the "
        "Science Bowl question text below and return ONLY a valid JSON object — no "
        "markdown, no explanation, no extra text, no code fences.\n\n"
        "Your response must be a single JSON object starting with {{ and ending with }}.\n\n"
        "Required JSON fields:\n"
        "- `question_stem` (string): The full question text, excluding answer choices "
        "and the answer line.\n"
        f"- `answer_choices` (array): {answerChoicesInstruction}\n"
        "- `answer` (string): The correct answer exactly as it appears after the "
        "\"ANSWER:\" label.\n\n"
        "Rules:\n"
        "1. Do NOT wrap the JSON in markdown code fences (no ```json or ```).\n"
        "2. Do NOT return a JSON array — return a single JSON object.\n"
        "3. All three fields are required and must be non-null and non-empty "
        "(except `answer_choices` which may be [] for Short Answer).\n"
        "4. Preserve the original wording; do not paraphrase.\n"
        "5. LaTeX formatting: whenever you encounter mathematical expressions, "
        "chemical formulas, scientific notation, Greek letters, subscripts, "
        "superscripts, or any symbolic notation, render them using LaTeX syntax "
        "wrapped in single dollar-sign delimiters for inline math (e.g. $E = mc^2$, "
        "$H_2O$, $\\\\alpha$, $6.02 \\\\times 10^{23}$). Use double dollar signs "
        "$$...$$ only for standalone display equations. Plain prose must remain "
        "as plain text — only mathematical/scientific notation gets LaTeX markup.\n\n"
        "Question text:\n"
        "---\n"
        f"{chunk}\n"
        "---\n"
    )


def parseBedrockResponse(responseBody: str) -> dict[str, str | list[str]]:
    """Parse and validate the JSON response body returned by Bedrock.

    Args:
        responseBody: The raw response string from the Bedrock model.

    Returns:
        A dict with keys ``question_stem`` (str), ``answer_choices`` (list),
        and ``answer`` (str).

    Raises:
        ValueError: If the JSON cannot be parsed, or if any of the three
            required fields is missing, null, or empty.
    """
    cleaned = _extractJsonObject(responseBody)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("parseBedrockResponse: invalid JSON. raw=%s", responseBody)
        raise ValueError(f"Bedrock response is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        # Model sometimes returns an array of objects instead of a single object.
        # Each chunk is one question, so take the first element if it's a valid dict.
        if isinstance(data, list) and len(data) >= 1 and isinstance(data[0], dict):
            logger.warning(
                "parseBedrockResponse: model returned array with %d element(s), using first",
                len(data),
            )
            data = data[0]
        else:
            logger.error(
                "parseBedrockResponse: expected JSON object, got %s. raw=%s",
                type(data).__name__,
                responseBody,
            )
            raise ValueError(f"Bedrock response is not a JSON object (got {type(data).__name__})")

    _validateField(data, "question_stem", responseBody)
    _validateField(data, "answer_choices", responseBody)
    _validateField(data, "answer", responseBody)

    return {
        "question_stem": data["question_stem"],
        "answer_choices": data["answer_choices"],
        "answer": data["answer"],
    }


def _stripMarkdownFence(text: str) -> str:
    """Remove markdown code fences if the model wrapped its JSON response.

    Handles both ```json ... ``` and ``` ... ``` variants.

    Args:
        text: Raw response string from the model.

    Returns:
        The response with any surrounding code fence stripped.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1:]
        if stripped.endswith("```"):
            stripped = stripped[:-3].rstrip()
    return stripped


def _extractJsonObject(text: str) -> str:
    """Extract the first complete JSON object or array from a string.

    Handles cases where the model appends reasoning text after the JSON,
    or wraps it in a markdown code fence.

    Args:
        text: Raw response string from the model.

    Returns:
        The first JSON object/array substring found.

    Raises:
        ValueError: If no JSON object or array can be found.
    """
    stripped = _stripMarkdownFence(text)

    # Find the first { or [ and match its closing counterpart
    for startChar, endChar in [('{', '}'), ('[', ']')]:
        start = stripped.find(startChar)
        if start == -1:
            continue
        depth = 0
        inString = False
        escape = False
        for i, ch in enumerate(stripped[start:], start):
            if escape:
                escape = False
                continue
            if ch == '\\' and inString:
                escape = True
                continue
            if ch == '"':
                inString = not inString
                continue
            if inString:
                continue
            if ch == startChar:
                depth += 1
            elif ch == endChar:
                depth -= 1
                if depth == 0:
                    return stripped[start:i + 1]

    raise ValueError("No JSON object or array found in response")


def _validateField(data: dict, fieldName: str, rawResponse: str) -> None:
    """Raise ValueError if a required field is missing, null, or empty.

    ``answer_choices`` is allowed to be an empty list ``[]`` because Short
    Answer questions legitimately have no answer choices (Requirement 7.4).
    All other fields must be non-null and non-empty.

    Args:
        data: The parsed response dict.
        fieldName: The field to validate.
        rawResponse: The original raw response string (for logging).

    Raises:
        ValueError: If the field is absent, None, or an empty string (or an
            empty list for fields other than ``answer_choices``).
    """
    value = data.get(fieldName)
    isInvalid = value is None or value == ""
    if fieldName != "answer_choices":
        isInvalid = isInvalid or value == []
    if isInvalid:
        logger.error(
            "parseBedrockResponse: missing or empty field=%s raw=%s",
            fieldName,
            rawResponse,
        )
        raise ValueError(f"Bedrock response missing or empty field: {fieldName!r}")


def extractFreeTextFields(
    bedrockClient,
    chunk: str,
    answerFormat: str,
    s3Key: str = "",
) -> dict[str, str | list[str]]:
    """Invoke Bedrock to extract question_stem, answer_choices, and answer.

    Builds a prompt from ``chunk`` and ``answerFormat``, calls the Bedrock
    converse API, and delegates response parsing to ``parseBedrockResponse``.

    Throttling exceptions are re-raised immediately so SQS can apply backoff.
    All other exceptions are logged with ``s3Key`` context before re-raising.

    Args:
        bedrockClient: A boto3 Bedrock Runtime client.
        chunk: The raw question block text from the PDF.
        answerFormat: Either ``"Multiple Choice"`` or ``"Short Answer"``.
        s3Key: Optional S3 key for error-log context.

    Returns:
        A dict with keys ``question_stem`` (str), ``answer_choices`` (list),
        and ``answer`` (str).

    Raises:
        botocore.exceptions.ClientError: Re-raised directly for throttling
            errors so SQS retry backoff applies.
        Exception: Re-raised after logging for all other Bedrock errors.
        ValueError: If the model response is missing required fields.
    """
    prompt = buildPrompt(chunk, answerFormat)
    messages = [{"role": "user", "content": [{"text": prompt}]}]

    try:
        response = bedrockClient.converse(
            modelId=_MODEL_ID,
            messages=messages,
        )
    except Exception as exc:
        _handleBedrockError(exc, s3Key)

    responseText = response["output"]["message"]["content"][0]["text"]
    return parseBedrockResponse(responseText)


def _handleBedrockError(exc: Exception, s3Key: str) -> None:
    """Log and re-raise a Bedrock invocation error.

    Throttling exceptions are re-raised immediately (no log) so SQS backoff
    applies.  All other exceptions are logged with context before re-raising.

    Args:
        exc: The exception raised by the Bedrock client.
        s3Key: S3 key for log context.

    Raises:
        Exception: Always re-raises ``exc``.
    """
    # botocore ClientError carries the error code in exc.response["Error"]["Code"]
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        errorCode = response.get("Error", {}).get("Code", "")
        if errorCode == "ThrottlingException":
            raise exc

    logger.error(
        "extractFreeTextFields: Bedrock error. s3Key=%s error=%s", s3Key, exc
    )
    raise exc
