import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CollectionsScreen } from "@/features/collections/components/collections-screen";
import { getAccessibilityViolations } from "@test/helpers/accessibility";
import { renderWithDashboardHeader } from "@test/render/render-with-dashboard-header";

vi.mock("@/hooks/use-auth", () => ({ useAuth: () => ({ logout: vi.fn() }) }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/dashboard/collections",
  useSearchParams: () => new URLSearchParams(),
}));

describe("CollectionsScreen accessibility", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
      items: [],
      limit: 20,
      offset: 0,
      total: 0,
    }), { headers: { "Content-Type": "application/json" } })));
  });

  it("has no detectable collection or dialog accessibility violations", async () => {
    const user = userEvent.setup();
    const { container } = renderWithDashboardHeader(<CollectionsScreen />);
    await screen.findByRole("heading", { name: "No collections yet" });
    expect(await getAccessibilityViolations(container)).toEqual([]);

    await user.click(screen.getAllByRole("button", { name: "Create Collection" })[0]);
    expect(await getAccessibilityViolations(screen.getByRole("dialog"))).toEqual([]);
  });
});
