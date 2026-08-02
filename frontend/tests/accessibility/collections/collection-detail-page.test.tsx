import { describe, expect, it, vi } from "vitest";
import { CollectionDetailPage } from "@/features/collections/components/detail/collection-detail-page";
import { getAccessibilityViolations } from "@test/helpers/accessibility";
import { renderWithDashboardHeader } from "@test/render/render-with-dashboard-header";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/dashboard/collections/quarterly-research",
  useSearchParams: () => new URLSearchParams(),
}));

describe("CollectionDetailPage accessibility", () => {
  it("has no detectable violations in populated content", async () => {
    const { container } = renderWithDashboardHeader(
      <CollectionDetailPage
        collectionId="quarterly-research"
        initialPreview="history"
      />,
    );

    await expect(getAccessibilityViolations(container)).resolves.toEqual([]);
  });
});
