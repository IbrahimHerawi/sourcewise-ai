import { describe, expect, it } from "vitest";
import {
  formatResultRange,
  getPaginationItems,
} from "@/features/collections/collection-detail-utils";

describe("collection detail utilities", () => {
  it("formats bounded result ranges", () => {
    expect(formatResultRange(1, 20, 0)).toBe("0");
    expect(formatResultRange(1, 20, 47)).toBe("1–20");
    expect(formatResultRange(3, 20, 47)).toBe("41–47");
  });

  it("creates compact accessible pagination models", () => {
    expect(getPaginationItems(2, 3)).toEqual([1, 2, 3]);
    expect(getPaginationItems(2, 12)).toEqual([1, 2, 3, "ellipsis", 12]);
    expect(getPaginationItems(6, 12)).toEqual([1, "ellipsis", 6, "ellipsis", 12]);
    expect(getPaginationItems(11, 12)).toEqual([1, "ellipsis", 10, 11, 12]);
  });
});
