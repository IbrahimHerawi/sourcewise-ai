import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DashboardSidebar } from "@/features/dashboard/components/dashboard-sidebar";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/collections",
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({ logout: vi.fn(), user: null }),
}));

function setNavigationDimensions(
  navigation: HTMLElement,
  { clientHeight, scrollHeight }: { clientHeight: number; scrollHeight: number },
) {
  Object.defineProperties(navigation, {
    clientHeight: { configurable: true, value: clientHeight },
    scrollHeight: { configurable: true, value: scrollHeight },
  });
  fireEvent(window, new Event("resize"));
}

describe("DashboardSidebar", () => {
  it("keeps fitting navigation visible without enabling internal scrolling", () => {
    render(<DashboardSidebar />);
    expect(screen.getByRole("img", { name: "SourceWise" })).toHaveAttribute(
      "src",
      expect.stringContaining("sourcewise-lockup.png"),
    );
    const navigation = screen.getByRole("navigation", {
      name: "Dashboard navigation",
    });

    setNavigationDimensions(navigation, {
      clientHeight: 420,
      scrollHeight: 180,
    });

    expect(navigation).toHaveAttribute("data-overflowing", "false");
    expect(screen.getByRole("link", { name: "Collections" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("keeps the navigation fallback keyboard accessible", async () => {
    const user = userEvent.setup();
    render(<DashboardSidebar />);

    await user.tab();
    expect(screen.getByRole("link", { name: "Overview" })).toHaveFocus();
  });

  it("enables the navigation fallback only when its content overflows", () => {
    render(<DashboardSidebar />);
    const navigation = screen.getByRole("navigation", {
      name: "Dashboard navigation",
    });

    setNavigationDimensions(navigation, {
      clientHeight: 120,
      scrollHeight: 240,
    });
    expect(navigation).toHaveAttribute("data-overflowing", "true");

    setNavigationDimensions(navigation, {
      clientHeight: 320,
      scrollHeight: 240,
    });
    expect(navigation).toHaveAttribute("data-overflowing", "false");
  });
});
