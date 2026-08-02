import type {
  Collection,
  CollectionsViewState,
} from "@/features/collections/collection-types";

export type CollectionsPreview =
  | "populated"
  | "loading"
  | "empty"
  | "error"
  | "not-found";

export type CollectionsModalPreview =
  | "create"
  | "duplicate"
  | "edit"
  | "delete";

export const mockCollections: readonly Collection[] = [
  {
    id: "quarterly-research",
    name: "Quarterly Research",
    description:
      "Market notes, reports, and supporting source documents for the current quarter.",
    created: "Created 20 Jul 2026, 14:08",
    updated: "Updated 20 Jul 2026, 14:35",
  },
  {
    id: "customer-discovery",
    name: "Customer Discovery",
    description:
      "Interview transcripts, personas, and evidence for product discovery.",
    created: "Created 19 Jul 2026, 10:12",
    updated: "Updated 20 Jul 2026, 09:04",
  },
  {
    id: "policy-compliance",
    name: "Policy & Compliance",
    description:
      "Policy references and review material for the governance team.",
    created: "Created 16 Jul 2026, 16:40",
    updated: "Updated 18 Jul 2026, 11:22",
  },
  {
    id: "engineering-notes",
    name: "Engineering Notes",
    created: "Created 12 Jul 2026, 08:20",
    updated: "Updated 17 Jul 2026, 15:18",
  },
];

export function createMockCollectionsState(
  preview: CollectionsPreview,
): CollectionsViewState {
  if (preview === "loading") {
    return { status: "loading" };
  }

  if (preview === "error") {
    return { status: "error" };
  }

  if (preview === "not-found") {
    return { status: "not-found" };
  }

  return {
    status: "success",
    collections: preview === "empty" ? [] : [...mockCollections],
  };
}

export function parseCollectionsPreview(value: unknown): CollectionsPreview {
  return value === "loading" ||
    value === "empty" ||
    value === "error" ||
    value === "not-found"
    ? value
    : "populated";
}

export function parseCollectionsModalPreview(
  value: unknown,
): CollectionsModalPreview | undefined {
  return value === "create" ||
    value === "duplicate" ||
    value === "edit" ||
    value === "delete"
    ? value
    : undefined;
}
