"use client";

import { useRef } from "react";
import type { CollectionDraft } from "@/features/collections/collection-validation";
import type { Collection } from "@/features/collections/collection-types";
import { CollectionDialog } from "./collection-dialog";
import { CollectionForm } from "./collection-form";

type EditCollectionDialogProps = {
  collection: Collection;
  collections: readonly Collection[];
  onClose: () => void;
  onUpdate: (collectionId: string, draft: CollectionDraft) => void;
};

export function EditCollectionDialog({
  collection,
  collections,
  onClose,
  onUpdate,
}: EditCollectionDialogProps) {
  const nameInputRef = useRef<HTMLInputElement>(null);

  return (
    <CollectionDialog
      description="Update this collection’s name and description."
      initialFocusRef={nameInputRef}
      onClose={onClose}
      title="Edit collection"
    >
      <CollectionForm
        collections={collections}
        excludeCollectionId={collection.id}
        helperVariant="counts"
        idPrefix="edit"
        initialValues={{
          name: collection.name,
          description: collection.description ?? "",
        }}
        nameInputRef={nameInputRef}
        onSubmit={(draft) => onUpdate(collection.id, draft)}
        submitLabel="Save changes"
      />
    </CollectionDialog>
  );
}
