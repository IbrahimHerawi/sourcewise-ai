export function formatResultRange(
  currentPage: number,
  pageSize: number,
  total: number,
): string {
  if (total === 0) return "0";
  const first = (currentPage - 1) * pageSize + 1;
  const last = Math.min(currentPage * pageSize, total);
  return `${first}–${last}`;
}

export type PaginationItem = number | "ellipsis";

export function getPaginationItems(
  currentPage: number,
  pageCount: number,
): readonly PaginationItem[] {
  if (pageCount <= 5) {
    return Array.from({ length: pageCount }, (_, index) => index + 1);
  }
  if (currentPage <= 3) return [1, 2, 3, "ellipsis", pageCount];
  if (currentPage >= pageCount - 2) {
    return [1, "ellipsis", pageCount - 2, pageCount - 1, pageCount];
  }
  return [1, "ellipsis", currentPage, "ellipsis", pageCount];
}
