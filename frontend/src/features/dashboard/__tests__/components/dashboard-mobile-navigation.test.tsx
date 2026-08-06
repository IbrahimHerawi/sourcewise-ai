import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DashboardMobileNavigation } from "@/features/dashboard/components/dashboard-mobile-navigation";

const { logoutMock } = vi.hoisted(() => ({
  logoutMock: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/collections",
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    logout: logoutMock,
    user: {
      id: "user-1",
      first_name: "Ada",
      last_name: "Lovelace",
      email: "ada@example.com",
      is_email_verified: true,
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
    },
  }),
}));

describe("DashboardMobileNavigation", () => {
  beforeEach(() => {
    logoutMock.mockClear();
  });

  it("opens an anchored menu with navigation and profile actions", async () => {
    const user = userEvent.setup();
    render(<DashboardMobileNavigation />);
    expect(screen.getByRole("img", { name: "SourceWise" })).toHaveAttribute(
      "src",
      expect.stringContaining("sourcewise-lockup.png"),
    );
    const trigger = screen.getByRole("button", {
      name: "Dashboard navigation",
    });

    expect(trigger).toHaveAttribute("aria-expanded", "false");
    await user.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("menu", { name: "Dashboard navigation" })).toBeVisible();
    expect(screen.getAllByRole("menuitem")).toHaveLength(6);
    expect(screen.getByRole("menuitem", { name: "Collections" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByText("Ada Lovelace")).toBeVisible();
    expect(screen.getByRole("menuitem", { name: "Log out" })).toBeVisible();
  });

  it("supports arrow-key focus and closes with Escape or the trigger", async () => {
    const user = userEvent.setup();
    render(<DashboardMobileNavigation />);
    const trigger = screen.getByRole("button", {
      name: "Dashboard navigation",
    });

    trigger.focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("menuitem", { name: "Overview" })).toHaveFocus();

    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("menuitem", { name: "Documents" })).toHaveFocus();

    await user.keyboard("{Escape}");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(trigger).toHaveFocus();

    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  it("closes after selection or outside interaction and invokes logout", async () => {
    const user = userEvent.setup();
    render(<DashboardMobileNavigation />);
    const trigger = screen.getByRole("button", {
      name: "Dashboard navigation",
    });

    await user.click(trigger);
    await user.click(screen.getByRole("menuitem", { name: "Documents" }));
    expect(trigger).toHaveAttribute("aria-expanded", "false");

    await user.click(trigger);
    await user.click(document.body);
    expect(trigger).toHaveAttribute("aria-expanded", "false");

    await user.click(trigger);
    await user.click(screen.getByRole("menuitem", { name: "Log out" }));
    expect(logoutMock).toHaveBeenCalledOnce();
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });
});
