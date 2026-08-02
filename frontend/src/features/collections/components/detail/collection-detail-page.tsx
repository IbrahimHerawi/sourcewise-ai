"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import { ApiError, getApiErrorMessage } from "@/lib/api";
import { useDashboardHeader } from "@/features/dashboard/components/dashboard-header-context";
import { resolveDashboardBackHref } from "@/features/dashboard/navigation";
import type { CollectionDetailTab } from "@/features/collections/collection-detail-types";
import type {
  CollectionDocument,
  QuestionHistoryItem,
} from "@/features/collections/collections-api-types";
import { useCollectionsDialog } from "@/features/collections/hooks/use-collections-dialog";
import {
  useCollectionDocuments,
  useCollectionHistory,
  useCollectionRecord,
} from "@/features/collections/hooks/use-collections-api";
import { CollectionButton } from "../collection-button";
import { CollectionsDialogs } from "../dialogs/collections-dialogs";
import { CollectionDetailContent } from "./collection-detail-content";
import { CollectionDetailLayout } from "./collection-detail-layout";
import {
  CollectionDetailErrorState,
  CollectionDetailSkeleton,
} from "./collection-detail-states";
import {
  DeleteDocumentDialog,
  DocumentDetailsDialog,
} from "./document-dialogs";
import {
  DeleteHistoryDialog,
  HistoryDetailsDialog,
} from "./history-dialogs";
import { UploadCollectionDialog } from "./upload-collection-dialog";

type CollectionDetailPageProps = {
  collectionId: string;
  initialTab?: CollectionDetailTab;
};

type DocumentDialogState =
  | { type: "details"; document: CollectionDocument }
  | { type: "delete"; document: CollectionDocument }
  | null;

type HistoryDialogState =
  | { type: "details"; item: QuestionHistoryItem }
  | { type: "delete"; item: QuestionHistoryItem }
  | null;

const PAGE_SIZE = 20;
const PROCESSING_POLL_INTERVAL_MS = 2_500;

export function CollectionDetailPage({
  collectionId,
  initialTab = "documents",
}: CollectionDetailPageProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { logout } = useAuth();
  const fallbackFocusRef = useRef<HTMLButtonElement>(null);
  const [activeTab, setActiveTab] = useState<CollectionDetailTab>(initialTab);
  const [documentPage, setDocumentPage] = useState(1);
  const [historyPage, setHistoryPage] = useState(1);
  const [documentDialog, setDocumentDialog] = useState<DocumentDialogState>(null);
  const [historyDialog, setHistoryDialog] = useState<HistoryDialogState>(null);
  const [showUpload, setShowUpload] = useState(false);
  const collectionRequest = useCollectionRecord(collectionId);
  const documentsRequest = useCollectionDocuments(
    collectionId,
    PAGE_SIZE,
    (documentPage - 1) * PAGE_SIZE,
  );
  const historyRequest = useCollectionHistory(
    collectionId,
    PAGE_SIZE,
    (historyPage - 1) * PAGE_SIZE,
  );
  const { closeDialog, dialog, openDialog } = useCollectionsDialog({
    fallbackFocusRef,
    initialDialog: null,
  });

  const requests = [collectionRequest, documentsRequest, historyRequest] as const;
  const firstError = requests.find((request) => request.status === "error");

  useEffect(() => {
    if (firstError?.status === "error" && firstError.error instanceof ApiError) {
      if (firstError.error.status === 401) logout();
    }
  }, [firstError, logout]);

  useEffect(() => {
    if (
      documentsRequest.status !== "success" ||
      !documentsRequest.data.items.some((document) =>
        document.status === "PENDING" || document.status === "PROCESSING"
      )
    ) {
      return;
    }
    const timer = window.setTimeout(() => {
      void documentsRequest.refetch({ silent: true }).catch(() => undefined);
    }, PROCESSING_POLL_INTERVAL_MS);
    return () => window.clearTimeout(timer);
  }, [documentsRequest]);

  const backHref = resolveDashboardBackHref(
    searchParams?.get("returnTo"),
    "/dashboard/collections",
  );
  const collection = collectionRequest.status === "success" ? collectionRequest.data : undefined;

  const headerActions = useMemo(
    () =>
      collection ? (
        <CollectionButton onClick={() => setShowUpload(true)} shape="pill">
          Upload to collection
        </CollectionButton>
      ) : undefined,
    [collection],
  );
  const headerConfiguration = useMemo(
    () => ({ actions: headerActions, title: collection?.name ?? "Collection" }),
    [collection?.name, headerActions],
  );
  useDashboardHeader(headerConfiguration);

  const refetchAll = useCallback(() => {
    void Promise.allSettled([
      collectionRequest.refetch(),
      documentsRequest.refetch(),
      historyRequest.refetch(),
    ]);
  }, [collectionRequest, documentsRequest, historyRequest]);

  const handleTabChange = (tab: CollectionDetailTab) => {
    setActiveTab(tab);
    const nextSearchParams = new URLSearchParams(searchParams?.toString());
    nextSearchParams.set("tab", tab);
    router.replace(`/dashboard/collections/${collectionId}?${nextSearchParams}`, {
      scroll: false,
    });
  };

  if (requests.some((request) => request.status === "loading")) {
    return (
      <CollectionDetailLayout>
        <CollectionDetailSkeleton />
      </CollectionDetailLayout>
    );
  }

  if (firstError?.status === "error") {
    const status = firstError.error instanceof ApiError ? firstError.error.status : 0;
    const kind = status === 404 ? "not-found" : status === 403 ? "forbidden" : "server-error";
    return (
      <CollectionDetailLayout>
        <CollectionDetailErrorState
          description={
            kind === "server-error"
              ? getApiErrorMessage(firstError.error, "The collection could not be loaded. Try again.")
              : undefined
          }
          kind={kind}
          onAction={kind === "server-error" ? refetchAll : () => router.push(backHref)}
        />
      </CollectionDetailLayout>
    );
  }

  if (
    collectionRequest.status !== "success" ||
    documentsRequest.status !== "success" ||
    historyRequest.status !== "success"
  ) {
    return null;
  }

  const resolvedCollection = collectionRequest.data;
  const closeDocumentDialog = () => setDocumentDialog(null);
  const closeHistoryDialog = () => setHistoryDialog(null);

  return (
    <CollectionDetailLayout>
      <CollectionDetailContent
        activeTab={activeTab}
        documentPage={documentPage}
        documents={documentsRequest.data}
        history={historyRequest.data}
        historyPage={historyPage}
        onAsk={() => router.push(`/dashboard/ask-question?collectionId=${resolvedCollection.id}`)}
        onDelete={(opener) => openDialog({ type: "delete", collection: resolvedCollection }, opener)}
        onDeleteDocument={(document) => setDocumentDialog({ type: "delete", document })}
        onDeleteHistory={(item) => setHistoryDialog({ type: "delete", item })}
        onDocumentPageChange={setDocumentPage}
        onEdit={(opener) => openDialog({ type: "edit", collection: resolvedCollection }, opener)}
        onHistoryPageChange={setHistoryPage}
        onTabChange={handleTabChange}
        onUpload={() => setShowUpload(true)}
        onViewDocument={(document) => setDocumentDialog({ type: "details", document })}
        onViewHistory={(item) => setHistoryDialog({ type: "details", item })}
      />
      <CollectionsDialogs
        dialog={dialog}
        onClose={closeDialog}
        onCreated={() => undefined}
        onDeleted={() => router.push("/dashboard/collections")}
        onUpdated={() => {
          closeDialog();
          void collectionRequest.refetch().catch(() => undefined);
        }}
      />
      {showUpload ? (
        <UploadCollectionDialog
          collectionId={collectionId}
          onClose={() => setShowUpload(false)}
          onUploaded={() => {
            setShowUpload(false);
            setDocumentPage(1);
            void documentsRequest.refetch().catch(() => undefined);
          }}
        />
      ) : null}
      {documentDialog?.type === "details" ? (
        <DocumentDetailsDialog documentId={documentDialog.document.id} onClose={closeDocumentDialog} />
      ) : null}
      {documentDialog?.type === "delete" ? (
        <DeleteDocumentDialog
          document={documentDialog.document}
          onClose={closeDocumentDialog}
          onDeleted={() => {
            closeDocumentDialog();
            void documentsRequest.refetch().catch(() => undefined);
          }}
        />
      ) : null}
      {historyDialog?.type === "details" ? (
        <HistoryDetailsDialog questionId={historyDialog.item.question_id} onClose={closeHistoryDialog} />
      ) : null}
      {historyDialog?.type === "delete" ? (
        <DeleteHistoryDialog
          item={historyDialog.item}
          onClose={closeHistoryDialog}
          onDeleted={() => {
            closeHistoryDialog();
            void historyRequest.refetch().catch(() => undefined);
          }}
        />
      ) : null}
    </CollectionDetailLayout>
  );
}
