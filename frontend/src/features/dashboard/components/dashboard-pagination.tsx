import { ChevronLeft, ChevronRight, MoreHorizontal } from "lucide-react";
import { getPaginationItems } from "@/features/collections/collection-detail-utils";
import styles from "./dashboard-pagination.module.css";

type DashboardPaginationProps = {
  ariaLabel: string;
  currentPage: number;
  onPageChange: (page: number) => void;
  pageCount: number;
  pageSize: number;
  total: number;
};

export function DashboardPagination({
  ariaLabel,
  currentPage,
  onPageChange,
  pageCount,
  pageSize,
  total,
}: DashboardPaginationProps) {
  const first = total === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const last = Math.min(currentPage * pageSize, total);

  return (
    <div className={styles.paginationBar}>
      <p>
        Showing {first}–{last} of {total}
      </p>
      <nav aria-label={ariaLabel} className={styles.paginationControls}>
        <button
          aria-label="Go to previous page"
          className={styles.paginationDirection}
          disabled={currentPage === 1}
          onClick={() => onPageChange(currentPage - 1)}
          type="button"
        >
          <ChevronLeft aria-hidden="true" />
          <span>Previous</span>
        </button>
        <ol>
          {getPaginationItems(currentPage, pageCount).map((item, index) =>
            item === "ellipsis" ? (
              <li className={styles.paginationEllipsis} key={`ellipsis-${index}`}>
                <MoreHorizontal aria-hidden="true" />
                <span className="sr-only">More pages</span>
              </li>
            ) : (
              <li key={item}>
                <button
                  aria-current={item === currentPage ? "page" : undefined}
                  aria-label={`Go to page ${item}`}
                  className={styles.paginationPage}
                  onClick={() => onPageChange(item)}
                  type="button"
                >
                  {item}
                </button>
              </li>
            ),
          )}
        </ol>
        <button
          aria-label="Go to next page"
          className={styles.paginationDirection}
          disabled={currentPage === pageCount}
          onClick={() => onPageChange(currentPage + 1)}
          type="button"
        >
          <span>Next</span>
          <ChevronRight aria-hidden="true" />
        </button>
      </nav>
    </div>
  );
}
