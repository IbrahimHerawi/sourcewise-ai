"use client";

import { useState, type ChangeEvent, type FormEvent, type RefObject } from "react";
import {
  COLLECTION_DESCRIPTION_MAX_LENGTH,
  COLLECTION_NAME_MAX_LENGTH,
  validateCollectionDraft,
  type CollectionDraft,
  type CollectionFieldErrors,
} from "@/features/collections/collection-validation";
import { CollectionButton } from "../collection-button";
import styles from "../collection-dialogs.module.css";
import {
  CollectionDialogCancel,
  CollectionDialogFooter,
} from "./collection-dialog";
import { CollectionFormField } from "./collection-form-field";

type CollectionFormProps = {
  helperVariant: "limits" | "counts";
  idPrefix: "create" | "edit";
  initialErrors?: CollectionFieldErrors;
  initialValues: CollectionDraft;
  isSubmitting?: boolean;
  nameInputRef: RefObject<HTMLInputElement | null>;
  onChange?: () => void;
  onSubmit: (draft: CollectionDraft) => void;
  serverErrors?: CollectionFieldErrors;
  submissionError?: string;
  submitLabel: string;
};

export function CollectionForm({
  helperVariant,
  idPrefix,
  initialErrors = {},
  initialValues,
  isSubmitting = false,
  nameInputRef,
  onChange,
  onSubmit,
  serverErrors = {},
  submissionError,
  submitLabel,
}: CollectionFormProps) {
  const [draft, setDraft] = useState<CollectionDraft>(initialValues);
  const [errors, setErrors] = useState<CollectionFieldErrors>(initialErrors);

  const updateField =
    (field: keyof CollectionDraft) =>
    (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      setDraft((current) => ({ ...current, [field]: event.target.value }));
      setErrors((current) => ({ ...current, [field]: undefined }));
      onChange?.();
    };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const result = validateCollectionDraft(draft);

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
          disabled={isSubmitting}
          error={errors.name ?? serverErrors.name}
          helper={nameHelper}
          id={`${idPrefix}-collection-name`}
          label="Name"
          maxLength={COLLECTION_NAME_MAX_LENGTH}
          onChange={updateField("name")}
          required
          value={draft.name}
        />
        <CollectionFormField
          disabled={isSubmitting}
          error={errors.description ?? serverErrors.description}
          helper={descriptionHelper}
          id={`${idPrefix}-collection-description`}
          label="Description (optional)"
          maxLength={COLLECTION_DESCRIPTION_MAX_LENGTH}
          onChange={updateField("description")}
          type="textarea"
          value={draft.description}
        />
      </div>
      {submissionError ? (
        <p className={styles.submissionError} role="alert">
          {submissionError}
        </p>
      ) : null}
      <CollectionDialogFooter>
        <CollectionDialogCancel disabled={isSubmitting} />
        <CollectionButton disabled={isSubmitting} type="submit">
          {isSubmitting ? "Saving…" : submitLabel}
        </CollectionButton>
      </CollectionDialogFooter>
    </form>
  );
}
