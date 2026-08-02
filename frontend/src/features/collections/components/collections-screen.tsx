"use client";

import {
  useCallback,
  useMemo,
  useRef,
  type MouseEvent,
} from "react";
import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { DashboardPage } from "@/features/dashboard/components/dashboard-page";
import { useDashboardHeader } from "@/features/dashboard/components/dashboard-header-context";
import type { CollectionDraft } from "@/features/collections/collection-validation";
import { createPreviewDialog } from "@/features/collections/collection-dialog-state";
import { useCollectionsDialog } from "@/features/collections/hooks/use-collections-dialog";
import { useMockCollections } from "@/features/collections/hooks/use-mock-collections";
import {
  mockCollections,
  type CollectionsModalPreview,
  type CollectionsPreview,
} from "@/features/collections/mock-collections";
import { CollectionButton } from "./collection-button";
import { CollectionsContent } from "./collections-content";
import { CollectionsDialogs } from "./dialogs/collections-dialogs";
import styles from "./collections-screen.module.css";

type CollectionsScreenProps = {
  initialModal?: CollectionsModalPreview;
  initialPreview: CollectionsPreview;
  returnTo?: string;
};

export function CollectionsScreen({
  initialModal,
  initialPreview,
  returnTo = "/dashboard/collections",
}: CollectionsScreenProps) {
  const router = useRouter();
  const headerActionRef = useRef<HTMLButtonElement>(null);
  const {
    createCollection,
    deleteCollection,
    restoreMockCollections,
    updateCollection,
    viewState,
  } = useMockCollections(initialPreview);
  const initialCollections =
    viewState.status === "success" ? viewState.collections : mockCollections;
  const { closeDialog, dialog, openDialog } = useCollectionsDialog({
    fallbackFocusRef: headerActionRef,
    initialDialog: createPreviewDialog(initialModal, initialCollections),
  });
  const collections =
    viewState.status === "success" ? viewState.collections : [];

  const handleCreate = (draft: CollectionDraft) => {
    createCollection(draft);
    closeDialog();
  };

  const handleUpdate = (collectionId: string, draft: CollectionDraft) => {
    updateCollection(collectionId, draft);
    closeDialog();
  };

  const handleDelete = (collectionId: string) => {
    deleteCollection(collectionId);
    closeDialog();
  };

  const handleOpenCreate = useCallback(
    (event: MouseEvent<HTMLButtonElement>) =>
      openDialog({ type: "create" }, event.currentTarget),
    [openDialog],
  );
  const headerAction = useMemo(
    () => (
      <CollectionButton onClick={handleOpenCreate} ref={headerActionRef}>
        <Plus aria-hidden="true" />
        Create Collection
      </CollectionButton>
    ),
    [handleOpenCreate],
  );
  const headerConfiguration = useMemo(
    () => ({ actions: headerAction }),
    [headerAction],
  );
  useDashboardHeader(headerConfiguration);

  return (
    <DashboardPage>
      <div className={styles.content}>
        <CollectionsContent
          onBack={() => router.push("/dashboard/collections")}
          onOpenDialog={openDialog}
          onRetry={restoreMockCollections}
          returnTo={returnTo}
          viewState={viewState}
        />
      </div>
      <CollectionsDialogs
        collections={collections}
        dialog={dialog}
        onClose={closeDialog}
        onCreate={handleCreate}
        onDelete={handleDelete}
        onUpdate={handleUpdate}
      />
    </DashboardPage>
  );
}
