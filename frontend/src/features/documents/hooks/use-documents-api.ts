"use client";

import { useCallback, useMemo } from "react";
import { getCollections } from "@/features/collections/collections-api";
import { useApiMutation, useApiRequest } from "@/hooks/use-api-request";
import { invalidApiResponse } from "@/lib/api-contract";
import {
  deleteDocumentApi,
  listDocumentsApi,
  uploadDocumentsApi,
} from "../documents-api";
import {
  mapDocumentUploadResult,
  mapPaginatedDocuments,
} from "../document-mappers";
import type { DocumentsUploadApiInput } from "../documents-api-types";
import type { DocumentCollection } from "../types";

const COLLECTION_PAGE_SIZE = 100;

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
  const collections: DocumentCollection[] = [];
  let offset = 0;
  let total = 0;

  do {
    const response = await getCollections(
      COLLECTION_PAGE_SIZE,
      offset,
      signal,
    );
    total = response.total;
    if (response.offset !== offset || (response.items.length === 0 && offset < total)) {
      return invalidApiResponse("Collections");
    }
    collections.push(
      ...response.items.map(({ id, name }) => ({ id, name })),
    );
    offset += response.items.length;
  } while (offset < total);

  return collections;
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
