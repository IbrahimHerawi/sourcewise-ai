import { vi } from "vitest";

export const collectionId = "11111111-1111-4111-8111-111111111111";
export const secondCollectionId = "22222222-2222-4222-8222-222222222222";
export const documentId = "33333333-3333-4333-8333-333333333333";
export const secondDocumentId = "44444444-4444-4444-8444-444444444444";

export const collections = [
  {
    id: collectionId,
    name: "Quarterly Research",
    description: null,
    created_at: "2026-07-01T12:00:00Z",
    updated_at: "2026-07-02T12:00:00Z",
  },
  {
    id: secondCollectionId,
    name: "Customer Evidence",
    description: null,
    created_at: "2026-06-01T12:00:00Z",
    updated_at: "2026-06-02T12:00:00Z",
  },
];

export const readyDocument = {
  id: documentId,
  collection_id: collectionId,
  filename: "market-report.pdf",
  original_extension: ".pdf",
  content_type: "application/pdf",
  size_bytes: 2_048,
  status: "READY",
  error_message: null,
  created_at: "2026-07-01T12:00:00Z",
  updated_at: "2026-07-02T12:00:00Z",
};

export const secondDocument = {
  ...readyDocument,
  id: secondDocumentId,
  filename: "interviews.md",
  original_extension: ".md",
  content_type: "text/markdown",
  size_bytes: 512,
};

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

export type DocumentsApiOverride = (
  url: string,
  init?: RequestInit,
) => Response | Promise<Response> | undefined;

export function installDocumentsApi(override?: DocumentsApiOverride) {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const overridden = await override?.(url, init);
      if (overridden) return overridden;

      if (url.includes("/api/v1/collections?") && !init?.method) {
        return jsonResponse({
          items: collections,
          limit: 100,
          offset: 0,
          total: collections.length,
        });
      }
      if (url.includes("/api/v1/documents?") && !init?.method) {
        return jsonResponse({
          items: [readyDocument],
          limit: 20,
          offset: 0,
          total: 1,
        });
      }
      if (
        url.endsWith(`/api/v1/documents/${documentId}`) &&
        !init?.method
      ) {
        return jsonResponse(readyDocument);
      }
      if (
        url.endsWith(`/api/v1/documents/${secondDocumentId}`) &&
        !init?.method
      ) {
        return jsonResponse(secondDocument);
      }
      if (
        url.endsWith(`/api/v1/documents/${documentId}`) &&
        init?.method === "DELETE"
      ) {
        return new Response(null, { status: 204 });
      }
      if (
        url.endsWith("/api/v1/documents/upload") &&
        init?.method === "POST"
      ) {
        return jsonResponse(
          {
            items: [
              {
                collection_id: null,
                document_id: secondDocumentId,
                filename: "notes.txt",
                status: "PENDING",
              },
            ],
          },
          202,
        );
      }
      throw new Error(`Unexpected request: ${init?.method ?? "GET"} ${url}`);
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
