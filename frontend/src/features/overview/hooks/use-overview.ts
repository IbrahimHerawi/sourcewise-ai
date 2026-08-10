"use client";

import { useCallback } from "react";
import { useApiRequest } from "@/hooks/use-api-request";
import { getOverviewDataApi } from "../overview-api";

export function useOverview() {
  const request = useCallback(
    (signal: AbortSignal) => getOverviewDataApi(signal),
    [],
  );
  return useApiRequest(request);
}
