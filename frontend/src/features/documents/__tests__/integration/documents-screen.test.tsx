import {
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DocumentsScreen } from "@/features/documents/components/documents-screen";
import { DOCUMENT_UPLOAD_LIMITS } from "@/features/documents/file-validation";
import { installTestAuthSession } from "@test/helpers/auth";
import { renderWithDashboardHeader } from "@test/render/render-with-dashboard-header";
import {
  collectionId,
  collections,
  documentId,
  installDocumentsApi,
  jsonResponse,
  readyDocument,
  secondDocument,
  secondDocumentId,
} from "../test-data";

const { logoutMock } = vi.hoisted(() => ({ logoutMock: vi.fn() }));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({ logout: logoutMock }),
}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/documents",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

function documentArticle(filename: string): HTMLElement {
  const article = screen.getByRole("heading", { name: filename }).closest("article");
  if (!article) throw new Error(`Document article not found for ${filename}`);
  return article;
}

describe("DocumentsScreen API integration", () => {
  beforeEach(() => {
    vi.useRealTimers();
    installTestAuthSession();
    logoutMock.mockReset();
  });

  it("shows initial loading, then backend-owned populated results and statuses", async () => {
    installDocumentsApi((url) => {
      if (url.includes("/documents?")) {
        return jsonResponse({
          items: [
            readyDocument,
            { ...secondDocument, status: "PENDING" },
            {
              ...secondDocument,
              id: "55555555-5555-4555-8555-555555555555",
              filename: "processing.txt",
              status: "PROCESSING",
            },
            {
              ...secondDocument,
              id: "66666666-6666-4666-8666-666666666666",
              filename: "failed.txt",
              status: "FAILED",
              error_message: "Document contains no extractable text.",
            },
            {
              ...secondDocument,
              id: "77777777-7777-4777-8777-777777777777",
              filename: "future.txt",
              status: "ARCHIVED",
            },
          ],
          limit: 20,
          offset: 0,
          total: 5,
        });
      }
    });

    renderWithDashboardHeader(<DocumentsScreen />);

    expect(screen.getByText("Loading documents…")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: readyDocument.filename }),
    ).toBeVisible();
    expect(screen.getByText("Ready")).toBeVisible();
    expect(screen.getByText("Pending")).toBeVisible();
    expect(screen.getByText("Processing")).toBeVisible();
    expect(screen.getByText("Failed")).toBeVisible();
    expect(screen.getByText("Unknown")).toBeVisible();
    expect(
      screen.getByText("Document contains no extractable text."),
    ).toBeVisible();
    expect(screen.getByText("Showing 1–5 of 5")).toBeVisible();
    expect(
      screen.queryByRole("button", {
        name: /retry processing|download|reassign|cancel processing/i,
      }),
    ).not.toBeInTheDocument();
  });

  it("renders an authoritative empty response", async () => {
    installDocumentsApi((url) => {
      if (url.includes("/documents?")) {
        return jsonResponse({ items: [], limit: 20, offset: 0, total: 0 });
      }
    });

    renderWithDashboardHeader(<DocumentsScreen />);

    expect(
      await screen.findByRole("heading", { name: "No documents yet" }),
    ).toBeVisible();
    expect(screen.queryByText("Showing 0–0 of 0")).not.toBeInTheDocument();
  });

  it.each([
    {
      name: "server failure",
      response: () =>
        jsonResponse(
          { error: { code: "internal_server_error", message: "Failed" } },
          500,
        ),
      title: "Documents couldn’t load",
    },
    {
      name: "authorization failure",
      response: () =>
        jsonResponse(
          { error: { code: "forbidden", message: "Forbidden" } },
          403,
        ),
      title: "Documents aren’t available",
    },
    {
      name: "unexpected response",
      response: () => jsonResponse({ items: "invalid" }),
      title: "Documents couldn’t load",
    },
  ])("handles $name safely", async ({ response, title }) => {
    installDocumentsApi((url) => {
      if (url.includes("/documents?")) return response();
    });

    renderWithDashboardHeader(<DocumentsScreen />);

    expect(await screen.findByRole("heading", { name: title })).toBeVisible();
    expect(screen.getByRole("button", { name: "Try loading again" })).toBeEnabled();
  });

  it("handles network failure and retries without replacing the feature with mocks", async () => {
    const user = userEvent.setup();
    let attempts = 0;
    installDocumentsApi((url) => {
      if (url.includes("/documents?")) {
        attempts += 1;
        if (attempts === 1) throw new TypeError("offline");
      }
      return undefined;
    });
    renderWithDashboardHeader(<DocumentsScreen />);

    expect(
      await screen.findByRole("heading", {
        name: "Can’t reach the document service",
      }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Try loading again" }));
    expect(
      await screen.findByRole("heading", { name: readyDocument.filename }),
    ).toBeVisible();
    expect(attempts).toBe(2);
  });

  it("logs out on authentication failure", async () => {
    installDocumentsApi((url) => {
      if (url.endsWith("/auth/refresh")) {
        return jsonResponse(
          {
            error: {
              code: "invalid_refresh_token",
              message: "Refresh token is invalid or expired.",
            },
          },
          401,
        );
      }
      if (url.includes("/documents?")) {
        return jsonResponse(
          { error: { code: "unauthorized", message: "Expired" } },
          401,
        );
      }
    });

    renderWithDashboardHeader(<DocumentsScreen />);

    expect(
      await screen.findByRole("heading", { name: "Your session has ended" }),
    ).toBeVisible();
    expect(logoutMock).toHaveBeenCalledTimes(1);
  });

  it("uses backend pagination and collection filtering together", async () => {
    const user = userEvent.setup();
    const fetchMock = installDocumentsApi((url) => {
      if (url.includes("/documents?")) {
        const params = new URL(url, "http://localhost").searchParams;
        const offset = Number(params.get("offset"));
        const selectedCollection = params.get("collection_id");
        if (selectedCollection) {
          return jsonResponse({
            items: [readyDocument],
            limit: 20,
            offset: 0,
            total: 1,
          });
        }
        return jsonResponse({
          items: [offset === 20 ? secondDocument : readyDocument],
          limit: 20,
          offset,
          total: 21,
        });
      }
    });
    renderWithDashboardHeader(<DocumentsScreen />);
    await screen.findByRole("heading", { name: readyDocument.filename });

    await user.click(screen.getByRole("button", { name: "Go to next page" }));
    expect(
      await screen.findByRole("heading", { name: secondDocument.filename }),
    ).toBeVisible();
    expect(
      fetchMock.mock.calls.some(([url]) =>
        String(url).includes("/documents?limit=20&offset=20"),
      ),
    ).toBe(true);

    await user.click(
      screen.getByRole("combobox", {
        name: "Filter documents by collection",
      }),
    );
    await user.click(
      screen.getByRole("option", { name: collections[0].name }),
    );
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) => {
          const parsed = new URL(String(url), "http://localhost");
          return (
            parsed.searchParams.get("offset") === "0" &&
            parsed.searchParams.get("collection_id") === collectionId
          );
        }),
      ).toBe(true),
    );
  });

  it("supports file picker, drag-and-drop, validation, and removal", async () => {
    const user = userEvent.setup();
    installDocumentsApi();
    renderWithDashboardHeader(<DocumentsScreen />);
    await screen.findByRole("heading", { name: readyDocument.filename });

    const input = screen.getByLabelText("Choose documents");
    await user.upload(input, new File(["notes"], "notes.txt"));
    expect(screen.getByText("Ready to upload")).toBeVisible();

    fireEvent.drop(
      screen.getByRole("button", {
        name: "Choose documents or drop files here",
      }),
      { dataTransfer: { files: [new File(["csv"], "data.csv")] } },
    );
    expect(screen.getByText("Unsupported type")).toBeVisible();
    expect(screen.getByRole("button", { name: /^Upload 2 files$/ })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Remove data.csv" }));
    expect(screen.queryByText("Unsupported type")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload 1 file" })).toBeEnabled();

    await user.upload(
      input,
      new File(
        [new Uint8Array(DOCUMENT_UPLOAD_LIMITS.maxFileBytes + 1)],
        "large.pdf",
      ),
    );
    expect(screen.getByText(/exceeds the 10 MB limit/i)).toBeVisible();
  });

  it("blocks batches over three files", async () => {
    const user = userEvent.setup();
    installDocumentsApi();
    renderWithDashboardHeader(<DocumentsScreen />);
    await screen.findByRole("heading", { name: readyDocument.filename });

    await user.upload(
      screen.getByLabelText("Choose documents"),
      ["one", "two", "three", "four"].map(
        (name) => new File([name], `${name}.txt`),
      ),
    );

    expect(screen.getByText("Over batch limit")).toBeVisible();
    expect(screen.getByRole("button", { name: "Upload 4 files" })).toBeDisabled();
  });

  it("uploads once, confirms backend success, and refreshes the current query", async () => {
    const user = userEvent.setup();
    let listRequests = 0;
    const fetchMock = installDocumentsApi((url) => {
      if (url.includes("/documents?")) listRequests += 1;
      return undefined;
    });
    renderWithDashboardHeader(<DocumentsScreen />);
    await screen.findByRole("heading", { name: readyDocument.filename });

    await user.upload(
      screen.getByLabelText("Choose documents"),
      new File(["notes"], "notes.txt"),
    );
    await user.click(screen.getByRole("button", { name: "Upload 1 file" }));

    expect(
      await screen.findByText(/document was accepted and queued/i),
    ).toBeVisible();
    await waitFor(() => expect(listRequests).toBe(2));
    const post = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).endsWith("/documents/upload") && init?.method === "POST",
    );
    expect(post).toBeTruthy();
  });

  it("prevents duplicate upload submissions and preserves failures", async () => {
    const user = userEvent.setup();
    let resolveUpload!: (response: Response) => void;
    const pendingUpload = new Promise<Response>((resolve) => {
      resolveUpload = resolve;
    });
    const fetchMock = installDocumentsApi((url, init) => {
      if (url.endsWith("/documents/upload") && init?.method === "POST") {
        return pendingUpload;
      }
    });
    renderWithDashboardHeader(<DocumentsScreen />);
    await screen.findByRole("heading", { name: readyDocument.filename });
    await user.upload(
      screen.getByLabelText("Choose documents"),
      new File(["notes"], "notes.txt"),
    );

    const submit = screen.getByRole("button", { name: "Upload 1 file" });
    await user.click(submit);
    expect(screen.getByRole("button", { name: "Uploading…" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Uploading…" }));
    expect(
      fetchMock.mock.calls.filter(
        ([url, init]) =>
          String(url).endsWith("/documents/upload") && init?.method === "POST",
      ),
    ).toHaveLength(1);

    resolveUpload(
      jsonResponse(
        {
          error: {
            code: "internal_server_error",
            message: "Storage path /private/data failed",
          },
        },
        500,
      ),
    );
    expect(
      await screen.findByText(
        "The document service could not complete the upload. Try again later.",
      ),
    ).toBeVisible();
    expect(screen.queryByText(/private\/data/)).not.toBeInTheDocument();
    expect(screen.getByText("notes.txt")).toBeVisible();
  });

  it("opens real list details without another request and restores focus", async () => {
    const user = userEvent.setup();
    const fetchMock = installDocumentsApi();
    renderWithDashboardHeader(<DocumentsScreen />);
    const heading = await screen.findByRole("heading", {
      name: readyDocument.filename,
    });
    const detailsButton = within(
      heading.closest("article") as HTMLElement,
    ).getByRole("button", { name: "Details" });

    await user.click(detailsButton);
    expect(
      screen.getByRole("dialog", { name: "Document metadata" }),
    ).toBeVisible();
    expect(screen.getByText(documentId)).toBeVisible();
    expect(
      fetchMock.mock.calls.some(([url]) =>
        String(url).endsWith(`/documents/${documentId}`),
      ),
    ).toBe(false);

    await user.click(screen.getByRole("button", { name: "Close" }));
    await waitFor(() => expect(detailsButton).toHaveFocus());
  });

  it("cancels deletion without a request and deletes only after confirmation", async () => {
    const user = userEvent.setup();
    let deleted = false;
    const fetchMock = installDocumentsApi((url, init) => {
      if (
        url.endsWith(`/documents/${documentId}`) &&
        init?.method === "DELETE"
      ) {
        deleted = true;
        return new Response(null, { status: 204 });
      }
      if (url.includes("/documents?") && deleted) {
        return jsonResponse({ items: [], limit: 20, offset: 0, total: 0 });
      }
    });
    renderWithDashboardHeader(<DocumentsScreen />);
    await screen.findByRole("heading", { name: readyDocument.filename });

    await user.click(
      within(documentArticle(readyDocument.filename)).getByRole("button", {
        name: "Delete",
      }),
    );
    expect(screen.getByRole("alertdialog", { name: "Delete document?" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(
      fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE"),
    ).toBe(false);

    await user.click(
      within(documentArticle(readyDocument.filename)).getByRole("button", {
        name: "Delete",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Delete document" }));
    expect(
      await screen.findByRole("heading", { name: "No documents yet" }),
    ).toBeVisible();
  });

  it("keeps the document and blocks duplicate deletes when deletion fails", async () => {
    const user = userEvent.setup();
    let resolveDelete!: (response: Response) => void;
    const pendingDelete = new Promise<Response>((resolve) => {
      resolveDelete = resolve;
    });
    const fetchMock = installDocumentsApi((url, init) => {
      if (
        url.endsWith(`/documents/${documentId}`) &&
        init?.method === "DELETE"
      ) {
        return pendingDelete;
      }
    });
    renderWithDashboardHeader(<DocumentsScreen />);
    await screen.findByRole("heading", { name: readyDocument.filename });
    await user.click(
      within(documentArticle(readyDocument.filename)).getByRole("button", {
        name: "Delete",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Delete document" }));
    expect(screen.getByRole("button", { name: "Deleting…" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Deleting…" }));
    expect(
      fetchMock.mock.calls.filter(([, init]) => init?.method === "DELETE"),
    ).toHaveLength(1);

    resolveDelete(
      jsonResponse(
        { error: { code: "internal_server_error", message: "SQL failed" } },
        500,
      ),
    );
    expect(
      await screen.findByText(
        "The document service could not delete this document. Try again later.",
      ),
    ).toBeVisible();
    expect(document.body).toHaveTextContent(readyDocument.filename);
    expect(screen.getByRole("alertdialog")).toBeVisible();
    expect(screen.queryByText("SQL failed")).not.toBeInTheDocument();
  });

  it("corrects pagination after deleting the last result on a later page", async () => {
    const user = userEvent.setup();
    let deleted = false;
    const fetchMock = installDocumentsApi((url, init) => {
      if (
        url.endsWith(`/documents/${secondDocumentId}`) &&
        init?.method === "DELETE"
      ) {
        deleted = true;
        return new Response(null, { status: 204 });
      }
      if (url.includes("/documents?")) {
        const offset = Number(
          new URL(url, "http://localhost").searchParams.get("offset"),
        );
        if (offset === 20 && !deleted) {
          return jsonResponse({
            items: [secondDocument],
            limit: 20,
            offset: 20,
            total: 21,
          });
        }
        return jsonResponse({
          items: [readyDocument],
          limit: 20,
          offset: 0,
          total: deleted ? 20 : 21,
        });
      }
    });
    renderWithDashboardHeader(<DocumentsScreen />);
    await screen.findByRole("heading", { name: readyDocument.filename });
    await user.click(screen.getByRole("button", { name: "Go to next page" }));
    await screen.findByRole("heading", { name: secondDocument.filename });
    await user.click(
      within(documentArticle(secondDocument.filename)).getByRole("button", {
        name: "Delete",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Delete document" }));

    expect(
      await screen.findByRole("heading", { name: readyDocument.filename }),
    ).toBeVisible();
    expect(
      fetchMock.mock.calls.some(([url]) =>
        String(url).includes("/documents?limit=20&offset=0"),
      ),
    ).toBe(true);
  });
});
