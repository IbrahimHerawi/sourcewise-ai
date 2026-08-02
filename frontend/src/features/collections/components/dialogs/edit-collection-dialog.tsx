"use client";

import { useRef } from "react";
import { updateCollection } from "@/features/collections/collections-api";
import type { CollectionApiRecord } from "@/features/collections/collections-api-types";
import type { CollectionDraft } from "@/features/collections/collection-validation";
import {
  getCollectionFieldErrors,
  getCollectionSubmissionError,
} from "@/features/collections/collection-error-utils";
import { useApiMutation } from "@/hooks/use-api-request";
import { CollectionDialog } from "./collection-dialog";
import { CollectionForm } from "./collection-form";

type EditCollectionDialogProps = {
  collection: CollectionApiRecord;
  onClose: () => void;
  onUpdated: (collection: CollectionApiRecord) => void;
};

export function EditCollectionDialog({
  collection,
  onClose,
  onUpdated,
}: EditCollectionDialogProps) {
  const nameInputRef = useRef<HTMLInputElement>(null);
  const mutation = useApiMutation(
    (draft: CollectionDraft, signal) => {
      const changes: { name?: string; description?: string | null } = {};
      if (draft.name !== collection.name) changes.name = draft.name;
      if (draft.description !== (collection.description ?? "")) {
        changes.description = draft.description || null;
      }
      if (!Object.keys(changes).length) return Promise.resolve(collection);
      return updateCollection(collection.id, changes, signal);
    },
  );
  const submit = (draft: CollectionDraft) => {
    void mutation.mutate(draft).then(onUpdated).catch(() => undefined);
  };

  return (
    <CollectionDialog
      description="Update this collection’s name and description."
      initialFocusRef={nameInputRef}
      onClose={onClose}
      title="Edit collection"
    >
      <CollectionForm
        helperVariant="counts"
        idPrefix="edit"
        initialValues={{
          name: collection.name,
          description: collection.description ?? "",
        }}
        isSubmitting={mutation.isPending}
        nameInputRef={nameInputRef}
        onChange={mutation.reset}
        onSubmit={submit}
        serverErrors={getCollectionFieldErrors(mutation.error)}
        submissionError={getCollectionSubmissionError(mutation.error)}
        submitLabel="Save changes"
      />
    </CollectionDialog>
  );
}
