import type { CollectionApiRecord } from "@/features/collections/collections-api-types";

export type CollectionsDialogState =
  | {
      type: "create";
      collection?: undefined;
    }
  | { type: "edit"; collection: CollectionApiRecord }
  | { type: "delete"; collection: CollectionApiRecord };
