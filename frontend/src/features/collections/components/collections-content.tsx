import type { CollectionsDialogState } from "@/features/collections/collection-dialog-state";
import type { CollectionApiRecord, PaginatedResponse } from "@/features/collections/collections-api-types";
import type { RequestState } from "@/hooks/use-api-request";
import { getApiErrorMessage } from "@/lib/api";
import { CollectionsList } from "./collection-list";
import {
  CollectionsEmptyState,
  CollectionsErrorState,
  CollectionsLoadingState,
} from "./collections-page-states";

type CollectionsContentProps = {
  currentPage: number;
  onPageChange: (page: number) => void;
  onOpenDialog: (
    dialog: CollectionsDialogState,
    opener: HTMLElement,
  ) => void;
  onRetry: () => void;
  requestState: RequestState<PaginatedResponse<CollectionApiRecord>>;
};

export function CollectionsContent({
  currentPage,
  onPageChange,
  onOpenDialog,
  onRetry,
  requestState,
}: CollectionsContentProps) {
  if (requestState.status === "loading") {
    return <CollectionsLoadingState />;
  }

  if (requestState.status === "error") {
    return (
      <CollectionsErrorState
        message={getApiErrorMessage(
          requestState.error,
          "Collections could not be loaded. Check your connection and try again.",
        )}
        onRetry={onRetry}
      />
    );
  }

  if (requestState.data.items.length === 0) {
    return (
      <CollectionsEmptyState
        onCreate={(opener) => onOpenDialog({ type: "create" }, opener)}
      />
    );
  }

  const openCollectionDialog =
    (type: "edit" | "delete") =>
    (collection: CollectionApiRecord, opener: HTMLButtonElement) => {
      onOpenDialog({ type, collection }, opener);
    };

  return (
    <CollectionsList
      collections={requestState.data.items}
      currentPage={currentPage}
      onDelete={openCollectionDialog("delete")}
      onEdit={openCollectionDialog("edit")}
      onPageChange={onPageChange}
      pageCount={Math.max(1, Math.ceil(requestState.data.total / requestState.data.limit))}
      returnTo={currentPage > 1 ? `/dashboard/collections?page=${currentPage}` : "/dashboard/collections"}
    />
  );
}
