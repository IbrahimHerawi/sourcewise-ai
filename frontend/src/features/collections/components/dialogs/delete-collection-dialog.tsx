"use client";

import { useRef } from "react";
import { deleteCollection } from "@/features/collections/collections-api";
import type { CollectionApiRecord } from "@/features/collections/collections-api-types";
import { getApiErrorMessage } from "@/lib/api";
import { useApiMutation } from "@/hooks/use-api-request";
import { CollectionButton } from "../collection-button";
import {
  CollectionDialog,
  CollectionDialogCancel,
  CollectionDialogFooter,
} from "./collection-dialog";

type DeleteCollectionDialogProps = {
  collection: CollectionApiRecord;
  onClose: () => void;
  onDeleted: (collectionId: string) => void;
};

export function DeleteCollectionDialog({
  collection,
  onClose,
  onDeleted,
}: DeleteCollectionDialogProps) {
  const cancelButtonRef = useRef<HTMLButtonElement>(null);
  const mutation = useApiMutation((collectionId: string, signal) =>
    deleteCollection(collectionId, signal),
  );
  const submit = () => {
    void mutation
      .mutate(collection.id)
      .then(() => onDeleted(collection.id))
      .catch(() => undefined);
  };

  return (
    <CollectionDialog
      description="Deleting a collection does not delete its documents or question history. Those records remain and become unassigned."
      descriptionVariant="warning"
      footer={
        <CollectionDialogFooter>
          <CollectionDialogCancel disabled={mutation.isPending} ref={cancelButtonRef} />
          <CollectionButton
            disabled={mutation.isPending}
            onClick={submit}
            tone="danger"
            type="button"
          >
            {mutation.isPending ? "Deleting…" : "Delete collection"}
          </CollectionButton>
        </CollectionDialogFooter>
      }
      initialFocusRef={cancelButtonRef}
      onClose={onClose}
      role="alertdialog"
      title="Delete collection?"
    >
      {mutation.error ? (
        <p className="text-sm text-destructive" role="alert">
          {getApiErrorMessage(
            mutation.error,
            "The collection could not be deleted. Try again.",
          )}
        </p>
      ) : null}
    </CollectionDialog>
  );
}
