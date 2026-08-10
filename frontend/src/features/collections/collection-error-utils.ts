import {
  ApiError,
  getApiErrorMessage,
  type ApiErrorDetail,
} from "@/lib/api";
import {
  DUPLICATE_COLLECTION_NAME_ERROR,
  type CollectionFieldErrors,
} from "@/features/collections/collection-validation";

function fieldFromDetail(detail: ApiErrorDetail): keyof CollectionFieldErrors | undefined {
  const field = detail.loc.at(-1);
  return field === "name" || field === "description" ? field : undefined;
}

export function getCollectionFieldErrors(error: unknown): CollectionFieldErrors {
  if (error instanceof ApiError && error.status === 409) {
    return { name: DUPLICATE_COLLECTION_NAME_ERROR };
  }

  const errors: CollectionFieldErrors = {};
  if (error instanceof ApiError && error.status === 422) {
    error.details?.errors?.forEach((detail) => {
      const field = fieldFromDetail(detail);
      if (field && !errors[field]) errors[field] = detail.msg;
    });
  }
  return errors;
}

export function getCollectionSubmissionError(error: unknown): string | undefined {
  if (!error) return undefined;
  if (Object.keys(getCollectionFieldErrors(error)).length) return undefined;
  return getApiErrorMessage(error, "The collection could not be saved. Try again.");
}
