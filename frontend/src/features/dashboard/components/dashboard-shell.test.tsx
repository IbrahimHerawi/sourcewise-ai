import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DashboardShell } from "./dashboard-shell";

vi.mock("next/font/google", () => ({
  Inter: () => ({ variable: "font-inter" }),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/collections",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("./dashboard-sidebar", () => ({
  DashboardSidebar: () => <aside aria-label="Dashboard sidebar" />,
}));

describe("DashboardShell", () => {
  it("keeps one sidebar beside the shared main content region", () => {
    render(
      <DashboardShell>
        <div>Dashboard content</div>
      </DashboardShell>,
    );

    const shell = screen.getByText("Dashboard content").closest(
      '[data-slot="dashboard-shell"]',
    );
    const sidebar = screen.getByRole("complementary", {
      name: "Dashboard sidebar",
    });
    const content = screen.getByRole("main", { name: "Dashboard content" });

    expect(shell).toContainElement(sidebar);
    expect(shell).toContainElement(content);
    expect(content).toHaveAttribute("data-slot", "dashboard-content");
    expect(content).toHaveAttribute("id", "dashboard-main-content");
    expect(content).toHaveAttribute("tabindex", "0");
    expect(content).toHaveTextContent("Dashboard content");
    expect(screen.getByRole("banner")).toHaveTextContent("Collections");
    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute(
      "href",
      "#dashboard-main-content",
    );
  });
});
