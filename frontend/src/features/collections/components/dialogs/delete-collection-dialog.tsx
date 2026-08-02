"use client";

import { useRef } from "react";
import type { Collection } from "@/features/collections/collection-types";
import { CollectionButton } from "../collection-button";
import {
  CollectionDialog,
  CollectionDialogCancel,
  CollectionDialogFooter,
} from "./collection-dialog";

type DeleteCollectionDialogProps = {
  collection: Collection;
  onClose: () => void;
  onDelete: (collectionId: string) => void;
};

export function DeleteCollectionDialog({
  collection,
  onClose,
  onDelete,
}: DeleteCollectionDialogProps) {
  const cancelButtonRef = useRef<HTMLButtonElement>(null);

  return (
    <CollectionDialog
      description="Deleting a collection does not delete its documents or question history. Those records remain and become unassigned."
      descriptionVariant="warning"
      initialFocusRef={cancelButtonRef}
      onClose={onClose}
      role="alertdialog"
      title="Delete collection?"
    >
      <CollectionDialogFooter>
        <CollectionDialogCancel ref={cancelButtonRef} />
        <CollectionButton
          onClick={() => onDelete(collection.id)}
          tone="danger"
          type="button"
        >
          Delete collection
        </CollectionButton>
      </CollectionDialogFooter>
    </CollectionDialog>
  );
}
