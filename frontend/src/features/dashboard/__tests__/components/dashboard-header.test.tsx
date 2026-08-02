import { createRef, useMemo } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DashboardHeader } from "@/features/dashboard/components/dashboard-header";
import {
  DashboardHeaderProvider,
  useDashboardHeader,
} from "@/features/dashboard/components/dashboard-header-context";

const navigationState = vi.hoisted(() => ({
  pathname: "/dashboard/collections",
  search: "",
}));

vi.mock("next/navigation", () => ({
  usePathname: () => navigationState.pathname,
  useSearchParams: () => new URLSearchParams(navigationState.search),
}));

function DynamicHeaderRegistration({ title }: { title: string }) {
  const configuration = useMemo(() => ({ title }), [title]);
  useDashboardHeader(configuration);
  return null;
}

function renderHeader({ dynamicTitle }: { dynamicTitle?: string } = {}) {
  const scrollContainer = document.createElement("div");
  Object.defineProperty(scrollContainer, "scrollTop", {
    configurable: true,
    value: 0,
    writable: true,
  });
  const scrollContainerRef = createRef<HTMLElement>();
  scrollContainerRef.current = scrollContainer;

  render(
    <DashboardHeaderProvider>
      <DashboardHeader scrollContainerRef={scrollContainerRef} />
      {dynamicTitle ? (
        <DynamicHeaderRegistration title={dynamicTitle} />
      ) : null}
    </DashboardHeaderProvider>,
  );

  return scrollContainer;
}

describe("DashboardHeader", () => {
  beforeEach(() => {
    navigationState.pathname = "/dashboard/collections";
    navigationState.search = "";
  });

  it("renders a top-level title from route metadata", () => {
    renderHeader();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Collections",
    );
    expect(screen.getByRole("banner")).toHaveAttribute("data-scrolled", "false");
  });

  it("renders dynamic nested context with an explicit safe parent link", () => {
    navigationState.pathname = "/dashboard/collections/quarterly-research";
    navigationState.search =
      "returnTo=%2Fdashboard%2Fcollections%3Fpage%3D3%26query%3Dpolicy";
    renderHeader({ dynamicTitle: "Quarterly Research" });

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Quarterly Research",
    );
    expect(screen.getByRole("link", { name: "Back to Collections" })).toHaveAttribute(
      "href",
      "/dashboard/collections?page=3&query=policy",
    );
  });

  it("adds elevation only after the content viewport scrolls", () => {
    const scrollContainer = renderHeader();
    const header = screen.getByRole("banner");

    expect(header).toHaveAttribute("data-scrolled", "false");
    scrollContainer.scrollTop = 12;
    fireEvent.scroll(scrollContainer);
    expect(header).toHaveAttribute("data-scrolled", "true");

    scrollContainer.scrollTop = 0;
    fireEvent.scroll(scrollContainer);
    expect(header).toHaveAttribute("data-scrolled", "false");
  });
});
