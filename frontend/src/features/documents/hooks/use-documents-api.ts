"use client";

import { useCallback, useMemo } from "react";
import { listAllCollectionsApi } from "@/features/collections/collections-api";
import { useApiMutation, useApiRequest } from "@/hooks/use-api-request";
import {
  deleteDocumentApi,
  getDocumentApi,
  listAllDocumentsApi,
  listDocumentsApi,
  uploadDocumentsApi,
} from "../documents-api";
import {
  mapDocumentRecord,
  mapDocumentUploadResult,
  mapPaginatedDocuments,
} from "../document-mappers";
import type { DocumentsUploadApiInput } from "../documents-api-types";
import type { SupportedDocumentExtension } from "../file-validation";
import type {
  DocumentCollection,
  PaginatedDocuments,
} from "../types";

export const documentsQueryKeys = {
  all: ["documents"] as const,
  collections: () => ["documents", "collections"] as const,
  detail: (documentId: string) =>
    ["documents", "detail", documentId] as const,
  list: ({
    collectionId,
    fileType = null,
    limit,
    offset,
  }: {
    collectionId: string | null;
    fileType?: SupportedDocumentExtension | null;
    limit: number;
    offset: number;
  }) => [
    "documents",
    "list",
    fileType === null
      ? { collectionId, limit, offset }
      : { collectionId, fileType, limit, offset },
  ] as const,
};

export function useDocumentsList({
  collectionId,
  fileType = null,
  limit,
  offset,
}: {
  collectionId: string | null;
  fileType?: SupportedDocumentExtension | null;
  limit: number;
  offset: number;
}) {
  const queryKey = useMemo(
    () =>
      documentsQueryKeys.list({
        collectionId,
        fileType,
        limit,
        offset,
      }),
    [collectionId, fileType, limit, offset],
  );
  const request = useCallback(
    async (signal: AbortSignal): Promise<PaginatedDocuments> => {
      if (fileType === null) {
        return mapPaginatedDocuments(
          await listDocumentsApi({ collectionId, limit, offset }, signal),
        );
      }

      const matchingDocuments = (await listAllDocumentsApi(signal))
        .map(mapDocumentRecord)
        .filter(
          (document) =>
            document.original_extension.toLowerCase() === fileType &&
            (collectionId === null ||
              document.collection_id === collectionId),
        );

      return {
        items: matchingDocuments.slice(offset, offset + limit),
        limit,
        offset,
        total: matchingDocuments.length,
      };
    },
    [collectionId, fileType, limit, offset],
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
