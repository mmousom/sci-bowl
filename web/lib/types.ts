/** Answer format filter options available in the practice UI. */
export type AnswerFormatFilter =
  | "All"
  | "Multiple Choice"
  | "Short Answer"
  | "TOSS-UP"
  | "BONUS";

/** Mirrors the DynamoDB record written by the ETL pipeline. */
export interface DynamoQuestion {
  /** Partition key */
  Set_Round: string;
  /** Sort key */
  Question_Id: string;
  /** GSI partition key (GSI_Category_MatchType) */
  Category: string;
  /** GSI sort key */
  MatchType: "TOSS-UP" | "BONUS";
  question_stem: string;
  /** Empty array for Short Answer questions */
  answer_choices: string[];
  answer: string;
  answer_format: "Multiple Choice" | "Short Answer";
  /** Not returned to the client */
  source_s3_key: string;
}

/** Shape returned by the /api/question route (source_s3_key stripped). */
export interface QuestionResponse {
  Set_Round: string;
  Question_Id: string;
  Category: string;
  MatchType: "TOSS-UP" | "BONUS";
  question_stem: string;
  answer_choices: string[];
  answer: string;
  answer_format: "Multiple Choice" | "Short Answer";
}

/** In-memory tally of correct and total answered questions for the session. */
export interface SessionScore {
  correct: number;
  total: number;
}

/** Combination of Category, AnswerFormat, and Set_Round selections used to fetch a question. */
export interface PracticeFilter {
  /** "All Categories" or a specific category name */
  category: string;
  format: AnswerFormatFilter;
  /** "All Rounds" or a specific Set_Round value */
  setRound: string;
}
