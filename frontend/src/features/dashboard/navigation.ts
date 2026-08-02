export type DashboardRoute =
  | "/dashboard/documents"
  | "/dashboard/collections"
  | "/dashboard/ask-question"
  | "/dashboard/history";

export type DashboardNavigationIcon =
  | "document"
  | "collection"
  | "question"
  | "history";

export type DashboardNavigationItem = {
  href: DashboardRoute;
  label: string;
  icon: DashboardNavigationIcon;
};

export const dashboardNavigationItems = [
  { href: "/dashboard/documents", label: "Documents", icon: "document" },
  { href: "/dashboard/collections", label: "Collections", icon: "collection" },
  { href: "/dashboard/ask-question", label: "Ask Question", icon: "question" },
  { href: "/dashboard/history", label: "History", icon: "history" },
] as const satisfies readonly DashboardNavigationItem[];

export function isDashboardNavigationItemActive(
  pathname: string,
  href: DashboardRoute,
): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
