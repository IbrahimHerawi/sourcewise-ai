import type { Collection } from "@/features/collections/collection-types";

let collectionSequence = 0;

export function buildCollection(
  overrides: Partial<Collection> = {},
): Collection {
  collectionSequence += 1;

  return {
    id: `collection-${collectionSequence}`,
    name: `Collection ${collectionSequence}`,
    created: "Created 1 Jan 2026, 09:00",
    updated: "Updated 1 Jan 2026, 09:00",
    ...overrides,
  };
}
