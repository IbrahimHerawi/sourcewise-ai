import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CollectionsScreen } from "@/features/collections/components/collections-screen";
import { renderWithDashboardHeader } from "@test/render/render-with-dashboard-header";

const pushMock = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  usePathname: () => "/dashboard/collections",
  useSearchParams: () => new URLSearchParams(),
}));

function renderCollections(
  props: Partial<React.ComponentProps<typeof CollectionsScreen>> = {},
) {
  return renderWithDashboardHeader(
    <CollectionsScreen initialPreview="populated" {...props} />,
  );
}

function collectionArticle(name: string): HTMLElement {
  const heading = screen.getByRole("heading", { name });
  const article = heading.closest("article");

  if (!article) {
    throw new Error(`Collection article not found for ${name}`);
  }

  return article;
}

describe("CollectionsScreen dialogs", () => {
  beforeEach(() => {
    pushMock.mockReset();
  });

  it("renders its route title and primary action in the shared header", () => {
    renderCollections();

    const header = screen.getByRole("banner");
    expect(within(header).getByRole("heading", { level: 1 })).toHaveTextContent(
      "Collections",
    );
    expect(
      within(header).getByRole("button", { name: "Create Collection" }),
    ).toBeVisible();
  });

  it("opens and closes create, edit, and delete dialogs", async () => {
    const user = userEvent.setup();
    renderCollections();

    await user.click(screen.getByRole("button", { name: "Create Collection" }));
    expect(screen.getByRole("dialog", { name: "Create collection" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    const quarterly = collectionArticle("Quarterly Research");
    await user.click(within(quarterly).getByRole("button", { name: "Edit" }));
    expect(screen.getByRole("dialog", { name: "Edit collection" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    await user.click(within(quarterly).getByRole("button", { name: "Delete" }));
    expect(screen.getByRole("alertdialog", { name: "Delete collection?" })).toBeVisible();
    expect(
      screen.getByText(
        "Deleting a collection does not delete its documents or question history. Those records remain and become unassigned.",
      ),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("renders configured modal previews through the screen interface", () => {
    renderCollections({ initialModal: "duplicate" });

    expect(screen.getByRole("dialog", { name: "Create collection" })).toBeVisible();
    expect(screen.getByLabelText("Name")).toHaveValue("quarterly research");
    expect(
      screen.getByText(
        "That name is already in use. Capitalization doesn’t make it unique.",
      ),
    ).toBeVisible();
  });

  it("validates required, duplicate, name-length, and description-length errors", async () => {
    const user = userEvent.setup();
    renderCollections();
    await user.click(screen.getByRole("button", { name: "Create Collection" }));

    const name = screen.getByLabelText("Name");
    const description = screen.getByLabelText("Description (optional)");
    const submit = screen.getByRole("button", { name: "Create Collection" });

    await user.click(submit);
    expect(screen.getByText("Enter a collection name.")).toBeVisible();

    await user.type(name, " quarterly research ");
    await user.click(submit);
    expect(
      screen.getByText(
        "That name is already in use. Capitalization doesn’t make it unique.",
      ),
    ).toBeVisible();
    expect(screen.getByRole("dialog")).toBeVisible();

    fireEvent.change(name, { target: { value: "n".repeat(256) } });
    await user.click(submit);
    expect(screen.getByText("Name must be 255 characters or fewer.")).toBeVisible();

    fireEvent.change(name, { target: { value: "Unique research" } });
    fireEvent.change(description, { target: { value: "d".repeat(2_001) } });
    await user.click(submit);
    expect(
      screen.getByText("Description must be 2,000 characters or fewer."),
    ).toBeVisible();

    fireEvent.change(description, { target: { value: "Within the limit" } });
    expect(
      screen.queryByText("Description must be 2,000 characters or fewer."),
    ).not.toBeInTheDocument();
  });

  it("creates a collection in local state and trims submitted values", async () => {
    const user = userEvent.setup();
    renderCollections({ initialPreview: "empty" });

    const emptyPanel = screen.getByRole("region", { name: "No collections yet" });
    await user.click(
      within(emptyPanel).getByRole("button", { name: "Create Collection" }),
    );
    await user.type(screen.getByLabelText("Name"), "  Evidence Archive  ");
    await user.type(
      screen.getByLabelText("Description (optional)"),
      "  Interview evidence  ",
    );
    await user.click(screen.getByRole("button", { name: "Create Collection" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Evidence Archive" })).toBeVisible();
    expect(screen.getByText("Interview evidence")).toBeVisible();
  });

  it("initializes the edit form, shows live counts, and saves locally", async () => {
    const user = userEvent.setup();
    renderCollections();

    await user.click(
      within(collectionArticle("Quarterly Research")).getByRole("button", {
        name: "Edit",
      }),
    );

    const name = screen.getByLabelText("Name");
    const description = screen.getByLabelText("Description (optional)");
    expect(name).toHaveValue("Quarterly Research");
    expect(description).toHaveValue(
      "Market notes, reports, and supporting source documents for the current quarter.",
    );
    expect(screen.getByText("18 / 255")).toBeVisible();
    expect(screen.getByText("79 / 2,000")).toBeVisible();

    await user.clear(name);
    await user.type(name, "Quarterly Insights");
    expect(screen.getByText("18 / 255")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(screen.getByRole("heading", { name: "Quarterly Insights" })).toBeVisible();
    expect(screen.getByText("Updated just now")).toBeVisible();
  });

  it("rejects another collection name while allowing the current name", async () => {
    const user = userEvent.setup();
    renderCollections();
    await user.click(
      within(collectionArticle("Quarterly Research")).getByRole("button", {
        name: "Edit",
      }),
    );

    const name = screen.getByLabelText("Name");
    await user.clear(name);
    await user.type(name, "customer discovery");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(
      screen.getByText(
        "That name is already in use. Capitalization doesn’t make it unique.",
      ),
    ).toBeVisible();

    await user.clear(name);
    await user.type(name, "quarterly research");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("cancels and confirms local deletion", async () => {
    const user = userEvent.setup();
    renderCollections();
    const quarterly = collectionArticle("Quarterly Research");

    await user.click(within(quarterly).getByRole("button", { name: "Delete" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("heading", { name: "Quarterly Research" })).toBeVisible();

    await user.click(
      within(collectionArticle("Quarterly Research")).getByRole("button", {
        name: "Delete",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Delete collection" }));
    expect(
      screen.queryByRole("heading", { name: "Quarterly Research" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Customer Discovery" })).toBeVisible();
  });

  it("navigates from the collection-not-found state", async () => {
    const user = userEvent.setup();
    renderCollections({ initialPreview: "not-found" });

    expect(screen.getByRole("heading", { name: "Collection not found" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Back to Collections" }));
    expect(pushMock).toHaveBeenCalledWith("/dashboard/collections");
  });

  it("renders loading and error states and retries with local data", async () => {
    const loading = renderCollections({ initialPreview: "loading" });
    expect(loading.container.querySelector('[aria-busy="true"]')).toBeVisible();
    expect(screen.getByText("Loading collections")).toHaveClass("sr-only");
    loading.unmount();

    const user = userEvent.setup();
    renderCollections({ initialPreview: "error" });
    expect(
      screen.getByRole("heading", { name: "Collections couldn’t load" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(screen.getByRole("heading", { name: "Quarterly Research" })).toBeVisible();
  });

  it("sets initial focus, traps keyboard focus, closes on Escape, and restores focus", async () => {
    const user = userEvent.setup();
    renderCollections();
    const trigger = screen.getByRole("button", { name: "Create Collection" });

    await user.click(trigger);
    const name = screen.getByLabelText("Name");
    expect(name).toHaveFocus();

    await user.tab({ shift: true });
    expect(screen.getByRole("button", { name: "Close" })).toHaveFocus();
    await user.tab({ shift: true });
    expect(screen.getByRole("button", { name: "Create Collection" })).toHaveFocus();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});
