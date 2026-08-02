"use client";

import { useState, type ChangeEvent, type FormEvent, type RefObject } from "react";
import {
  COLLECTION_DESCRIPTION_MAX_LENGTH,
  COLLECTION_NAME_MAX_LENGTH,
  validateCollectionDraft,
  type CollectionDraft,
  type CollectionFieldErrors,
} from "@/features/collections/collection-validation";
import type { Collection } from "@/features/collections/collection-types";
import { CollectionButton } from "../collection-button";
import styles from "../collection-dialogs.module.css";
import {
  CollectionDialogCancel,
  CollectionDialogFooter,
} from "./collection-dialog";
import { CollectionFormField } from "./collection-form-field";

type CollectionFormProps = {
  collections: readonly Collection[];
  excludeCollectionId?: string;
  helperVariant: "limits" | "counts";
  idPrefix: "create" | "edit";
  initialErrors?: CollectionFieldErrors;
  initialValues: CollectionDraft;
  nameInputRef: RefObject<HTMLInputElement | null>;
  onSubmit: (draft: CollectionDraft) => void;
  submitLabel: string;
};

export function CollectionForm({
  collections,
  excludeCollectionId,
  helperVariant,
  idPrefix,
  initialErrors = {},
  initialValues,
  nameInputRef,
  onSubmit,
  submitLabel,
}: CollectionFormProps) {
  const [draft, setDraft] = useState<CollectionDraft>(initialValues);
  const [errors, setErrors] = useState<CollectionFieldErrors>(initialErrors);

  const updateField =
    (field: keyof CollectionDraft) =>
    (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      setDraft((current) => ({ ...current, [field]: event.target.value }));
      setErrors((current) => ({ ...current, [field]: undefined }));
    };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const result = validateCollectionDraft(draft, {
      collections,
      excludeCollectionId,
    });

    if (!result.isValid) {
      setErrors(result.errors);
      return;
    }

    onSubmit(result.values);
  };

  const showCounts = helperVariant === "counts";
  const nameHelper = showCounts
    ? `${draft.name.length.toLocaleString("en-US")} / ${COLLECTION_NAME_MAX_LENGTH}`
    : `1–${COLLECTION_NAME_MAX_LENGTH} characters`;
  const descriptionHelper = showCounts
    ? `${draft.description.length.toLocaleString("en-US")} / ${COLLECTION_DESCRIPTION_MAX_LENGTH.toLocaleString("en-US")}`
    : `Optional · up to ${COLLECTION_DESCRIPTION_MAX_LENGTH.toLocaleString("en-US")} characters`;

  return (
    <form className={styles.form} noValidate onSubmit={submit}>
      <div className={styles.body}>
        <CollectionFormField
          controlRef={nameInputRef}
          error={errors.name}
          helper={nameHelper}
          id={`${idPrefix}-collection-name`}
          label="Name"
          maxLength={COLLECTION_NAME_MAX_LENGTH}
          onChange={updateField("name")}
          required
          value={draft.name}
        />
        <CollectionFormField
          error={errors.description}
          helper={descriptionHelper}
          id={`${idPrefix}-collection-description`}
          label="Description (optional)"
          maxLength={COLLECTION_DESCRIPTION_MAX_LENGTH}
          onChange={updateField("description")}
          type="textarea"
          value={draft.description}
        />
      </div>
      <CollectionDialogFooter>
        <CollectionDialogCancel />
        <CollectionButton type="submit">{submitLabel}</CollectionButton>
      </CollectionDialogFooter>
    </form>
  );
}
