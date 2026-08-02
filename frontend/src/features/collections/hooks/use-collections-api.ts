"use client";

import { useCallback } from "react";
import {
  getCollection,
  getCollectionDocuments,
  getCollectionHistory,
  getCollections,
} from "@/features/collections/collections-api";
import { useApiRequest } from "@/hooks/use-api-request";

export function useCollectionsPage(limit: number, offset: number) {
  const request = useCallback(
    (signal: AbortSignal) => getCollections(limit, offset, signal),
    [limit, offset],
  );
  return useApiRequest(request);
}

export function useCollectionRecord(collectionId: string) {
  const request = useCallback(
    (signal: AbortSignal) => getCollection(collectionId, signal),
    [collectionId],
  );
  return useApiRequest(request);
}

export function useCollectionDocuments(
  collectionId: string,
  limit: number,
  offset: number,
) {
  const request = useCallback(
    (signal: AbortSignal) =>
      getCollectionDocuments(collectionId, limit, offset, signal),
    [collectionId, limit, offset],
  );
  return useApiRequest(request);
}

export function useCollectionHistory(
  collectionId: string,
  limit: number,
  offset: number,
) {
  const request = useCallback(
    (signal: AbortSignal) =>
      getCollectionHistory(collectionId, limit, offset, signal),
    [collectionId, limit, offset],
  );
  return useApiRequest(request);
}
