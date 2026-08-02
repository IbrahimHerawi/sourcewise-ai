import { describe, expect, it } from "vitest";
import {
  dashboardNavigationItems,
  getDashboardParentRoute,
  isDashboardNavigationItemActive,
  resolveDashboardBackHref,
  resolveDashboardRoute,
} from "./navigation";

describe("dashboard route metadata", () => {
  it("drives sidebar and top-level header labels from one source", () => {
    for (const item of dashboardNavigationItems) {
      expect(resolveDashboardRoute(item.href)?.headerTitle).toBe(
        item.navigationLabel,
      );
    }
  });

  it("resolves nested collection hierarchy and parent active state", () => {
    const detail = resolveDashboardRoute(
      "/dashboard/collections/quarterly-research",
    );

    expect(detail?.headerTitle).toBe("Collection");
    expect(getDashboardParentRoute(detail)?.headerTitle).toBe("Collections");
    expect(
      isDashboardNavigationItemActive(
        "/dashboard/collections/quarterly-research",
        "/dashboard/collections",
      ),
    ).toBe(true);
  });

  it("preserves a safe parent query and rejects unrelated return targets", () => {
    expect(
      resolveDashboardBackHref(
        "/dashboard/collections?page=3&query=policy",
        "/dashboard/collections",
      ),
    ).toBe("/dashboard/collections?page=3&query=policy");
    expect(
      resolveDashboardBackHref(
        "https://example.com/dashboard/collections",
        "/dashboard/collections",
      ),
    ).toBe("/dashboard/collections");
    expect(
      resolveDashboardBackHref(
        "/dashboard/history",
        "/dashboard/collections",
      ),
    ).toBe("/dashboard/collections");
  });
});
