import { apiRequest } from "@/lib/api";
import {
  invalidApiResponse,
  readApiArray,
  readApiDateTime,
  readApiInteger,
  readApiNullableString,
  readApiObject,
  readApiString,
  readApiUuid,
} from "@/lib/api-contract";
import type {
  CollectionApiRecord,
  CollectionCreateInput,
  CollectionUpdateInput,
  PaginatedResponse,
} from "@/features/collections/collections-api-types";

const COLLECTIONS_CONTRACT = "Collections";
const MAX_COLLECTION_PAGE_SIZE = 100;

function paginationQuery(limit: number, offset: number) {
  return new URLSearchParams({ limit: String(limit), offset: String(offset) });
}

function parseCollection(value: unknown): CollectionApiRecord {
  const record = readApiObject(value, COLLECTIONS_CONTRACT);
  return {
    id: readApiUuid(record, "id", COLLECTIONS_CONTRACT),
    name: readApiString(record, "name", COLLECTIONS_CONTRACT),
    description: readApiNullableString(
      record,
      "description",
      COLLECTIONS_CONTRACT,
    ),
    created_at: readApiDateTime(record, "created_at", COLLECTIONS_CONTRACT),
    updated_at: readApiDateTime(record, "updated_at", COLLECTIONS_CONTRACT),
  };
}

function parseCollectionPage(
  value: unknown,
): PaginatedResponse<CollectionApiRecord> {
  const record = readApiObject(value, COLLECTIONS_CONTRACT);
  const limit = readApiInteger(record, "limit", COLLECTIONS_CONTRACT, 1);
  const offset = readApiInteger(record, "offset", COLLECTIONS_CONTRACT);
  const total = readApiInteger(record, "total", COLLECTIONS_CONTRACT);
  const items = readApiArray(record, "items", COLLECTIONS_CONTRACT).map(
    parseCollection,
  );
  if (
    items.length > limit ||
    items.length > Math.max(0, total - offset)
  ) {
    return invalidApiResponse(COLLECTIONS_CONTRACT);
  }
  return { items, limit, offset, total };
}

export async function getCollections(
  limit: number,
  offset: number,
  signal?: AbortSignal,
) {
  const response = await apiRequest<unknown>(
    `/collections?${paginationQuery(limit, offset)}`,
    { signal },
  );
  return parseCollectionPage(response);
}

export async function listAllCollectionsApi(
  signal?: AbortSignal,
): Promise<CollectionApiRecord[]> {
  const collections: CollectionApiRecord[] = [];
  const collectionIds = new Set<string>();
  let expectedTotal: number | undefined;
  let offset = 0;
  let total = 0;

  do {
    const page = await getCollections(MAX_COLLECTION_PAGE_SIZE, offset, signal);
    total = page.total;
    expectedTotal ??= total;
    if (
      page.offset !== offset ||
      total !== expectedTotal ||
      (page.items.length === 0 && offset < total) ||
      page.items.some(({ id }) => collectionIds.has(id))
    ) {
      return invalidApiResponse(COLLECTIONS_CONTRACT);
    }
    collections.push(...page.items);
    page.items.forEach(({ id }) => collectionIds.add(id));
    offset += page.items.length;
  } while (offset < total);

  return collections;
}

export async function getCollection(
  collectionId: string,
  signal?: AbortSignal,
) {
  const response = await apiRequest<unknown>(`/collections/${collectionId}`, {
    signal,
  });
  return parseCollection(response);
}

export async function createCollection(
  input: CollectionCreateInput,
  signal?: AbortSignal,
) {
  const response = await apiRequest<unknown>("/collections", {
    method: "POST",
    body: JSON.stringify(input),
    signal,
  });
  return parseCollection(response);
}

export async function updateCollection(
  collectionId: string,
  input: CollectionUpdateInput,
  signal?: AbortSignal,
) {
  const response = await apiRequest<unknown>(`/collections/${collectionId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
    signal,
  });
  return parseCollection(response);
}

export function deleteCollection(collectionId: string, signal?: AbortSignal) {
  return apiRequest<Record<string, never>>(`/collections/${collectionId}`, {
    method: "DELETE",
    signal,
  });
}
