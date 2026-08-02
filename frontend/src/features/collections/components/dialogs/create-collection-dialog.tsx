"use client";

import { useRef } from "react";
import type { CollectionDraft } from "@/features/collections/collection-validation";
import type { Collection } from "@/features/collections/collection-types";
import { CollectionDialog } from "./collection-dialog";
import { CollectionForm } from "./collection-form";

type CreateCollectionDialogProps = {
  collections: readonly Collection[];
  initialDescription?: string;
  initialName?: string;
  initialNameError?: string;
  onClose: () => void;
  onCreate: (draft: CollectionDraft) => void;
};

export function CreateCollectionDialog({
  collections,
  initialDescription = "",
  initialName = "",
  initialNameError,
  onClose,
  onCreate,
}: CreateCollectionDialogProps) {
  const nameInputRef = useRef<HTMLInputElement>(null);

  return (
    <CollectionDialog
      description="Create a collection with a name and optional description."
      initialFocusRef={nameInputRef}
      onClose={onClose}
      title="Create collection"
    >
      <CollectionForm
        collections={collections}
        helperVariant="limits"
        idPrefix="create"
        initialErrors={initialNameError ? { name: initialNameError } : undefined}
        initialValues={{ name: initialName, description: initialDescription }}
        nameInputRef={nameInputRef}
        onSubmit={onCreate}
        submitLabel="Create Collection"
      />
    </CollectionDialog>
  );
}
