"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { DashboardPage } from "@/features/dashboard/components/dashboard-page";
import { useDashboardHeader } from "@/features/dashboard/components/dashboard-header-context";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";
import {
  createUploadQueue,
  DOCUMENT_FILE_TYPE_LABELS,
  hasBlockingUploadError,
  isSupportedDocumentExtension,
  type SupportedDocumentExtension,
} from "../file-validation";
import {
  getDocumentsListError,
  getDocumentsRefreshError,
  getUploadErrorMessage,
} from "../documents-error-utils";
import { useDocumentProcessingPolling } from "../hooks/use-document-processing-polling";
import {
  useDocumentCollections,
  useDocumentsList,
  useUploadDocumentsMutation,
} from "../hooks/use-documents-api";
import type {
  DocumentDialogState,
  DocumentRecord,
  UploadQueueItem,
} from "../types";
import { DeleteDocumentDialog, DocumentDetailsPanel } from "./document-dialogs";
import { DocumentList, DocumentsToolbar } from "./document-library";
import { DocumentUploadCard } from "./document-upload-card";
import {
  DocumentsEmptyState,
  DocumentsErrorState,
  DocumentsRefreshNotice,
  DocumentsSkeleton,
  DocumentsZeroResultsState,
} from "./documents-states";
import styles from "./documents-page.module.css";

const ALL_COLLECTIONS_FILTER = "all";
const PAGE_SIZE = 20;

export function DocumentsScreen() {
  const { logout } = useAuth();
  const headerConfiguration = useMemo(() => ({ title: "Documents" }), []);
  useDashboardHeader(headerConfiguration);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const dialogTriggerRef = useRef<HTMLElement>(null);
  const libraryRef = useRef<HTMLElement>(null);
  const [queue, setQueue] = useState<UploadQueueItem[]>([]);
  const [filter, setFilter] = useState(ALL_COLLECTIONS_FILTER);
  const [fileTypeFilter, setFileTypeFilter] =
    useState<SupportedDocumentExtension | null>(null);
  const [uploadCollectionId, setUploadCollectionId] = useState<string | null>(
    null,
  );
  const [currentPage, setCurrentPage] = useState(1);
  const [dialog, setDialog] = useState<DocumentDialogState>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string>();

  const collectionId =
    filter === ALL_COLLECTIONS_FILTER ? null : filter;
  const documentsRequest = useDocumentsList({
    collectionId,
    fileType: fileTypeFilter,
    limit: PAGE_SIZE,
    offset: (currentPage - 1) * PAGE_SIZE,
  });
  const collectionsRequest = useDocumentCollections();
  const uploadMutation = useUploadDocumentsMutation();

  const documentData =
    documentsRequest.status === "success"
      ? documentsRequest.data
      : undefined;
  const documentRefreshError =
    documentsRequest.status === "success"
      ? documentsRequest.refreshError
      : undefined;
  useDocumentProcessingPolling({
    data: documentData,
    isRefreshing:
      documentsRequest.status === "success"
        ? documentsRequest.isRefreshing
        : false,
    refetch: documentsRequest.refetch,
  });

  useEffect(() => {
    const errors = [
      documentsRequest.status === "error"
        ? documentsRequest.error
        : undefined,
      collectionsRequest.status === "error"
        ? collectionsRequest.error
        : undefined,
      uploadMutation.error,
    ];
    if (
      errors.some(
        (error) => error instanceof ApiError && error.status === 401,
      )
    ) {
      logout();
    }
  }, [
    collectionsRequest.error,
    collectionsRequest.status,
    documentsRequest.error,
    documentsRequest.status,
    logout,
    uploadMutation.error,
  ]);

  const changePage = useCallback((page: number) => {
    setCurrentPage(Math.max(1, page));
    libraryRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  useEffect(() => {
    if (documentsRequest.status !== "success") return;
    const lastPage = Math.max(
      1,
      Math.ceil(
        documentsRequest.data.total / documentsRequest.data.limit,
      ),
    );
    if (currentPage > lastPage) setCurrentPage(lastPage);
  }, [currentPage, documentsRequest.data, documentsRequest.status]);

  useEffect(() => {
    if (
      documentsRequest.status === "error" &&
      documentsRequest.error instanceof ApiError &&
      documentsRequest.error.status === 404 &&
      filter !== ALL_COLLECTIONS_FILTER
    ) {
      setFilter(ALL_COLLECTIONS_FILTER);
      setCurrentPage(1);
    }
  }, [documentsRequest.error, documentsRequest.status, filter]);

  useEffect(() => {
    if (
      collectionsRequest.status === "success" &&
      filter !== ALL_COLLECTIONS_FILTER &&
      !collectionsRequest.data.some((collection) => collection.id === filter)
    ) {
      setFilter(ALL_COLLECTIONS_FILTER);
      setCurrentPage(1);
    }
    if (
      collectionsRequest.status === "success" &&
      uploadCollectionId !== null &&
      !collectionsRequest.data.some(
        (collection) => collection.id === uploadCollectionId,
      )
    ) {
      setUploadCollectionId(null);
    }
  }, [
    collectionsRequest.data,
    collectionsRequest.status,
    filter,
    uploadCollectionId,
  ]);

  const resetUploadFeedback = () => {
    uploadMutation.reset();
    setUploadSuccess(undefined);
  };
  const selectFiles = (files: readonly File[]) => {
    if (uploadMutation.isPending) return;
    resetUploadFeedback();
    setQueue((current) =>
      createUploadQueue([
        ...current.map((item) => item.file),
        ...files,
      ]),
    );
  };
  const removeFile = (id: string) => {
    if (uploadMutation.isPending) return;
    resetUploadFeedback();
    setQueue((current) =>
      createUploadQueue(
        current
          .filter((item) => item.id !== id)
          .map((item) => item.file),
      ),
    );
  };
  const changeUploadCollection = (nextCollectionId: string | null) => {
    if (uploadMutation.isPending) return;
    resetUploadFeedback();
    setUploadCollectionId(nextCollectionId);
  };
  const uploadFiles = () => {
    if (
      uploadMutation.isPending ||
      queue.length === 0 ||
      hasBlockingUploadError(queue)
    ) {
      return;
    }

    const files = queue.map((item) => item.file);
    const targetFilter =
      uploadCollectionId ?? ALL_COLLECTIONS_FILTER;
    setUploadSuccess(undefined);
    void uploadMutation
      .mutate({ collectionId: uploadCollectionId, files })
      .then((response) => {
        const acceptedCount = response.items.length;
        setQueue([]);
        setUploadSuccess(
          `${acceptedCount} ${
            acceptedCount === 1 ? "document was" : "documents were"
          } accepted and queued for processing.`,
        );

        if (filter !== targetFilter) {
          setFilter(targetFilter);
          setCurrentPage(1);
        } else if (currentPage !== 1) {
          setCurrentPage(1);
        } else {
          void documentsRequest.refetch().catch(() => undefined);
        }
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.code === "invalid_response") {
          void documentsRequest
            .refetch({ silent: true })
            .catch(() => undefined);
        }
      });
  };

  const openDialog = (
    nextDialog: Exclude<DocumentDialogState, null>,
    opener: HTMLElement,
  ) => {
    dialogTriggerRef.current = opener;
    setDialog(nextDialog);
  };
  const closeDialog = () => {
    const restoreTarget = dialogTriggerRef.current;
    setDialog(null);
    requestAnimationFrame(() => restoreTarget?.focus());
  };
  const handleDeleted = (document: DocumentRecord) => {
    setDialog(null);
    dialogTriggerRef.current = null;

    if (
      currentPage > 1 &&
      documentsRequest.status === "success" &&
      documentsRequest.data.items.length === 1
    ) {
      setCurrentPage((page) => page - 1);
    } else {
      void documentsRequest.refetch().catch(() => undefined);
    }
    requestAnimationFrame(() => libraryRef.current?.focus());
  };

  const collections =
    collectionsRequest.status === "success"
      ? collectionsRequest.data
      : [];
  const selectedCollection = collections.find(
    (collection) => collection.id === filter,
  );
  const listError =
    documentsRequest.status === "error"
      ? getDocumentsListError(documentsRequest.error)
      : undefined;
  const pageCount = documentData
    ? Math.max(1, Math.ceil(documentData.total / documentData.limit))
    : 1;

  return (
    <DashboardPage>
      <div className={styles.pageContent}>
        <DocumentUploadCard
          collectionOptions={collections}
          collectionsUnavailable={collectionsRequest.status === "error"}
          fileInputRef={fileInputRef}
          isUploading={uploadMutation.isPending}
          onCollectionChange={changeUploadCollection}
          onFilesSelected={selectFiles}
          onRemove={removeFile}
          onUpload={uploadFiles}
          queue={queue}
          selectedCollectionId={uploadCollectionId}
          serverError={
            uploadMutation.error
              ? getUploadErrorMessage(uploadMutation.error)
              : undefined
          }
          submissionBlocked={
            uploadMutation.error instanceof ApiError &&
            uploadMutation.error.code === "invalid_response"
          }
          successMessage={uploadSuccess}
        />
        <section
          aria-label="Document library"
          aria-busy={
            documentsRequest.status === "success"
              ? documentsRequest.isRefreshing
              : undefined
          }
          className={styles.library}
          ref={libraryRef}
          tabIndex={-1}
        >
          {documentsRequest.status === "loading" ? (
            <DocumentsSkeleton />
          ) : documentsRequest.status === "error" && listError ? (
            <DocumentsErrorState
              description={listError.description}
              onRetry={() =>
                void documentsRequest.refetch().catch(() => undefined)
              }
              title={listError.title}
            />
          ) : documentData ? (
            <>
              <DocumentsToolbar
                collections={collections}
                filter={filter}
                fileType={fileTypeFilter ?? "all"}
                onFilterChange={(value) => {
                  setFilter(value);
                  setCurrentPage(1);
                }}
                onFileTypeChange={(value) => {
                  setFileTypeFilter(
                    isSupportedDocumentExtension(value) ? value : null,
                  );
                  setCurrentPage(1);
                }}
                showCollectionFilter={
                  collectionsRequest.status === "success" &&
                  collections.length > 0 &&
                  (documentData.total > 0 ||
                    filter !== ALL_COLLECTIONS_FILTER)
                }
                showFileTypeFilter={
                  documentData.total > 0 ||
                  filter !== ALL_COLLECTIONS_FILTER ||
                  fileTypeFilter !== null
                }
              />
              {documentRefreshError ? (
                <DocumentsRefreshNotice
                  message={getDocumentsRefreshError(
                    documentRefreshError,
                  )}
                  onRetry={() =>
                    void documentsRequest
                      .refetch({ silent: true })
                      .catch(() => undefined)
                  }
                />
              ) : null}
              {filter === ALL_COLLECTIONS_FILTER &&
              fileTypeFilter === null &&
              documentData.total === 0 ? (
                <DocumentsEmptyState
                  onChooseFiles={() => fileInputRef.current?.click()}
                />
              ) : documentData.items.length === 0 ? (
                <DocumentsZeroResultsState
                  collectionName={
                    filter === ALL_COLLECTIONS_FILTER
                      ? undefined
                      : selectedCollection?.name ?? "this collection"
                  }
                  fileTypeLabel={
                    fileTypeFilter
                      ? DOCUMENT_FILE_TYPE_LABELS[fileTypeFilter]
                      : undefined
                  }
                  onShowAll={() => {
                    setFilter(ALL_COLLECTIONS_FILTER);
                    setFileTypeFilter(null);
                    setCurrentPage(1);
                  }}
                />
              ) : (
                <DocumentList
                  currentPage={currentPage}
                  documents={documentData.items}
                  onDelete={(document, opener) =>
                    openDialog({ type: "delete", document }, opener)
                  }
                  onOpenDetails={(document, opener) =>
                    openDialog({ type: "details", document }, opener)
                  }
                  onPageChange={changePage}
                  pageCount={pageCount}
                  pageSize={documentData.limit}
                  total={documentData.total}
                />
              )}
            </>
          ) : null}
        </section>
      </div>
      {dialog?.type === "details" ? (
        <DocumentDetailsPanel
          document={dialog.document}
          onClose={closeDialog}
        />
      ) : null}
      {dialog?.type === "delete" ? (
        <DeleteDocumentDialog
          document={dialog.document}
          onClose={closeDialog}
          onDeleted={() => handleDeleted(dialog.document)}
        />
      ) : null}
    </DashboardPage>
  );
}
