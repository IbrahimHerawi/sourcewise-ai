import type { CollectionsDialogState } from "@/features/collections/collection-dialog-state";
import type {
  Collection,
  CollectionsViewState,
} from "@/features/collections/collection-types";
import { CollectionsList } from "./collection-list";
import {
  CollectionNotFoundState,
  CollectionsEmptyState,
  CollectionsErrorState,
  CollectionsLoadingState,
} from "./collections-page-states";

type CollectionsContentProps = {
  onBack: () => void;
  onOpenDialog: (
    dialog: CollectionsDialogState,
    opener: HTMLElement,
  ) => void;
  onRetry: () => void;
  returnTo: string;
  viewState: CollectionsViewState;
};

export function CollectionsContent({
  onBack,
  onOpenDialog,
  onRetry,
  returnTo,
  viewState,
}: CollectionsContentProps) {
  if (viewState.status === "loading") {
    return <CollectionsLoadingState />;
  }

  if (viewState.status === "error") {
    return <CollectionsErrorState onRetry={onRetry} />;
  }

  if (viewState.status === "not-found") {
    return <CollectionNotFoundState onBack={onBack} />;
  }

  if (viewState.collections.length === 0) {
    return (
      <CollectionsEmptyState
        onCreate={(opener) => onOpenDialog({ type: "create" }, opener)}
      />
    );
  }

  const openCollectionDialog =
    (type: "edit" | "delete") =>
    (collection: Collection, opener: HTMLButtonElement) => {
      onOpenDialog({ type, collection }, opener);
    };

  return (
    <CollectionsList
      collections={viewState.collections}
      onDelete={openCollectionDialog("delete")}
      onEdit={openCollectionDialog("edit")}
      returnTo={returnTo}
    />
  );
}
