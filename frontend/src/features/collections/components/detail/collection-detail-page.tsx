"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { CollectionDraft } from "@/features/collections/collection-validation";
import type {
  CollectionDetail,
  CollectionDetailTab,
  CollectionDetailViewState,
} from "@/features/collections/collection-detail-types";
import type { Collection } from "@/features/collections/collection-types";
import { useCollectionsDialog } from "@/features/collections/hooks/use-collections-dialog";
import {
  createCollectionDetailState,
  createTabState,
  type CollectionDetailPreview,
} from "@/features/collections/mock-collection-detail";
import { mockCollections } from "@/features/collections/mock-collections";
import { CollectionsDialogs } from "../dialogs/collections-dialogs";
import { CollectionDetailContent } from "./collection-detail-content";
import { CollectionDetailLayout } from "./collection-detail-layout";
import {
  CollectionDetailErrorState,
  CollectionDetailSkeleton,
} from "./collection-detail-states";

type CollectionDetailPageProps = {
  collectionId: string;
  initialPreview: CollectionDetailPreview;
};

function stateCollection(state: CollectionDetailViewState) {
  return "collection" in state ? state.collection : undefined;
}

function updateStateCollection(
  state: CollectionDetailViewState,
  update: (collection: CollectionDetail) => CollectionDetail,
): CollectionDetailViewState {
  return "collection" in state
    ? { ...state, collection: update(state.collection) }
    : state;
}

export function CollectionDetailPage({
  collectionId,
  initialPreview,
}: CollectionDetailPageProps) {
  const router = useRouter();
  const fallbackFocusRef = useRef<HTMLButtonElement>(null);
  const [viewState, setViewState] = useState<CollectionDetailViewState>(() =>
    createCollectionDetailState(collectionId, initialPreview),
  );
  const { closeDialog, dialog, openDialog } = useCollectionsDialog({
    fallbackFocusRef,
    initialDialog: null,
  });
  const collection = stateCollection(viewState);
  const validationCollections: readonly Collection[] = collection
    ? [collection, ...mockCollections.filter((item) => item.id !== collection.id)]
    : mockCollections;

  const handleTabChange = (tab: CollectionDetailTab) => {
    if (!collection) return;
    setViewState(createTabState(collection, tab));
    router.replace(`/dashboard/collections/${collection.id}?tab=${tab}`, {
      scroll: false,
    });
  };

  const handleUpdate = (id: string, draft: CollectionDraft) => {
    setViewState((current) =>
      updateStateCollection(current, (item) =>
        item.id === id
          ? {
              ...item,
              name: draft.name,
              description: draft.description || undefined,
              updated: "Updated just now",
            }
          : item,
      ),
    );
    closeDialog();
  };

  const handleDelete = () => {
    setViewState({ status: "not-found" });
    closeDialog();
  };

  const handleRetry = () => {
    setViewState(createCollectionDetailState(collectionId, "documents"));
  };

  if (viewState.status === "loading") {
    return (
      <CollectionDetailLayout isLoading>
        <CollectionDetailSkeleton />
      </CollectionDetailLayout>
    );
  }

  if (viewState.status === "not-found" || viewState.status === "server-error") {
    return (
      <CollectionDetailLayout title="Collection">
        <CollectionDetailErrorState
          kind={viewState.status}
          onAction={
            viewState.status === "not-found"
              ? () => router.push("/dashboard/collections")
              : handleRetry
          }
        />
      </CollectionDetailLayout>
    );
  }

  const resolvedCollection = viewState.collection;
  const handleAsk = () =>
    router.push(`/dashboard/ask-question?collectionId=${resolvedCollection.id}`);
  const handleUpload = () =>
    router.push(`/dashboard/documents?collectionId=${resolvedCollection.id}`);

  return (
    <CollectionDetailLayout
      onUpload={handleUpload}
      title={resolvedCollection.name}
    >
      <CollectionDetailContent
        onAsk={handleAsk}
        onDelete={(opener) =>
          openDialog({ type: "delete", collection: resolvedCollection }, opener)
        }
        onEdit={(opener) =>
          openDialog({ type: "edit", collection: resolvedCollection }, opener)
        }
        onTabChange={handleTabChange}
        onUpload={handleUpload}
        state={viewState}
      />
      <CollectionsDialogs
        collections={validationCollections}
        dialog={dialog}
        onClose={closeDialog}
        onCreate={() => undefined}
        onDelete={handleDelete}
        onUpdate={handleUpdate}
      />
    </CollectionDetailLayout>
  );
}
