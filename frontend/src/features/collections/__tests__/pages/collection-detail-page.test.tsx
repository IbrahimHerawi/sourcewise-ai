import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CollectionDetailPage } from "@/features/collections/components/detail/collection-detail-page";
import { renderWithDashboardHeader } from "@test/render/render-with-dashboard-header";

const { logoutMock, pushMock, replaceMock } = vi.hoisted(() => ({
  logoutMock: vi.fn(),
  pushMock: vi.fn(),
  replaceMock: vi.fn(),
}));

vi.mock("@/hooks/use-auth", () => ({ useAuth: () => ({ logout: logoutMock }) }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
  usePathname: () => "/dashboard/collections/11111111-1111-4111-8111-111111111111",
  useSearchParams: () => new URLSearchParams(),
}));

const collectionId = "11111111-1111-4111-8111-111111111111";
const documentId = "22222222-2222-4222-8222-222222222222";
const questionId = "33333333-3333-4333-8333-333333333333";
const collection = {
  id: collectionId,
  name: "Quarterly Research",
  description: "Current-quarter evidence.",
  created_at: "2026-07-01T12:00:00Z",
  updated_at: "2026-07-02T12:00:00Z",
};
const documents = [
  {
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
  },
  {
    id: "44444444-4444-4444-8444-444444444444",
    collection_id: collectionId,
    filename: "interviews.md",
    original_extension: ".md",
    content_type: "text/markdown",
    size_bytes: 512,
    status: "PENDING",
    error_message: null,
    created_at: "2026-07-01T12:00:00Z",
    updated_at: "2026-07-02T12:00:00Z",
  },
  {
    id: "55555555-5555-4555-8555-555555555555",
    collection_id: collectionId,
    filename: "customer-notes.txt",
    original_extension: ".txt",
    content_type: "text/plain",
    size_bytes: 256,
    status: "PROCESSING",
    error_message: null,
    created_at: "2026-07-01T12:00:00Z",
    updated_at: "2026-07-02T12:00:00Z",
  },
  {
    id: "66666666-6666-4666-8666-666666666666",
    collection_id: collectionId,
    filename: "scanned-report.pdf",
    original_extension: ".pdf",
    content_type: "application/pdf",
    size_bytes: 4_096,
    status: "FAILED",
    error_message: "Document contains no extractable text.",
    created_at: "2026-07-01T12:00:00Z",
    updated_at: "2026-07-02T12:00:00Z",
  },
] as const;
const historyItem = {
  question_id: questionId,
  collection_id: collectionId,
  question: "What changed this quarter?",
  answer: "Revenue increased while churn declined.",
  citations: [
    {
      rank: 1,
      document_id: documentId,
      document_filename: "market-report.pdf",
      chunk_id: "chunk-1",
      chunk_index: 7,
      excerpt: "Revenue grew by twelve percent.",
      distance: 0.12,
    },
  ],
  created_at: "2026-07-02T12:00:00Z",
  provider: "openai",
  model: "gpt-test",
} as const;

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

function installDetailApi(overrides?: (url: string, init?: RequestInit) => Response | undefined) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const overridden = overrides?.(url, init);
    if (overridden) return overridden;
    if (url.endsWith(`/api/v1/collections/${collectionId}`) && !init?.method) return jsonResponse(collection);
    if (url.includes("/api/v1/documents?") && !init?.method) {
      return jsonResponse({ items: documents, limit: 20, offset: 0, total: documents.length });
    }
    if (url.includes("/api/v1/questions/history?") && !init?.method) {
      return jsonResponse({ items: [historyItem], limit: 20, offset: 0, total: 1 });
    }
    if (url.endsWith(`/api/v1/documents/${documentId}`) && !init?.method) return jsonResponse(documents[0]);
    if (url.endsWith(`/api/v1/questions/history/${questionId}`) && !init?.method) return jsonResponse(historyItem);
    if (url.endsWith(`/api/v1/questions/history/${questionId}`) && init?.method === "DELETE") return new Response(null, { status: 204 });
    if (url.endsWith(`/api/v1/documents/${documentId}`) && init?.method === "DELETE") return new Response(null, { status: 204 });
    if (url.endsWith("/api/v1/documents/upload") && init?.method === "POST") {
      return jsonResponse({ items: [{ document_id: documentId, filename: "notes.txt", collection_id: collectionId, status: "PENDING" }] }, 202);
    }
    throw new Error(`Unexpected request: ${init?.method ?? "GET"} ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("CollectionDetailPage API integration", () => {
  beforeEach(() => {
    localStorage.setItem("sourcewise_token", "test-token");
    logoutMock.mockReset();
    pushMock.mockReset();
    replaceMock.mockReset();
  });

  it("loads detail, documents, and history counts and renders only exact statuses", async () => {
    installDetailApi();
    renderWithDashboardHeader(<CollectionDetailPage collectionId={collectionId} />);

    expect(screen.getByText("Loading collection details")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: collection.name })).toBeVisible();
    const summary = screen.getByRole("region", { name: "Collection summary" });
    expect(within(summary).getByText("4")).toBeVisible();
    expect(within(summary).getByText("1")).toBeVisible();
    expect(screen.getByText("Ready")).toBeVisible();
    expect(screen.getByText("Pending")).toBeVisible();
    expect(screen.getByText("Processing")).toBeVisible();
    expect(screen.getByText("Failed")).toBeVisible();
    expect(screen.getByText("Document contains no extractable text.")).toBeVisible();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask this collection" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: /download|preview|remove from|reassign|cancel processing|retry processing/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/ready documents|processing must finish|pages/i)).not.toBeInTheDocument();
  });

  it("uses collection-scoped history and displays citation snapshots without invented pages", async () => {
    const user = userEvent.setup();
    installDetailApi();
    renderWithDashboardHeader(<CollectionDetailPage collectionId={collectionId} />);
    await screen.findByRole("heading", { name: collection.name });

    await user.click(screen.getByRole("tab", { name: "History 1" }));
    expect(replaceMock).toHaveBeenCalledWith(
      `/dashboard/collections/${collectionId}?tab=history`,
      { scroll: false },
    );
    await user.click(screen.getByRole("button", { name: historyItem.question }));
    expect(await screen.findByRole("dialog", { name: "Question details" })).toBeVisible();
    expect(screen.getByText(historyItem.citations[0].excerpt)).toBeVisible();
    expect(screen.getByText("Chunk 7")).toBeVisible();
    expect(screen.queryByText(/page 8/i)).not.toBeInTheDocument();
  });

  it("uploads directly to the collection with the backend multipart contract", async () => {
    const user = userEvent.setup();
    const fetchMock = installDetailApi();
    renderWithDashboardHeader(<CollectionDetailPage collectionId={collectionId} />);
    await screen.findByRole("heading", { name: collection.name });

    await user.click(screen.getAllByRole("button", { name: "Upload to collection" })[0]);
    const file = new File(["evidence"], "notes.txt", { type: "text/plain" });
    await user.upload(screen.getByLabelText("Choose documents"), file);
    await user.click(screen.getByRole("button", { name: "Upload 1 document" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    const uploadCall = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    const body = uploadCall?.[1]?.body as FormData;
    expect(body.get("collection_id")).toBe(collectionId);
    expect((body.get("files") as File).name).toBe("notes.txt");
    expect(new Headers(uploadCall?.[1]?.headers).has("Content-Type")).toBe(false);
    expect(
      fetchMock.mock.calls.filter(([url]) => String(url).includes("/documents?")).length,
    ).toBeGreaterThanOrEqual(2);
  });

  it("enforces obvious upload constraints and excludes unsupported XLSX files", async () => {
    const user = userEvent.setup();
    installDetailApi();
    renderWithDashboardHeader(<CollectionDetailPage collectionId={collectionId} />);
    await screen.findByRole("heading", { name: collection.name });
    await user.click(screen.getAllByRole("button", { name: "Upload to collection" })[0]);

    const input = screen.getByLabelText("Choose documents");
    expect(input).toHaveAttribute(
      "accept",
      ".txt,.md,.pdf,text/plain,text/markdown,application/pdf",
    );
    expect(screen.getByText(/up to 3 files · 10 MB each/i)).toBeVisible();

    fireEvent.change(input, {
      target: { files: [new File(["sheet"], "forecast.xlsx")] },
    });
    expect(await screen.findByText(/forecast.xlsx is not a supported file type/i)).toBeVisible();
    expect(screen.queryByText(/xlsx files? (are )?supported/i)).not.toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: "Close" })[0]);
    await user.click(screen.getAllByRole("button", { name: "Upload to collection" })[0]);
    fireEvent.change(screen.getByLabelText("Choose documents"), {
      target: {
        files: [1, 2, 3, 4].map(
          (index) => new File([`file ${index}`], `file-${index}.txt`, { type: "text/plain" }),
        ),
      },
    });
    expect(await screen.findByText("Choose no more than three documents.")).toBeVisible();

    await user.click(screen.getAllByRole("button", { name: "Close" })[0]);
    await user.click(screen.getAllByRole("button", { name: "Upload to collection" })[0]);
    const oversized = new File(
      [new Uint8Array(10 * 1024 * 1024 + 1)],
      "large.pdf",
      { type: "application/pdf" },
    );
    fireEvent.change(screen.getByLabelText("Choose documents"), {
      target: { files: [oversized] },
    });
    expect(await screen.findByText(/large.pdf is larger than the 10 MB limit/i)).toBeVisible();
  });

  it("keeps upload server errors in the dialog", async () => {
    const user = userEvent.setup();
    installDetailApi((url, init) => {
      if (url.endsWith("/api/v1/documents/upload") && init?.method === "POST") {
        return jsonResponse(
          { error: { code: "content_too_large", message: "Upload exceeds MAX_UPLOAD_MB (10 MB)." } },
          413,
        );
      }
    });
    renderWithDashboardHeader(<CollectionDetailPage collectionId={collectionId} />);
    await screen.findByRole("heading", { name: collection.name });
    await user.click(screen.getAllByRole("button", { name: "Upload to collection" })[0]);
    await user.upload(
      screen.getByLabelText("Choose documents"),
      new File(["notes"], "notes.txt", { type: "text/plain" }),
    );
    await user.click(screen.getByRole("button", { name: "Upload 1 document" }));

    expect(await screen.findByText("Upload exceeds MAX_UPLOAD_MB (10 MB).")).toBeVisible();
    expect(screen.getByRole("dialog", { name: "Upload to collection" })).toBeVisible();
  });

  it("opens supported document metadata and permanently deletes a document", async () => {
    const user = userEvent.setup();
    const fetchMock = installDetailApi();
    renderWithDashboardHeader(<CollectionDetailPage collectionId={collectionId} />);
    await screen.findByRole("heading", { name: collection.name });

    await user.click(screen.getByRole("button", { name: `Actions for ${documents[0].filename}` }));
    await user.click(screen.getByRole("menuitem", { name: "View details" }));
    expect(await screen.findByRole("dialog", { name: "Document details" })).toBeVisible();
    expect(screen.getByText("application/pdf")).toBeVisible();
    await user.click(screen.getAllByRole("button", { name: "Close" }).at(-1)!);

    await user.click(screen.getByRole("button", { name: `Actions for ${documents[0].filename}` }));
    await user.click(screen.getByRole("menuitem", { name: "Delete document" }));
    await user.click(screen.getByRole("button", { name: "Delete document" }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) =>
      String(url).endsWith(`/documents/${documentId}`) && init?.method === "DELETE"
    )).toBe(true));
  });

  it("routes Ask this collection even when documents are not ready", async () => {
    const user = userEvent.setup();
    installDetailApi();
    renderWithDashboardHeader(<CollectionDetailPage collectionId={collectionId} />);
    await screen.findByRole("heading", { name: collection.name });

    await user.click(screen.getByRole("button", { name: "Ask this collection" }));
    expect(pushMock).toHaveBeenCalledWith(`/dashboard/ask-question?collectionId=${collectionId}`);
  });

  it("paginates collection documents and history with real offsets", async () => {
    const user = userEvent.setup();
    const fetchMock = installDetailApi((url) => {
      if (url.includes("/api/v1/documents?")) {
        const offset = new URL(url, "http://localhost").searchParams.get("offset");
        return jsonResponse({
          items: offset === "20" ? [documents[0]] : documents,
          limit: 20,
          offset: Number(offset),
          total: 21,
        });
      }
      if (url.includes("/api/v1/questions/history?")) {
        const offset = new URL(url, "http://localhost").searchParams.get("offset");
        return jsonResponse({
          items: [historyItem],
          limit: 20,
          offset: Number(offset),
          total: 21,
        });
      }
    });
    renderWithDashboardHeader(<CollectionDetailPage collectionId={collectionId} />);
    await screen.findByRole("heading", { name: collection.name });

    await user.click(screen.getByRole("button", { name: "Go to next page" }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) =>
      String(url).includes("/documents?limit=20&offset=20")
    )).toBe(true));
    await user.click(screen.getByRole("tab", { name: "History 21" }));
    await user.click(screen.getByRole("button", { name: "Go to next page" }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) =>
      String(url).includes("/questions/history?limit=20&offset=20")
    )).toBe(true));
  });

  it("shows successful empty document and history states", async () => {
    const user = userEvent.setup();
    installDetailApi((url) => {
      if (url.includes("/api/v1/documents?") || url.includes("/api/v1/questions/history?")) {
        return jsonResponse({ items: [], limit: 20, offset: 0, total: 0 });
      }
    });
    renderWithDashboardHeader(<CollectionDetailPage collectionId={collectionId} />);
    expect(await screen.findByRole("heading", { name: "This collection is empty" })).toBeVisible();
    await user.click(screen.getByRole("tab", { name: "History 0" }));
    expect(screen.getByRole("heading", { name: "No question history" })).toBeVisible();
    screen.getAllByRole("button", { name: "Ask this collection" }).forEach((button) => {
      expect(button).toBeEnabled();
    });
  });

  it("deletes a history item permanently and refreshes collection history", async () => {
    const user = userEvent.setup();
    const fetchMock = installDetailApi();
    renderWithDashboardHeader(<CollectionDetailPage collectionId={collectionId} />);
    await screen.findByRole("heading", { name: collection.name });
    await user.click(screen.getByRole("tab", { name: "History 1" }));
    await user.click(screen.getByRole("button", { name: `Actions for question: ${historyItem.question}` }));
    await user.click(screen.getByRole("menuitem", { name: "Delete history item" }));
    await user.click(screen.getByRole("button", { name: "Delete history item" }));

    await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) =>
      String(url).endsWith(`/questions/history/${questionId}`) && init?.method === "DELETE"
    )).toBe(true));
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("/questions/history?")).length).toBe(2);
  });

  it("retries a genuine server failure", async () => {
    const user = userEvent.setup();
    let detailAttempts = 0;
    installDetailApi((url) => {
      if (url.endsWith(`/collections/${collectionId}`)) {
        detailAttempts += 1;
        if (detailAttempts === 1) {
          return jsonResponse({ error: { code: "backend_unavailable", message: "Backend unavailable" } }, 503);
        }
      }
    });
    renderWithDashboardHeader(<CollectionDetailPage collectionId={collectionId} />);
    expect(await screen.findByRole("heading", { name: "Collection couldn’t load" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: collection.name })).toBeVisible();
  });

  it("keeps not-found, forbidden, and retryable server failures distinct", async () => {
    installDetailApi((url) => {
      if (url.endsWith(`/collections/${collectionId}`)) {
        return jsonResponse({ error: { code: "not_found", message: "Missing" } }, 404);
      }
    });
    const notFound = renderWithDashboardHeader(<CollectionDetailPage collectionId={collectionId} />);
    expect(await screen.findByRole("heading", { name: "Collection not found" })).toBeVisible();
    notFound.unmount();

    installDetailApi((url) => {
      if (url.endsWith(`/collections/${collectionId}`)) {
        return jsonResponse({ error: { code: "forbidden", message: "Forbidden" } }, 403);
      }
    });
    renderWithDashboardHeader(<CollectionDetailPage collectionId={collectionId} />);
    expect(await screen.findByRole("heading", { name: "Access unavailable" })).toBeVisible();
  });
});
