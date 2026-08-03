import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DocumentsScreen } from "@/features/documents/components/documents-screen";
import { getAccessibilityViolations } from "@test/helpers/accessibility";
import { renderWithDashboardHeader } from "@test/render/render-with-dashboard-header";
import {
  installDocumentsApi,
  readyDocument,
} from "@/features/documents/__tests__/test-data";

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({ logout: vi.fn() }),
}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/documents",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

describe("DocumentsScreen accessibility", () => {
  beforeEach(() => {
    localStorage.setItem("sourcewise_token", "test-token");
    installDocumentsApi();
  });

  it("has no detectable violations in the loaded list and upload validation", async () => {
    const user = userEvent.setup();
    const { container } = renderWithDashboardHeader(<DocumentsScreen />);
    await screen.findByRole("heading", { name: readyDocument.filename });

    expect(await getAccessibilityViolations(container)).toEqual([]);
    expect(screen.getByText("Ready")).toHaveTextContent("Ready");
    const detailsButton = screen.getByRole("button", { name: "Details" });
    detailsButton.focus();
    expect(detailsButton).toHaveFocus();

    fireEvent.drop(
      screen.getByRole("button", {
        name: "Choose documents or drop files here",
      }),
      {
        dataTransfer: {
          files: [new File(["csv"], "unsupported.csv")],
        },
      },
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/not a supported file type/i);
    expect(await getAccessibilityViolations(container)).toEqual([]);
  });

  it("keeps details and delete overlays labelled, modal, and keyboard reachable", async () => {
    const user = userEvent.setup();
    const { container } = renderWithDashboardHeader(<DocumentsScreen />);
    const heading = await screen.findByRole("heading", {
      name: readyDocument.filename,
    });
    const article = heading.closest("article") as HTMLElement;

    const details = within(article).getByRole("button", { name: "Details" });
    details.focus();
    await user.keyboard("{Enter}");
    const detailsDialog = screen.getByRole("dialog", {
      name: "Document metadata",
    });
    expect(detailsDialog).toHaveAttribute("aria-describedby");
    expect(await getAccessibilityViolations(detailsDialog)).toEqual([]);
    await user.keyboard("{Escape}");
    await vi.waitFor(() =>
      expect(
        document.querySelector('[data-slot="sheet-content"]'),
      ).not.toBeInTheDocument(),
    );
    await vi.waitFor(() => expect(details).toHaveFocus());

    const deleteButton = within(article).getByRole("button", { name: "Delete" });
    deleteButton.focus();
    await user.keyboard("{Enter}");
    const deleteDialog = screen.getByRole("alertdialog", {
      name: "Delete document?",
    });
    expect(deleteDialog).toHaveAttribute("aria-describedby");
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
    await user.tab();
    expect(deleteDialog).toContainElement(document.activeElement as HTMLElement);
    expect(await getAccessibilityViolations(deleteDialog)).toEqual([]);
    await user.keyboard("{Escape}");
    await vi.waitFor(() => expect(deleteButton).toHaveFocus());

    expect(
      screen.getByRole("navigation", { name: "Documents pagination" }),
    ).toBeInTheDocument();
    expect(container).toBeInTheDocument();
  });
});
