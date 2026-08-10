import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DocumentDetailsDialog } from "@/features/collections/components/detail/document-dialogs";
import { installTestAuthSession } from "@test/helpers/auth";
import {
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

describe("DocumentDetailsDialog", () => {
  beforeEach(() => {
    installTestAuthSession();
    logoutMock.mockReset();
  });

  it("loads the selected document from the real detail endpoint", async () => {
    const fetchMock = installDocumentsApi();

    render(<DocumentDetailsDialog documentId={documentId} onClose={vi.fn()} />);

    expect(screen.getByText("Loading document details…")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Document details" }),
    ).toBeVisible();
    expect(await screen.findByText(readyDocument.filename)).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/documents/${documentId}`,
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("preserves the dialog on failure and retries successfully", async () => {
    const user = userEvent.setup();
    let attempts = 0;
    installDocumentsApi((url) => {
      if (url.endsWith(`/documents/${documentId}`)) {
        attempts += 1;
        if (attempts === 1) {
          return jsonResponse(
            { error: { code: "service_unavailable", message: "Unavailable" } },
            503,
          );
        }
      }
    });

    render(<DocumentDetailsDialog documentId={documentId} onClose={vi.fn()} />);

    expect(
      await screen.findByText(
        "The document service could not load these details. Try again later.",
      ),
    ).toBeVisible();
    expect(screen.queryByText("Unavailable")).not.toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText(readyDocument.filename)).toBeVisible();
    expect(attempts).toBe(2);
  });

  it("ignores an older detail response after the selection changes", async () => {
    let resolveFirst!: (response: Response) => void;
    const first = new Promise<Response>((resolve) => {
      resolveFirst = resolve;
    });
    installDocumentsApi((url) => {
      if (url.endsWith(`/documents/${documentId}`)) return first;
      if (url.endsWith(`/documents/${secondDocumentId}`)) {
        return jsonResponse(secondDocument);
      }
    });
    const view = render(
      <DocumentDetailsDialog documentId={documentId} onClose={vi.fn()} />,
    );

    view.rerender(
      <DocumentDetailsDialog
        documentId={secondDocumentId}
        onClose={vi.fn()}
      />,
    );
    expect(await screen.findByText(secondDocument.filename)).toBeVisible();

    resolveFirst(jsonResponse(readyDocument));
    await waitFor(() =>
      expect(screen.queryByText(readyDocument.filename)).not.toBeInTheDocument(),
    );
    expect(screen.getByText(secondDocument.filename)).toBeVisible();
  });

  it("logs out when detail authentication fails", async () => {
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
      if (url.endsWith(`/documents/${documentId}`)) {
        return jsonResponse(
          { error: { code: "unauthorized", message: "Expired" } },
          401,
        );
      }
    });

    render(<DocumentDetailsDialog documentId={documentId} onClose={vi.fn()} />);

    expect(
      await screen.findByText("Your session has ended. Sign in and try again."),
    ).toBeVisible();
    expect(screen.queryByText("Expired")).not.toBeInTheDocument();
    expect(logoutMock).toHaveBeenCalledTimes(1);
  });
});
