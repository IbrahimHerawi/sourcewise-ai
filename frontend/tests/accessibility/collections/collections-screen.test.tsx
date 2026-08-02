import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CollectionsScreen } from "@/features/collections/components/collections-screen";
import { getAccessibilityViolations } from "@test/helpers/accessibility";
import { renderWithDashboardHeader } from "@test/render/render-with-dashboard-header";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/dashboard/collections",
  useSearchParams: () => new URLSearchParams(),
}));

describe("CollectionsScreen accessibility", () => {
  it("has no detectable dialog accessibility violations", async () => {
    const user = userEvent.setup();
    renderWithDashboardHeader(
      <CollectionsScreen initialPreview="populated" />,
    );

    await user.click(screen.getByRole("button", { name: "Create Collection" }));

    await expect(
      getAccessibilityViolations(screen.getByRole("dialog")),
    ).resolves.toEqual([]);
  });
});
