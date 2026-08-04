import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";
import { installTestAuthSession } from "@test/helpers/auth";
import {
  deleteDocumentApi,
  getDocumentApi,
  listDocumentsApi,
  uploadDocumentsApi,
} from "@/features/documents/documents-api";
import {
  mapDocumentRecord,
  mapDocumentStatus,
} from "@/features/documents/document-mappers";
import { DOCUMENT_STATUS_PRESENTATION } from "@/features/documents/document-status";
import { documentsQueryKeys } from "@/features/documents/hooks/use-documents-api";
import {
  collectionId,
  documentId,
  installDocumentsApi,
  jsonResponse,
  readyDocument,
} from "../test-data";

describe("Documents API contract", () => {
  beforeEach(() => {
    installTestAuthSession();
  });

  it("uses the real list query contract and authenticated API client", async () => {
    const fetchMock = installDocumentsApi((url) => {
      if (url.includes("/documents?")) {
        return jsonResponse({
          items: [],
          limit: 20,
          offset: 40,
          total: 40,
        });
      }
    });

    const response = await listDocumentsApi({
      collectionId,
      limit: 20,
      offset: 40,
    });

    expect(response.items).toEqual([]);
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/documents?limit=20&offset=40&collection_id=${collectionId}`,
      expect.objectContaining({ signal: undefined }),
    );
    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers);
    expect(headers.get("Authorization")).toBe("Bearer test-token");
  });

  it("rejects page metadata that does not match the requested page", async () => {
    installDocumentsApi((url) => {
      if (url.includes("/documents?")) {
        return jsonResponse({
          items: [readyDocument],
          limit: 20,
          offset: 0,
          total: 1,
        });
      }
    });

    await expect(
      listDocumentsApi({ collectionId: null, limit: 20, offset: 20 }),
    ).rejects.toMatchObject({ code: "invalid_response" });
  });

  it("validates details and rejects unexpected response shapes", async () => {
    installDocumentsApi((url) => {
      if (url.endsWith(`/documents/${documentId}`)) {
        return jsonResponse({ ...readyDocument, size_bytes: "2048" });
      }
    });

    await expect(getDocumentApi(documentId)).rejects.toMatchObject({
      code: "invalid_response",
    });
  });

  it("uses multipart field names and optional collection assignment", async () => {
    const fetchMock = installDocumentsApi((url, init) => {
      if (url.endsWith("/documents/upload") && init?.method === "POST") {
        return jsonResponse(
          {
            items: [
              {
                collection_id: collectionId,
                document_id: documentId,
                filename: "notes.txt",
                status: "PENDING",
              },
            ],
          },
          202,
        );
      }
    });
    const upload = new File(["notes"], "notes.txt", { type: "text/plain" });

    await uploadDocumentsApi({ collectionId, files: [upload] });

    const post = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).endsWith("/documents/upload") && init?.method === "POST",
    );
    const body = post?.[1]?.body;
    expect(body).toBeInstanceOf(FormData);
    expect((body as FormData).getAll("files")).toEqual([upload]);
    expect((body as FormData).get("collection_id")).toBe(collectionId);
    expect(new Headers(post?.[1]?.headers).has("Content-Type")).toBe(false);
  });

  it("rejects partial upload confirmations because the backend is all-or-nothing", async () => {
    installDocumentsApi((url, init) => {
      if (url.endsWith("/documents/upload") && init?.method === "POST") {
        return jsonResponse({ items: [] }, 202);
      }
    });

    await expect(
      uploadDocumentsApi({
        collectionId: null,
        files: [new File(["a"], "one.txt")],
      }),
    ).rejects.toBeInstanceOf(ApiError);
  });

  it("submits the real document id for deletion", async () => {
    const fetchMock = installDocumentsApi();

    await deleteDocumentApi(documentId);

    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/documents/${documentId}`,
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it.each(["PENDING", "PROCESSING", "READY", "FAILED"] as const)(
    "maps the backend %s status",
    (status) => {
      expect(mapDocumentStatus(status)).toBe(status);
      expect(DOCUMENT_STATUS_PRESENTATION[status].label).toBeTruthy();
    },
  );

  it("maps future statuses safely without discarding the document", () => {
    expect(mapDocumentStatus("ARCHIVED")).toBe("UNKNOWN");
    expect(
      mapDocumentRecord({ ...readyDocument, status: "ARCHIVED" }).status,
    ).toBe("UNKNOWN");
    expect(DOCUMENT_STATUS_PRESENTATION.UNKNOWN.pollingRequired).toBe(false);
    expect(DOCUMENT_STATUS_PRESENTATION.UNKNOWN.tone).toBe("unknown");
  });

  it("builds stable keys containing pagination, filter, and detail identity", () => {
    expect(
      documentsQueryKeys.list({ collectionId, limit: 20, offset: 40 }),
    ).toEqual([
      "documents",
      "list",
      { collectionId, limit: 20, offset: 40 },
    ]);
    expect(documentsQueryKeys.detail(documentId)).toEqual([
      "documents",
      "detail",
      documentId,
    ]);
    expect(documentsQueryKeys.collections()).toEqual([
      "documents",
      "collections",
    ]);
  });
});
