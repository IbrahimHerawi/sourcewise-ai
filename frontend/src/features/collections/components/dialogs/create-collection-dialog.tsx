"use client";

import { useRef } from "react";
import { createCollection } from "@/features/collections/collections-api";
import type { CollectionApiRecord } from "@/features/collections/collections-api-types";
import type { CollectionDraft } from "@/features/collections/collection-validation";
import {
  getCollectionFieldErrors,
  getCollectionSubmissionError,
} from "@/features/collections/collection-error-utils";
import { useApiMutation } from "@/hooks/use-api-request";
import { CollectionDialog } from "./collection-dialog";
import { CollectionForm } from "./collection-form";

type CreateCollectionDialogProps = {
  onClose: () => void;
  onCreated: (collection: CollectionApiRecord) => void;
};

export function CreateCollectionDialog({
  onClose,
  onCreated,
}: CreateCollectionDialogProps) {
  const nameInputRef = useRef<HTMLInputElement>(null);
  const mutation = useApiMutation(
    (draft: CollectionDraft, signal) =>
      createCollection(
        { name: draft.name, description: draft.description || null },
        signal,
      ),
  );
  const submit = (draft: CollectionDraft) => {
    void mutation.mutate(draft).then(onCreated).catch(() => undefined);
  };

  return (
    <CollectionDialog
      description="Create a collection with a name and optional description."
      initialFocusRef={nameInputRef}
      onClose={onClose}
      title="Create collection"
    >
      <CollectionForm
        helperVariant="limits"
        idPrefix="create"
        initialValues={{ name: "", description: "" }}
        isSubmitting={mutation.isPending}
        nameInputRef={nameInputRef}
        onChange={mutation.reset}
        onSubmit={submit}
        serverErrors={getCollectionFieldErrors(mutation.error)}
        submissionError={getCollectionSubmissionError(mutation.error)}
        submitLabel="Create Collection"
      />
    </CollectionDialog>
  );
}
