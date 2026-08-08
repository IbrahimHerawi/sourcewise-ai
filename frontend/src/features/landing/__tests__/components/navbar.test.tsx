import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Navbar } from "@/features/landing/components/navbar";

const { scrollFromHeaderNavigationMock } = vi.hoisted(() => ({
  scrollFromHeaderNavigationMock: vi.fn(),
}));

vi.mock("@/features/landing/components/navigation-scroll", () => ({
  scrollFromHeaderNavigation: scrollFromHeaderNavigationMock,
}));

describe("Navbar", () => {
  beforeEach(() => {
    scrollFromHeaderNavigationMock.mockClear();
    document.body.innerHTML = `
      <div id="top"></div>
      <section id="how-it-works"></section>
      <section id="features"></section>
      <footer id="footer"></footer>
    `;
    window.history.replaceState(null, "", "/");
  });

  it("scrolls navigation buttons without changing the URL or history", async () => {
    const user = userEvent.setup();
    const pushState = vi.spyOn(window.history, "pushState");
    const replaceState = vi.spyOn(window.history, "replaceState");

    render(<Navbar onOpenAuth={vi.fn()} />);
    const featuresButtons = screen.getAllByRole("button", { name: "Features" });

    expect(featuresButtons[0]).not.toHaveAttribute("href");
    await user.click(featuresButtons[0]);

    expect(scrollFromHeaderNavigationMock).toHaveBeenCalledWith(
      document.getElementById("features"),
      52,
    );
    expect(window.location.href).toBe("http://localhost:3000/");
    expect(pushState).not.toHaveBeenCalled();
    expect(replaceState).not.toHaveBeenCalled();
  });

  it("scrolls the brand to the page top without a header offset", async () => {
    const user = userEvent.setup();
    render(<Navbar onOpenAuth={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Back to top" }));

    expect(scrollFromHeaderNavigationMock).toHaveBeenCalledWith(
      document.getElementById("top"),
      0,
    );
  });
});
