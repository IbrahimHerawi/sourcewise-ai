"use client";

import { useEffect } from "react";
import type { PaginatedDocuments } from "../types";
import { DOCUMENT_STATUS_PRESENTATION } from "../document-status";

const PROCESSING_POLL_INTERVAL_MS = 2_500;

export function useDocumentProcessingPolling({
  data,
  isRefreshing,
  refetch,
}: {
  data: PaginatedDocuments | undefined;
  isRefreshing: boolean;
  refetch: (options?: { silent?: boolean }) => Promise<PaginatedDocuments>;
}) {
  const pollingRequired =
    data?.items.some(
      (document) =>
        DOCUMENT_STATUS_PRESENTATION[document.status].pollingRequired,
    ) ?? false;

  useEffect(() => {
    if (!pollingRequired || isRefreshing) return;

    let timer: number | undefined;
    const refresh = () => {
      void refetch({ silent: true }).catch(() => undefined);
    };
    const schedule = () => {
      if (document.visibilityState === "visible") {
        timer = window.setTimeout(refresh, PROCESSING_POLL_INTERVAL_MS);
      }
    };
    const handleVisibilityChange = () => {
      if (timer !== undefined) window.clearTimeout(timer);
      timer = undefined;
      if (document.visibilityState === "visible") refresh();
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    schedule();
    return () => {
      if (timer !== undefined) window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [isRefreshing, pollingRequired, refetch]);
}
