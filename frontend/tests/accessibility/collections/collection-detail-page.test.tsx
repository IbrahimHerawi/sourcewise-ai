import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CollectionDetailPage } from "@/features/collections/components/detail/collection-detail-page";
import { getAccessibilityViolations } from "@test/helpers/accessibility";
import { renderWithDashboardHeader } from "@test/render/render-with-dashboard-header";

vi.mock("@/hooks/use-auth", () => ({ useAuth: () => ({ logout: vi.fn() }) }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/dashboard/collections/11111111-1111-4111-8111-111111111111",
  useSearchParams: () => new URLSearchParams(),
}));

const collectionId = "11111111-1111-4111-8111-111111111111";

describe("CollectionDetailPage accessibility", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/documents?")) {
        return new Response(JSON.stringify({ items: [], limit: 20, offset: 0, total: 0 }));
      }
      if (url.includes("/questions/history?")) {
        return new Response(JSON.stringify({ items: [], limit: 20, offset: 0, total: 0 }));
      }
      return new Response(JSON.stringify({
        id: collectionId,
        name: "Quarterly Research",
        description: null,
        created_at: "2026-07-01T12:00:00Z",
        updated_at: "2026-07-02T12:00:00Z",
      }));
    }));
  });

  it("has no detectable violations in loaded empty content", async () => {
    const { container } = renderWithDashboardHeader(
      <CollectionDetailPage collectionId={collectionId} />,
    );
    await screen.findByRole("heading", { name: "This collection is empty" });
    expect(await getAccessibilityViolations(container)).toEqual([]);
  });
});
