import { apiRequest } from "@/lib/api";
import {
  invalidApiResponse,
  readApiArray,
  readApiDateTime,
  readApiInteger,
  readApiNullableString,
  readApiNullableUuid,
  readApiNumber,
  readApiObject,
  readApiString,
  readApiText,
  readApiUuid,
} from "@/lib/api-contract";
import type {
  AskQuestionApiInput,
  Citation,
  PaginatedQuestionHistory,
  QuestionAnswer,
  QuestionHistoryApiInput,
  QuestionHistoryItem,
  QuestionProvider,
} from "./questions-api-types";

const QUESTION_CONTRACT = "question";
const QUESTION_HISTORY_CONTRACT = "question history";

function readProvider(
  record: Record<string, unknown>,
  contract: string,
): QuestionProvider | null {
  const provider = readApiNullableString(record, "provider", contract);
  if (provider === null || provider === "openai" || provider === "ollama") {
    return provider;
  }
  return invalidApiResponse(contract);
}

function parseCitation(value: unknown, contract: string): Citation {
  const record = readApiObject(value, contract);
  return {
    rank: readApiInteger(record, "rank", contract, 1),
    document_id: readApiUuid(record, "document_id", contract),
    document_filename: readApiString(
      record,
      "document_filename",
      contract,
    ),
    chunk_id: readApiUuid(record, "chunk_id", contract),
    chunk_index: readApiInteger(record, "chunk_index", contract),
    excerpt: readApiText(record, "excerpt", contract),
    distance: readApiNumber(record, "distance", contract),
  };
}

function parseQuestionAnswerRecord(
  value: unknown,
  contract: string,
): QuestionAnswer {
  const record = readApiObject(value, contract);
  return {
    question_id: readApiUuid(record, "question_id", contract),
    collection_id: readApiNullableUuid(record, "collection_id", contract),
    answer: readApiText(record, "answer", contract),
    citations: readApiArray(record, "citations", contract).map((citation) =>
      parseCitation(citation, contract),
    ),
    created_at: readApiDateTime(record, "created_at", contract),
    provider: readProvider(record, contract),
    model: readApiNullableString(record, "model", contract),
  };
}

function parseQuestionHistoryItem(value: unknown): QuestionHistoryItem {
  const record = readApiObject(value, QUESTION_HISTORY_CONTRACT);
  return {
    ...parseQuestionAnswerRecord(record, QUESTION_HISTORY_CONTRACT),
    question: readApiString(
      record,
      "question",
      QUESTION_HISTORY_CONTRACT,
    ),
  };
}

function parseQuestionHistoryPage(value: unknown): PaginatedQuestionHistory {
  const record = readApiObject(value, QUESTION_HISTORY_CONTRACT);
  const limit = readApiInteger(
    record,
    "limit",
    QUESTION_HISTORY_CONTRACT,
    1,
  );
  const offset = readApiInteger(
    record,
    "offset",
    QUESTION_HISTORY_CONTRACT,
  );
  const total = readApiInteger(
    record,
    "total",
    QUESTION_HISTORY_CONTRACT,
  );
  const items = readApiArray(
    record,
    "items",
    QUESTION_HISTORY_CONTRACT,
  ).map(parseQuestionHistoryItem);

  if (
    items.length > limit ||
    items.length > Math.max(0, total - offset)
  ) {
    return invalidApiResponse(QUESTION_HISTORY_CONTRACT);
  }

  return { items, limit, offset, total };
}

export async function askQuestionApi(
  input: AskQuestionApiInput,
  signal?: AbortSignal,
): Promise<QuestionAnswer> {
  const response = await apiRequest<unknown>("/questions/ask", {
    method: "POST",
    body: JSON.stringify({
      question: input.question,
      collection_id: input.collectionId,
    }),
    signal,
  });
  const answer = parseQuestionAnswerRecord(response, QUESTION_CONTRACT);
  if (answer.collection_id !== input.collectionId) {
    return invalidApiResponse(QUESTION_CONTRACT);
  }
  return answer;
}

export async function listQuestionHistoryApi(
  input: QuestionHistoryApiInput,
  signal?: AbortSignal,
): Promise<PaginatedQuestionHistory> {
  const query = new URLSearchParams({
    limit: String(input.limit),
    offset: String(input.offset),
  });
  if (input.collectionId) {
    query.set("collection_id", input.collectionId);
  }

  const response = await apiRequest<unknown>(
    `/questions/history?${query}`,
    { signal },
  );
  const page = parseQuestionHistoryPage(response);
  if (page.limit !== input.limit || page.offset !== input.offset) {
    return invalidApiResponse(QUESTION_HISTORY_CONTRACT);
  }
  return page;
}

export async function getQuestionHistoryItemApi(
  questionId: string,
  signal?: AbortSignal,
): Promise<QuestionHistoryItem> {
  const response = await apiRequest<unknown>(
    `/questions/history/${questionId}`,
    { signal },
  );
  const item = parseQuestionHistoryItem(response);
  if (item.question_id !== questionId) {
    return invalidApiResponse(QUESTION_HISTORY_CONTRACT);
  }
  return item;
}

export function deleteQuestionHistoryItemApi(
  questionId: string,
  signal?: AbortSignal,
): Promise<Record<string, never>> {
  return apiRequest<Record<string, never>>(
    `/questions/history/${questionId}`,
    {
      method: "DELETE",
      signal,
    },
  );
}
