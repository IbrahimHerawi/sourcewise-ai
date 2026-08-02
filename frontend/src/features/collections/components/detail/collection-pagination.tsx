import { ChevronLeft, ChevronRight, MoreHorizontal } from "lucide-react";
import { getPaginationItems } from "@/features/collections/collection-detail-utils";
import styles from "./collection-detail.module.css";

type CollectionPaginationProps = {
  currentPage: number;
  onPageChange: (page: number) => void;
  pageCount: number;
};

export function CollectionPagination({
  currentPage,
  onPageChange,
  pageCount,
}: CollectionPaginationProps) {
  return (
    <nav aria-label="Collection content pagination" className={styles.pagination}>
      <button
        aria-label="Go to previous page"
        className={styles.paginationDirection}
        disabled={currentPage === 1}
        onClick={() => onPageChange(currentPage - 1)}
        type="button"
      >
        <ChevronLeft aria-hidden="true" />
        Previous
      </button>
      <ol className={styles.pageList}>
        {getPaginationItems(currentPage, pageCount).map((item, index) =>
          item === "ellipsis" ? (
            <li className={styles.ellipsis} key={`ellipsis-${index}`}>
              <MoreHorizontal aria-hidden="true" />
              <span className="sr-only">More pages</span>
            </li>
          ) : (
            <li key={item}>
              <button
                aria-current={item === currentPage ? "page" : undefined}
                aria-label={`Go to page ${item}`}
                className={styles.pageButton}
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
        Next
        <ChevronRight aria-hidden="true" />
      </button>
    </nav>
  );
}
