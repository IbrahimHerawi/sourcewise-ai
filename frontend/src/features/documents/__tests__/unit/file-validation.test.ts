import { describe, expect, it } from "vitest";
import {
  createUploadQueue,
  DOCUMENT_UPLOAD_LIMITS,
  getUploadValidationMessage,
  hasBlockingUploadError,
} from "@/features/documents/file-validation";

function file(name: string, size = 16): File {
  return new File([new Uint8Array(size)], name);
}

describe("document upload validation", () => {
  it("accepts the backend-supported extensions case-insensitively", () => {
    const queue = createUploadQueue([
      file("report.PDF"),
      file("notes.txt"),
      file("readme.MD"),
    ]);

    expect(queue.map((item) => item.status)).toEqual([
      "valid",
      "valid",
      "valid",
    ]);
    expect(hasBlockingUploadError(queue)).toBe(false);
  });

  it("rejects unsupported, empty, oversized, and excess files", () => {
    const unsupported = createUploadQueue([file("data.csv")]);
    const empty = createUploadQueue([new File([], "empty.txt")]);
    const oversized = createUploadQueue([
      file("large.pdf", DOCUMENT_UPLOAD_LIMITS.maxFileBytes + 1),
    ]);
    const tooMany = createUploadQueue([
      file("one.txt"),
      file("two.txt"),
      file("three.txt"),
      file("four.txt"),
    ]);

    expect(unsupported[0].status).toBe("invalid-type");
    expect(empty[0].status).toBe("empty-file");
    expect(oversized[0].status).toBe("too-large");
    expect(tooMany[3].status).toBe("too-many-files");
    expect(getUploadValidationMessage(tooMany)).toMatch(/Select 1–3/);
    expect(hasBlockingUploadError(tooMany)).toBe(true);
  });

  it("does not invent duplicate-file rejection", () => {
    const duplicate = file("same.txt");
    const queue = createUploadQueue([duplicate, duplicate]);

    expect(queue).toHaveLength(2);
    expect(queue[0].id).not.toBe(queue[1].id);
    expect(queue.every((item) => item.status === "valid")).toBe(true);
  });
});
