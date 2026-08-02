import type { Collection } from "@/features/collections/collection-types";
import { DUPLICATE_COLLECTION_NAME_ERROR } from "@/features/collections/collection-validation";
import type { CollectionsModalPreview } from "@/features/collections/mock-collections";

export type CollectionsDialogState =
  | {
      type: "create";
      initialDescription?: string;
      initialName?: string;
      initialNameError?: string;
    }
  | { type: "edit"; collection: Collection }
  | { type: "delete"; collection: Collection };

export function createPreviewDialog(
  preview: CollectionsModalPreview | undefined,
  collections: readonly Collection[],
): CollectionsDialogState | null {
  const firstCollection = collections[0];

  if (preview === "create") {
    return {
      type: "create",
      initialName: "Customer discovery",
      initialDescription: "Add context for this collection",
    };
  }

  if (preview === "duplicate") {
    return {
      type: "create",
      initialName: "quarterly research",
      initialDescription: "Add context for this collection",
      initialNameError: DUPLICATE_COLLECTION_NAME_ERROR,
    };
  }

  if (preview === "edit" && firstCollection) {
    return { type: "edit", collection: firstCollection };
  }

  if (preview === "delete" && firstCollection) {
    return { type: "delete", collection: firstCollection };
  }

  return null;
}
