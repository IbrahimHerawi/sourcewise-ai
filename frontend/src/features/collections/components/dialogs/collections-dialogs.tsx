"use client";

import type { CollectionDraft } from "@/features/collections/collection-validation";
import type { CollectionsDialogState } from "@/features/collections/collection-dialog-state";
import type { Collection } from "@/features/collections/collection-types";
import { CreateCollectionDialog } from "./create-collection-dialog";
import { DeleteCollectionDialog } from "./delete-collection-dialog";
import { EditCollectionDialog } from "./edit-collection-dialog";

type CollectionsDialogsProps = {
  collections: readonly Collection[];
  dialog: CollectionsDialogState | null;
  onClose: () => void;
  onCreate: (draft: CollectionDraft) => void;
  onDelete: (collectionId: string) => void;
  onUpdate: (collectionId: string, draft: CollectionDraft) => void;
};

export function CollectionsDialogs({
  collections,
  dialog,
  onClose,
  onCreate,
  onDelete,
  onUpdate,
}: CollectionsDialogsProps) {
  if (!dialog) {
    return null;
  }

  if (dialog.type === "create") {
    return (
      <CreateCollectionDialog
        collections={collections}
        initialDescription={dialog.initialDescription}
        initialName={dialog.initialName}
        initialNameError={dialog.initialNameError}
        onClose={onClose}
        onCreate={onCreate}
      />
    );
  }

  if (dialog.type === "edit") {
    return (
      <EditCollectionDialog
        collection={dialog.collection}
        collections={collections}
        key={dialog.collection.id}
        onClose={onClose}
        onUpdate={onUpdate}
      />
    );
  }

  return (
    <DeleteCollectionDialog
      collection={dialog.collection}
      onClose={onClose}
      onDelete={onDelete}
    />
  );
}
