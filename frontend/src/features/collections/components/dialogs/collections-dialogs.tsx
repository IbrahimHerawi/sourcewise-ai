"use client";

import type { CollectionsDialogState } from "@/features/collections/collection-dialog-state";
import type { CollectionApiRecord } from "@/features/collections/collections-api-types";
import { CreateCollectionDialog } from "./create-collection-dialog";
import { DeleteCollectionDialog } from "./delete-collection-dialog";
import { EditCollectionDialog } from "./edit-collection-dialog";

type CollectionsDialogsProps = {
  dialog: CollectionsDialogState | null;
  onClose: () => void;
  onCreated: (collection: CollectionApiRecord) => void;
  onDeleted: (collectionId: string) => void;
  onUpdated: (collection: CollectionApiRecord) => void;
};

export function CollectionsDialogs({
  dialog,
  onClose,
  onCreated,
  onDeleted,
  onUpdated,
}: CollectionsDialogsProps) {
  if (!dialog) {
    return null;
  }

  if (dialog.type === "create") {
    return (
      <CreateCollectionDialog
        onClose={onClose}
        onCreated={onCreated}
      />
    );
  }

  if (dialog.type === "edit") {
    return (
      <EditCollectionDialog
        collection={dialog.collection}
        key={dialog.collection.id}
        onClose={onClose}
        onUpdated={onUpdated}
      />
    );
  }

  return (
    <DeleteCollectionDialog
      collection={dialog.collection}
      onClose={onClose}
      onDeleted={onDeleted}
    />
  );
}
