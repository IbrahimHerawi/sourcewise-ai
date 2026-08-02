import { describe, expect, it } from "vitest";
import {
  COLLECTION_DESCRIPTION_MAX_LENGTH,
  COLLECTION_NAME_MAX_LENGTH,
  validateCollectionDraft,
} from "@/features/collections/collection-validation";

describe("validateCollectionDraft", () => {
  it("trims values and requires a non-empty name", () => {
    const result = validateCollectionDraft({ name: "   ", description: "  Context  " });

    expect(result.isValid).toBe(false);
    expect(result.errors.name).toBe("Enter a collection name.");
    expect(result.values).toEqual({ name: "", description: "Context" });
  });

  it("enforces the backend-confirmed name and description limits", () => {
    const result = validateCollectionDraft({
      name: "n".repeat(COLLECTION_NAME_MAX_LENGTH + 1),
      description: "d".repeat(COLLECTION_DESCRIPTION_MAX_LENGTH + 1),
    });

    expect(result.errors.name).toBe("Name must be 255 characters or fewer.");
    expect(result.errors.description).toBe("Description must be 2,000 characters or fewer.");
  });

  it("does not infer duplicate-name state from a paginated frontend dataset", () => {
    const result = validateCollectionDraft({
      name: "Quarterly Research",
      description: "Updated",
    });

    expect(result.isValid).toBe(true);
  });
});
