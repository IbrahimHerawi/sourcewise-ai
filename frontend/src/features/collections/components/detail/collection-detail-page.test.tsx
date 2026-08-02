import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CollectionDetailPage } from "./collection-detail-page";

const { pushMock, replaceMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  replaceMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
}));

function renderDetail(
  initialPreview: React.ComponentProps<typeof CollectionDetailPage>["initialPreview"] = "documents",
  collectionId = "quarterly-research",
) {
  return render(
    <CollectionDetailPage
      collectionId={collectionId}
      initialPreview={initialPreview}
    />,
  );
}

describe("CollectionDetailPage", () => {
  beforeEach(() => {
    pushMock.mockReset();
    replaceMock.mockReset();
  });

  it("renders populated documents and local pagination", async () => {
    const user = userEvent.setup();
    renderDetail();

    expect(screen.getByRole("heading", { name: "Quarterly Research" })).toBeVisible();
    const summary = screen.getByRole("region", { name: "Collection summary" });
    expect(within(summary).getByText("223")).toBeVisible();
    expect(within(summary).getByText("47")).toBeVisible();
    expect(screen.getByRole("tab", { name: "Documents 223" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getAllByText("Ready")).toHaveLength(6);
    expect(screen.getByText("Showing 21–40 of 223")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Go to page 12" }));
    expect(screen.getByText("Showing 221–223 of 223")).toBeVisible();
    expect(screen.getByRole("button", { name: "Go to next page" })).toBeDisabled();
  });

  it("switches tabs, preserves the route convention, and renders history cards", async () => {
    const user = userEvent.setup();
    renderDetail();

    await user.click(screen.getByRole("tab", { name: "History 47" }));
    expect(replaceMock).toHaveBeenCalledWith(
      "/dashboard/collections/quarterly-research?tab=history",
      { scroll: false },
    );
    expect(screen.getByRole("heading", { name: "Question history" })).toBeVisible();
    expect(screen.getByText("4 citations")).toBeVisible();
    expect(screen.getByText("Asked yesterday")).toBeVisible();
  });

  it("renders the empty collection and keeps asking disabled", async () => {
    const user = userEvent.setup();
    renderDetail("empty");

    expect(screen.getByRole("heading", { name: "This collection is empty" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Ask this collection" })).toBeDisabled();
    await user.click(
      within(screen.getByRole("region", { name: "This collection is empty" })).getByRole(
        "button",
        { name: "Upload to collection" },
      ),
    );
    expect(pushMock).toHaveBeenCalledWith(
      "/dashboard/documents?collectionId=quarterly-research",
    );
  });

  it("renders and dismisses the no-ready warning with processing variants", async () => {
    const user = userEvent.setup();
    renderDetail("no-ready-documents");

    expect(screen.getByText("3 documents · 0 ready")).toBeVisible();
    expect(screen.getAllByText("Processing")).toHaveLength(2);
    expect(screen.getByText("Pending")).toBeVisible();
    expect(screen.getByText("Processing · 64%")).toBeVisible();
    expect(screen.getByRole("button", { name: "Ask this collection" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Dismiss processing warning" }));
    expect(
      screen.queryByText(
        "No ready documents. Processing must finish before you can ask this collection.",
      ),
    ).not.toBeInTheDocument();
  });

  it("renders active no-history state and enables its ask action", async () => {
    const user = userEvent.setup();
    renderDetail("no-question-history");

    expect(screen.getByRole("tab", { name: "History 0" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByText("0 questions")).toBeVisible();
    const state = screen.getByRole("region", { name: "No question history" });
    await user.click(within(state).getByRole("button", { name: "Ask this collection" }));
    expect(pushMock).toHaveBeenCalledWith(
      "/dashboard/ask-question?collectionId=quarterly-research",
    );
  });

  it("keeps loading, not-found, and server-error states distinct", async () => {
    const loading = renderDetail("loading");
    expect(loading.container.querySelector('[aria-busy="true"]')).toBeVisible();
    expect(screen.getByText("Loading collection details")).toHaveClass("sr-only");
    loading.unmount();

    const user = userEvent.setup();
    const notFound = renderDetail("not-found");
    await user.click(screen.getByRole("button", { name: "Back to Collections" }));
    expect(pushMock).toHaveBeenCalledWith("/dashboard/collections");
    notFound.unmount();

    renderDetail("server-error");
    expect(screen.getByRole("heading", { name: "Collection couldn’t load" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(screen.getByRole("heading", { name: "Documents" })).toBeVisible();
  });

  it("treats an unresolved route collection ID as genuinely not found", () => {
    renderDetail("documents", "outdated-collection-link");

    expect(screen.getByRole("heading", { name: "Collection not found" })).toBeVisible();
    expect(
      screen.getByText(
        "The collection may have been deleted or the link may be outdated.",
      ),
    ).toBeVisible();
  });

  it("uses the shared edit and delete dialogs", async () => {
    const user = userEvent.setup();
    renderDetail();

    await user.click(screen.getByRole("button", { name: "Edit" }));
    expect(screen.getByRole("dialog", { name: "Edit collection" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(screen.getByRole("alertdialog", { name: "Delete collection?" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Delete collection" }));
    expect(screen.getByRole("heading", { name: "Collection not found" })).toBeVisible();
  });

  it("has no detectable accessibility violations in populated content", async () => {
    const { container } = renderDetail("history");
    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(results.violations).toEqual([]);
  });
});
