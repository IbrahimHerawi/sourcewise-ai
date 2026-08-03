"use client";

import { useCallback, useMemo } from "react";
import { listAllCollectionsApi } from "@/features/collections/collections-api";
import { useApiMutation, useApiRequest } from "@/hooks/use-api-request";
import {
  deleteDocumentApi,
  getDocumentApi,
  listDocumentsApi,
  uploadDocumentsApi,
} from "../documents-api";
import {
  mapDocumentRecord,
  mapDocumentUploadResult,
  mapPaginatedDocuments,
} from "../document-mappers";
import type { DocumentsUploadApiInput } from "../documents-api-types";
import type { DocumentCollection } from "../types";

export const documentsQueryKeys = {
  all: ["documents"] as const,
  collections: () => ["documents", "collections"] as const,
  detail: (documentId: string) =>
    ["documents", "detail", documentId] as const,
  list: ({
    collectionId,
    limit,
    offset,
  }: {
    collectionId: string | null;
    limit: number;
    offset: number;
  }) =>
    ["documents", "list", { collectionId, limit, offset }] as const,
};

export function useDocumentsList({
  collectionId,
  limit,
  offset,
}: {
  collectionId: string | null;
  limit: number;
  offset: number;
}) {
  const queryKey = useMemo(
    () => documentsQueryKeys.list({ collectionId, limit, offset }),
    [collectionId, limit, offset],
  );
  const request = useCallback(
    async (signal: AbortSignal) =>
      mapPaginatedDocuments(
        await listDocumentsApi({ collectionId, limit, offset }, signal),
      ),
    [collectionId, limit, offset],
  );
  const state = useApiRequest(request);
  return { ...state, queryKey };
}

async function loadAllCollections(
  signal: AbortSignal,
): Promise<DocumentCollection[]> {
  return (await listAllCollectionsApi(signal)).map(({ id, name }) => ({
    id,
    name,
  }));
}

export function useDocumentCollections() {
  const queryKey = useMemo(() => documentsQueryKeys.collections(), []);
  const request = useCallback(
    (signal: AbortSignal) => loadAllCollections(signal),
    [],
  );
  const state = useApiRequest(request);
  return { ...state, queryKey };
}

export function useDocumentDetails(documentId: string) {
  const queryKey = useMemo(
    () => documentsQueryKeys.detail(documentId),
    [documentId],
  );
  const request = useCallback(
    async (signal: AbortSignal) =>
      mapDocumentRecord(await getDocumentApi(documentId, signal)),
    [documentId],
  );
  const state = useApiRequest(request);
  return { ...state, queryKey };
}

export function useUploadDocumentsMutation() {
  return useApiMutation(
    async (input: DocumentsUploadApiInput, signal) =>
      mapDocumentUploadResult(await uploadDocumentsApi(input, signal)),
  );
}

export function useDeleteDocumentMutation() {
  return useApiMutation((documentId: string, signal) =>
    deleteDocumentApi(documentId, signal),
  );
}
