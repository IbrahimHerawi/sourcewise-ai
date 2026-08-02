export const COLLECTION_NAME_MAX_LENGTH = 255;
export const COLLECTION_DESCRIPTION_MAX_LENGTH = 2_000;
export const DUPLICATE_COLLECTION_NAME_ERROR =
  "That name is already in use. Capitalization doesn’t make it unique.";

export type CollectionDraft = {
  name: string;
  description: string;
};

export type CollectionFieldErrors = Partial<Record<keyof CollectionDraft, string>>;

export function validateCollectionDraft(draft: CollectionDraft): {
  errors: CollectionFieldErrors;
  isValid: boolean;
  values: CollectionDraft;
} {
  const values = {
    name: draft.name.trim(),
    description: draft.description.trim(),
  };
  const errors: CollectionFieldErrors = {};

  if (!values.name) {
    errors.name = "Enter a collection name.";
  } else if (values.name.length > COLLECTION_NAME_MAX_LENGTH) {
    errors.name = `Name must be ${COLLECTION_NAME_MAX_LENGTH} characters or fewer.`;
  }

  if (values.description.length > COLLECTION_DESCRIPTION_MAX_LENGTH) {
    errors.description =
      "Description must be 2,000 characters or fewer.";
  }

  return {
    errors,
    isValid: Object.keys(errors).length === 0,
    values,
  };
}
