import { describe, expect, it } from "vitest";
import {
  COLLECTION_DESCRIPTION_MAX_LENGTH,
  COLLECTION_NAME_MAX_LENGTH,
  DUPLICATE_COLLECTION_NAME_ERROR,
  validateCollectionDraft,
} from "@/features/collections/collection-validation";
import { buildCollection } from "@/features/collections/__tests__/factories/collection.factory";

const existingCollections = [
  buildCollection({
    id: "quarterly-research",
    name: "Quarterly Research",
  }),
];

describe("validateCollectionDraft", () => {
  it("trims values and requires a non-empty name", () => {
    const empty = validateCollectionDraft(
      { name: "   ", description: "  Context  " },
      { collections: existingCollections },
    );

    expect(empty.isValid).toBe(false);
    expect(empty.errors.name).toBe("Enter a collection name.");
    expect(empty.values).toEqual({ name: "", description: "Context" });
  });

  it("enforces name and description limits", () => {
    const result = validateCollectionDraft(
      {
        name: "n".repeat(COLLECTION_NAME_MAX_LENGTH + 1),
        description: "d".repeat(COLLECTION_DESCRIPTION_MAX_LENGTH + 1),
      },
      { collections: existingCollections },
    );

    expect(result.errors.name).toBe("Name must be 255 characters or fewer.");
    expect(result.errors.description).toBe(
      "Description must be 2,000 characters or fewer.",
    );
  });

  it("treats names as case-insensitively unique after trimming", () => {
    const result = validateCollectionDraft(
      { name: "  quarterly research  ", description: "" },
      { collections: existingCollections },
    );

    expect(result.errors.name).toBe(DUPLICATE_COLLECTION_NAME_ERROR);
  });

  it("excludes the collection currently being edited from duplicate checks", () => {
    const result = validateCollectionDraft(
      { name: "quarterly research", description: "Updated" },
      {
        collections: existingCollections,
        excludeCollectionId: "quarterly-research",
      },
    );

    expect(result.isValid).toBe(true);
    expect(result.values.name).toBe("quarterly research");
  });
});
