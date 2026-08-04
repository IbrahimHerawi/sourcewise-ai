"use client";

import { useCallback, useMemo } from "react";
import { listAllDocumentsApi } from "@/features/documents/documents-api";
import { mapDocumentRecord } from "@/features/documents/document-mappers";
import { useApiRequest } from "@/hooks/use-api-request";
import { invalidApiResponse } from "@/lib/api-contract";

export type QuestionSourceAvailability = {
  documentCount: number;
  readyByCollection: Readonly<Record<string, number>>;
  readyDocumentCount: number;
};

export const questionSourceQueryKey = ["questions", "sources"] as const;

async function loadQuestionSourceAvailability(
  signal: AbortSignal,
): Promise<QuestionSourceAvailability> {
  const documents = (await listAllDocumentsApi(signal)).map(mapDocumentRecord);
  if (documents.some((document) => document.status === "UNKNOWN")) {
    return invalidApiResponse("question sources");
  }
  const readyByCollection: Record<string, number> = {};
  let readyDocumentCount = 0;

  for (const document of documents) {
    if (document.status !== "READY") continue;
    readyDocumentCount += 1;
    if (document.collection_id) {
      readyByCollection[document.collection_id] =
        (readyByCollection[document.collection_id] ?? 0) + 1;
    }
  }

  return {
    documentCount: documents.length,
    readyByCollection,
    readyDocumentCount,
  };
}

export function useQuestionSources() {
  const queryKey = useMemo(() => questionSourceQueryKey, []);
  const request = useCallback(
    (signal: AbortSignal) => loadQuestionSourceAvailability(signal),
    [],
  );
  const state = useApiRequest(request);
  return { ...state, queryKey };
}
