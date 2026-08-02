export type DashboardTopLevelRoute =
  | "/dashboard/documents"
  | "/dashboard/collections"
  | "/dashboard/ask-question"
  | "/dashboard/history";

export type DashboardNavigationIcon =
  | "document"
  | "collection"
  | "question"
  | "history";

export type DashboardRouteId =
  | "documents"
  | "collections"
  | "collection-detail"
  | "ask-question"
  | "history";

export type DashboardHeaderActionMetadata = {
  id: "create-collection" | "upload-to-collection";
  label: string;
};

type DashboardBaseRouteMetadata = {
  id: DashboardRouteId;
  headerTitle: string;
  contextualLabel?: string;
  parent?: Exclude<DashboardRouteId, "collection-detail">;
  secondaryActions?: readonly DashboardHeaderActionMetadata[];
};

export type DashboardNavigationItem = DashboardBaseRouteMetadata & {
  href: DashboardTopLevelRoute;
  icon: DashboardNavigationIcon;
  navigationLabel: string;
  showInSidebar: true;
};

type DashboardNestedRouteMetadata = DashboardBaseRouteMetadata & {
  href: string;
  match: (pathname: string) => boolean;
  showInSidebar: false;
};

export type DashboardRouteMetadata =
  | DashboardNavigationItem
  | DashboardNestedRouteMetadata;

const topLevelRoutes = [
  {
    id: "documents",
    href: "/dashboard/documents",
    headerTitle: "Documents",
    icon: "document",
    navigationLabel: "Documents",
    showInSidebar: true,
  },
  {
    id: "collections",
    href: "/dashboard/collections",
    headerTitle: "Collections",
    icon: "collection",
    navigationLabel: "Collections",
    secondaryActions: [
      { id: "create-collection", label: "Create Collection" },
    ],
    showInSidebar: true,
  },
  {
    id: "ask-question",
    href: "/dashboard/ask-question",
    headerTitle: "Ask Question",
    icon: "question",
    navigationLabel: "Ask Question",
    showInSidebar: true,
  },
  {
    id: "history",
    href: "/dashboard/history",
    headerTitle: "History",
    icon: "history",
    navigationLabel: "History",
    showInSidebar: true,
  },
] as const satisfies readonly DashboardNavigationItem[];

const nestedRoutes = [
  {
    id: "collection-detail",
    href: "/dashboard/collections/[collectionId]",
    headerTitle: "Collection",
    contextualLabel: "Collection details",
    match: (pathname: string) =>
      /^\/dashboard\/collections\/[^/]+\/?$/.test(pathname),
    parent: "collections",
    secondaryActions: [
      { id: "upload-to-collection", label: "Upload to collection" },
    ],
    showInSidebar: false,
  },
] as const satisfies readonly DashboardNestedRouteMetadata[];

export const dashboardRoutes = [
  ...topLevelRoutes,
  ...nestedRoutes,
] as const satisfies readonly DashboardRouteMetadata[];

/** Sidebar navigation is derived from the same metadata as the shared header. */
export const dashboardNavigationItems: readonly DashboardNavigationItem[] =
  topLevelRoutes;

export function getDashboardRouteById(
  id: DashboardRouteId,
): DashboardRouteMetadata | undefined {
  return dashboardRoutes.find((route) => route.id === id);
}

export function resolveDashboardRoute(
  pathname: string,
): DashboardRouteMetadata | undefined {
  const normalizedPathname =
    pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  const nestedRoute = nestedRoutes.find((route) => route.match(normalizedPathname));
  if (nestedRoute) return nestedRoute;

  return topLevelRoutes.find((route) => route.href === normalizedPathname);
}

export function getDashboardParentRoute(
  route: DashboardRouteMetadata | undefined,
): DashboardNavigationItem | undefined {
  if (!route?.parent) return undefined;

  return topLevelRoutes.find((candidate) => candidate.id === route.parent);
}

export function isDashboardNavigationItemActive(
  pathname: string,
  href: DashboardTopLevelRoute,
): boolean {
  const route = resolveDashboardRoute(pathname);
  if (!route) return false;

  if (route.showInSidebar) return route.href === href;

  return getDashboardParentRoute(route)?.href === href;
}

/**
 * Accept a return target only when it resolves to the known parent route.
 * This preserves list query state without allowing unrelated or external URLs.
 */
export function resolveDashboardBackHref(
  returnTo: string | null | undefined,
  parentHref: DashboardTopLevelRoute,
): string {
  if (!returnTo) return parentHref;

  try {
    const url = new URL(returnTo, "https://sourcewise.local");
    if (
      url.origin !== "https://sourcewise.local" ||
      url.pathname !== parentHref
    ) {
      return parentHref;
    }

    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return parentHref;
  }
}

export function appendDashboardReturnTo(
  href: string,
  returnTo: string,
): string {
  const query = new URLSearchParams({ returnTo });
  return `${href}?${query.toString()}`;
}
