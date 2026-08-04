"use client";

import { useCallback, useMemo } from "react";
import { useApiRequest } from "@/hooks/use-api-request";
import { listQuestionHistoryApi } from "../questions-api";

export const questionHistoryQueryKeys = {
  all: ["questions", "history"] as const,
  list: (limit: number, offset: number) =>
    ["questions", "history", { limit, offset }] as const,
};

export function useQuestionHistory(limit: number, offset: number) {
  const queryKey = useMemo(
    () => questionHistoryQueryKeys.list(limit, offset),
    [limit, offset],
  );
  const request = useCallback(
    (signal: AbortSignal) =>
      listQuestionHistoryApi({ limit, offset }, signal),
    [limit, offset],
  );
  const state = useApiRequest(request);
  return { ...state, queryKey };
}
