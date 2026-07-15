"use client";

import {
  type ChangeEvent,
  type DragEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  Eye,
  FileText,
  LoaderCircle,
  MoreHorizontal,
  RefreshCw,
  Trash2,
  Upload,
  X,
} from "lucide-react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
} from "@/components/ui/pagination";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAuth } from "@/hooks/use-auth";
import { useToast } from "@/hooks/use-toast";
import { DashboardPageHeader } from "@/features/dashboard/components/dashboard-page-header";
import {
  ApiError,
  api,
  getApiErrorMessage,
  type CollectionResponse,
  type DocumentStatus,
  type DocumentSummaryResponse,
  type PaginatedDocumentListResponse,
} from "@/lib/api";
import type { PendingUpload } from "@/features/dashboard/documents/types";

import styles from "./documents-page.module.css";

const PAGE_SIZE = 20;
const MAX_FILES_PER_UPLOAD = 3;

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";

  const units = ["B", "KB", "MB", "GB"];
  const unitIndex = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** unitIndex;
  const precision = value >= 10 || unitIndex === 0 ? 0 : 1;

  return `${value.toFixed(precision)} ${units[unitIndex]}`;
}

function formatRelativeDate(value: string): string {
  const createdAt = new Date(value).getTime();
  const elapsedSeconds = Math.max(0, Math.floor((Date.now() - createdAt) / 1000));

  if (elapsedSeconds < 60) return "Just now";
  if (elapsedSeconds < 3600) return `${Math.floor(elapsedSeconds / 60)} min ago`;
  if (elapsedSeconds < 86400) return `${Math.floor(elapsedSeconds / 3600)} hr ago`;
  if (elapsedSeconds < 604800) return `${Math.floor(elapsedSeconds / 86400)} days ago`;

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
  }).format(new Date(value));
}

function getFileTypeLabel(extension: string): string {
  return extension.startsWith(".") ? extension.toUpperCase() : `.${extension.toUpperCase()}`;
}

function getDocumentTypeClassName(extension: string): string {
  switch (extension.toLowerCase()) {
    case ".md":
      return styles.documentTypeMd;
    case ".txt":
      return styles.documentTypeTxt;
    case ".pdf":
      return styles.documentTypePdf;
    default:
      return styles.documentTypeOther;
  }
}

function getBackendErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.status === 401) {
    return "Your session has expired. Sign in again to manage documents.";
  }
  if (error instanceof ApiError && error.status === 403) {
    return "You do not have permission to manage documents.";
  }
  return getApiErrorMessage(error, fallback);
}

function UploadRow({
  item,
  onRemove,
  onUpload,
}: {
  item: PendingUpload;
  onRemove: (id: string) => void;
  onUpload: (item: PendingUpload) => void;
}) {
  return (
    <div className={`${styles.uploadRow} dashboard-surface`}>
      <div className={styles.fileIdentity}>
        <span className={styles.fileType} aria-hidden="true">
          <FileText />
          <span className={styles.visuallyHidden}>{getFileTypeLabel(item.file.name.split(".").pop() ?? "file")}</span>
        </span>
        <span className={styles.fileName}>{item.file.name}</span>
        <span className={styles.fileSize}>{formatBytes(item.file.size)}</span>
      </div>

      {item.status === "ready" ? (
        <Button
          className={styles.uploadButton}
          onClick={() => onUpload(item)}
          size="sm"
          type="button"
        >
          Upload
        </Button>
      ) : (
        <span className={styles.uploadingState} role="status">
          <RefreshCw className="animate-spin" aria-hidden="true" />
          Uploading...
        </span>
      )}

      <Button
        aria-label={`Remove ${item.file.name}`}
        className={styles.removeButton}
        disabled={item.status === "uploading"}
        onClick={() => onRemove(item.id)}
        size="icon"
        type="button"
        variant="ghost"
      >
        <X aria-hidden="true" />
      </Button>

      {item.error ? <p className={styles.uploadError}>{item.error}</p> : null}
    </div>
  );
}

function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  const statusClassName = {
    READY: styles.statusReady,
    PROCESSING: styles.statusProcessing,
    PENDING: styles.statusPending,
    FAILED: styles.statusFailed,
  }[status];

  const statusLabel = {
    READY: "Ready",
    PROCESSING: "Processing",
    PENDING: "Pending",
    FAILED: "Failed",
  }[status];

  const StatusIcon = {
    READY: CheckCircle2,
    PROCESSING: RefreshCw,
    PENDING: Clock3,
    FAILED: X,
  }[status];

  return (
    <Badge className={`${styles.status} ${statusClassName}`} variant="outline">
      <StatusIcon
        className={`${styles.statusIcon} ${status === "PROCESSING" ? "animate-spin" : ""}`}
        aria-hidden="true"
      />
      {statusLabel}
    </Badge>
  );
}

function DocumentRow({
  document,
  collectionName,
  onDelete,
  onView,
}: {
  document: DocumentSummaryResponse;
  collectionName?: string;
  onDelete: (document: DocumentSummaryResponse) => void;
  onView: (documentId: string) => void;
}) {
  return (
    <TableRow className={styles.documentRow}>
      <TableCell className={`${styles.documentCell} ${styles.documentNameCell}`}>
        <div className={styles.documentName}>
          <span
            className={`${styles.documentTypeBadge} ${getDocumentTypeClassName(document.original_extension)}`}
            aria-hidden="true"
          >
            {getFileTypeLabel(document.original_extension)}
          </span>
          <div className={styles.documentNameDetails}>
            <div className={styles.documentFileName}>{document.filename}</div>
            {collectionName ? <div className={styles.documentCollection}>{collectionName}</div> : null}
            {document.error_message ? (
              <div className={styles.documentError}>{document.error_message}</div>
            ) : null}
          </div>
        </div>
      </TableCell>
      <TableCell className={`${styles.documentCell} ${styles.documentSizeCell}`}>
        {formatBytes(document.size_bytes)}
      </TableCell>
      <TableCell className={`${styles.documentCell} ${styles.documentDateCell}`}>
        {formatRelativeDate(document.created_at)}
      </TableCell>
      <TableCell className={`${styles.documentCell} ${styles.documentStatusCell}`}>
        <DocumentStatusBadge status={document.status} />
      </TableCell>
      <TableCell className={`${styles.documentCell} ${styles.actionsCell}`}>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              aria-label={`Actions for ${document.filename}`}
              className={styles.actionsButton}
              size="icon"
              type="button"
              variant="ghost"
            >
              <MoreHorizontal aria-hidden="true" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={() => onView(document.id)}>
              <Eye aria-hidden="true" />
              View details
            </DropdownMenuItem>
            <DropdownMenuItem variant="destructive" onSelect={() => onDelete(document)}>
              <Trash2 aria-hidden="true" />
              Delete document
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </TableCell>
    </TableRow>
  );
}

function DocumentTableSkeleton() {
  return (
    <Card className={styles.tableCard} aria-label="Loading documents" role="status">
      <div className={styles.loadingRows}>
        {Array.from({ length: 4 }, (_, index) => (
          <div className={styles.loadingRow} key={index}>
            <Skeleton className={styles.loadingFile} />
            <Skeleton className={styles.loadingMeta} />
            <Skeleton className={styles.loadingMeta} />
            <Skeleton className={styles.loadingStatus} />
          </div>
        ))}
      </div>
    </Card>
  );
}

function DocumentsState({
  description,
  onAction,
  title,
  actionLabel,
  icon: Icon,
}: {
  description: string;
  onAction?: () => void;
  title: string;
  actionLabel?: string;
  icon: typeof AlertCircle;
}) {
  return (
    <div className={`${styles.stateCard} dashboard-surface`} role="status">
      <Icon className={styles.stateIcon} aria-hidden="true" />
      <h3 className={styles.stateTitle}>{title}</h3>
      <p className={styles.stateDescription}>{description}</p>
      {onAction && actionLabel ? (
        <Button onClick={onAction} size="sm" type="button">
          {actionLabel}
        </Button>
      ) : null}
    </div>
  );
}

export function DocumentsPage() {
  const { logout } = useAuth();
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [documents, setDocuments] = useState<PaginatedDocumentListResponse | null>(null);
  const [collections, setCollections] = useState<CollectionResponse[]>([]);
  const [selectedCollection, setSelectedCollection] = useState("all");
  const [uploadCollection, setUploadCollection] = useState("none");
  const [page, setPage] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadErrorStatus, setLoadErrorStatus] = useState<number | null>(null);
  const [pendingUploads, setPendingUploads] = useState<PendingUpload[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<DocumentSummaryResponse | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [detailsId, setDetailsId] = useState<string | null>(null);
  const [detailsDocument, setDetailsDocument] = useState<DocumentSummaryResponse | null>(null);
  const [detailsError, setDetailsError] = useState<string | null>(null);
  const [isDetailsLoading, setIsDetailsLoading] = useState(false);

  const collectionNames = useMemo(
    () => new Map(collections.map((collection) => [collection.id, collection.name])),
    [collections],
  );

  const loadDocuments = useCallback(
    async ({ silent = false }: { silent?: boolean } = {}) => {
      if (silent) {
        setIsRefreshing(true);
      } else {
        setIsLoading(true);
        setLoadError(null);
        setLoadErrorStatus(null);
      }

      try {
        const response = await api.listDocuments({
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
          collectionId: selectedCollection === "all" ? undefined : selectedCollection,
        });

        if (response.items.length === 0 && response.total > 0 && page > 0) {
          setPage((currentPage) => currentPage - 1);
          return;
        }

        setDocuments(response);
      } catch (error: unknown) {
        setLoadError(getBackendErrorMessage(error, "Unable to load your documents."));
        setLoadErrorStatus(error instanceof ApiError ? error.status : null);
      } finally {
        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [page, selectedCollection],
  );

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  useEffect(() => {
    let isMounted = true;

    async function loadCollections() {
      try {
        const response = await api.listCollections();
        if (isMounted) {
          setCollections(response.items);
        }
      } catch (error: unknown) {
        if (isMounted) {
          toast({
            title: "Collections unavailable",
            description: getBackendErrorMessage(
              error,
              "Documents can still be uploaded without a collection.",
            ),
            variant: "warning",
          });
        }
      }
    }

    void loadCollections();
    return () => {
      isMounted = false;
    };
  }, [toast]);

  const hasActiveProcessing = documents?.items.some(
    (document) => document.status === "PENDING" || document.status === "PROCESSING",
  );

  useEffect(() => {
    if (!hasActiveProcessing) return;

    const intervalId = window.setInterval(() => {
      void loadDocuments({ silent: true });
    }, 4000);

    return () => window.clearInterval(intervalId);
  }, [hasActiveProcessing, loadDocuments]);

  function handleCollectionFilterChange(value: string) {
    setSelectedCollection(value);
    setPage(0);
  }

  function handleFiles(files: FileList | File[]) {
    const selectedFiles = Array.from(files);
    if (!selectedFiles.length) return;

    if (selectedFiles.length + pendingUploads.length > MAX_FILES_PER_UPLOAD) {
      setUploadError(`You can upload up to ${MAX_FILES_PER_UPLOAD} files at a time.`);
      return;
    }

    setUploadError(null);
    setPendingUploads((current) => [
      ...current,
      ...selectedFiles.map((file) => ({
        id: `${file.name}-${file.lastModified}-${crypto.randomUUID()}`,
        file,
        status: "ready" as const,
      })),
    ]);
  }

  function handleFileInputChange(event: ChangeEvent<HTMLInputElement>) {
    if (event.target.files) {
      handleFiles(event.target.files);
    }
    event.target.value = "";
  }

  function handleDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setIsDragging(false);
    handleFiles(event.dataTransfer.files);
  }

  function handleRemoveUpload(id: string) {
    setPendingUploads((current) => current.filter((item) => item.id !== id));
  }

  async function handleUpload(items: PendingUpload[]) {
    const readyItems = items.filter((item) => item.status === "ready");
    if (!readyItems.length) return;

    const ids = new Set(readyItems.map((item) => item.id));
    setUploadError(null);
    setPendingUploads((current) =>
      current.map((item) => (ids.has(item.id) ? { ...item, status: "uploading", error: undefined } : item)),
    );

    try {
      const response = await api.uploadDocuments(
        readyItems.map((item) => item.file),
        uploadCollection === "none" ? undefined : uploadCollection,
      );
      setPendingUploads((current) => current.filter((item) => !ids.has(item.id)));
      toast({
        title: response.items.length === 1 ? "Document uploaded" : "Documents uploaded",
        description: "Processing has started. Status will update automatically.",
        variant: "success",
      });
      await loadDocuments({ silent: true });
    } catch (error: unknown) {
      const message = getBackendErrorMessage(error, "Document upload failed.");
      setPendingUploads((current) =>
        current.map((item) => (ids.has(item.id) ? { ...item, status: "ready", error: message } : item)),
      );
      setUploadError(message);
    }
  }

  async function handleDelete() {
    if (!deleteTarget || isDeleting) return;

    setIsDeleting(true);
    try {
      await api.deleteDocument(deleteTarget.id);
      setDeleteTarget(null);
      toast({
        title: "Document deleted",
        description: `${deleteTarget.filename} was removed from your documents.`,
        variant: "success",
      });
      await loadDocuments({ silent: true });
    } catch (error: unknown) {
      toast({
        title: "Unable to delete document",
        description: getBackendErrorMessage(error, "Document deletion failed."),
        variant: "error",
      });
    } finally {
      setIsDeleting(false);
    }
  }

  async function handleView(documentId: string) {
    setDetailsId(documentId);
    setDetailsDocument(null);
    setDetailsError(null);
    setIsDetailsLoading(true);

    try {
      setDetailsDocument(await api.getDocument(documentId));
    } catch (error: unknown) {
      setDetailsError(getBackendErrorMessage(error, "Unable to load document details."));
    } finally {
      setIsDetailsLoading(false);
    }
  }

  const readyUploads = pendingUploads.filter((item) => item.status === "ready");
  const totalPages = documents ? Math.max(1, Math.ceil(documents.total / PAGE_SIZE)) : 1;
  const canGoPrevious = page > 0;
  const canGoNext = documents ? (page + 1) * PAGE_SIZE < documents.total : false;

  return (
    <section className={styles.page} aria-labelledby="documents-heading">
      <div className={styles.content}>
        <DashboardPageHeader id="documents-heading" title="Documents" />

        <section className={styles.uploadSection} aria-labelledby="upload-heading">
          <div className={styles.uploadHeader}>
            <h2 className={styles.subheading} id="upload-heading">
              Add documents
            </h2>
            {collections.length > 0 ? (
              <div className={styles.controlGroup}>
                <span className={styles.fieldLabel}>Upload to collection</span>
                <Select value={uploadCollection} onValueChange={setUploadCollection}>
                  <SelectTrigger className={styles.collectionSelect} aria-label="Upload to collection">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent align="end">
                    <SelectItem value="none">No collection</SelectItem>
                    {collections.map((collection) => (
                      <SelectItem key={collection.id} value={collection.id}>
                        {collection.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ) : null}
          </div>

          <input
            ref={fileInputRef}
            accept=".txt,.md,.pdf,text/plain,text/markdown,application/pdf"
            className={styles.hiddenFileInput}
            multiple
            onChange={handleFileInputChange}
            type="file"
          />
          <button
            className={`${styles.dropzone} dashboard-surface ${isDragging ? styles.dropzoneActive : ""}`}
            onClick={() => fileInputRef.current?.click()}
            onDragEnter={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={(event) => {
              event.preventDefault();
              setIsDragging(false);
            }}
            onDragOver={(event) => event.preventDefault()}
            onDrop={handleDrop}
            type="button"
          >
            <span className={styles.dropzoneIcon} aria-hidden="true">
              <Upload />
            </span>
            <span className={styles.dropzoneTitle}>Drop your file here or click to browse</span>
            <span className={styles.dropzoneHint}>Supported: .txt, .md, .pdf</span>
          </button>

          {pendingUploads.length > 0 ? (
            <div className={styles.uploadQueue} aria-label="Selected files">
              <div className={styles.uploadQueueHeader}>
                <span className={styles.uploadQueueTitle}>{pendingUploads.length} selected</span>
                {readyUploads.length > 1 ? (
                  <Button
                    className={styles.uploadAllButton}
                    onClick={() => void handleUpload(readyUploads)}
                    size="sm"
                    type="button"
                  >
                    Upload all
                  </Button>
                ) : null}
              </div>
              {pendingUploads.map((item) => (
                <UploadRow
                  item={item}
                  key={item.id}
                  onRemove={handleRemoveUpload}
                  onUpload={(upload) => void handleUpload([upload])}
                />
              ))}
            </div>
          ) : null}

          {uploadError ? (
            <Alert className={styles.errorAlert} variant="destructive">
              <AlertCircle aria-hidden="true" />
              <AlertDescription className={styles.errorDescription}>{uploadError}</AlertDescription>
              <Button
                aria-label="Dismiss upload error"
                className={styles.alertClose}
                onClick={() => setUploadError(null)}
                size="icon"
                type="button"
                variant="ghost"
              >
                <X aria-hidden="true" />
              </Button>
            </Alert>
          ) : null}
        </section>

        <section className={styles.documentsSection} aria-labelledby="all-documents-heading">
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle} id="all-documents-heading">
              All documents
            </h2>
            <div className={styles.controlGroup}>
              <span className={styles.fieldLabel}>Filter by collection</span>
              <Select value={selectedCollection} onValueChange={handleCollectionFilterChange}>
                <SelectTrigger className={styles.collectionSelect} aria-label="Filter by collection">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent align="end">
                  <SelectItem value="all">All collections</SelectItem>
                  {collections.map((collection) => (
                    <SelectItem key={collection.id} value={collection.id}>
                      {collection.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {isLoading ? <DocumentTableSkeleton /> : null}

          {!isLoading && loadError ? (
            <DocumentsState
              actionLabel={loadErrorStatus === 401 ? "Sign in again" : "Try again"}
              description={loadError}
              icon={AlertCircle}
              onAction={loadErrorStatus === 401 ? logout : () => void loadDocuments()}
              title="Documents could not be loaded"
            />
          ) : null}

          {!isLoading && !loadError && documents?.total === 0 ? (
            <DocumentsState
              description="Upload a TXT, Markdown, or PDF file to start building your knowledge base."
              icon={FileText}
              title="No documents yet"
            />
          ) : null}

          {!isLoading && !loadError && documents && documents.items.length > 0 ? (
            <Card className={styles.tableCard}>
              <div className={styles.tableWrapper}>
                <Table className={styles.table}>
                  <TableHeader className={styles.tableHeader}>
                    <TableRow>
                      <TableHead className={`${styles.tableHeaderCell} ${styles.documentNameCell}`}>
                        Document
                      </TableHead>
                      <TableHead className={styles.tableHeaderCell}>Size</TableHead>
                      <TableHead className={styles.tableHeaderCell}>Uploaded</TableHead>
                      <TableHead className={styles.tableHeaderCell}>Status</TableHead>
                      <TableHead className={styles.tableHeaderCell}>
                        <span className={styles.visuallyHidden}>Actions</span>
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {documents.items.map((document) => (
                      <DocumentRow
                        collectionName={document.collection_id ? collectionNames.get(document.collection_id) : undefined}
                        document={document}
                        key={document.id}
                        onDelete={setDeleteTarget}
                        onView={(id) => void handleView(id)}
                      />
                    ))}
                  </TableBody>
                </Table>
              </div>

              <div className={styles.tableFooter}>
                <p className={styles.resultCount}>
                  Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, documents.total)} of {documents.total}
                </p>
                <Pagination className={styles.pagination}>
                  <PaginationContent className={styles.paginationContent}>
                    <PaginationItem>
                      <Button
                        className={styles.paginationButton}
                        disabled={!canGoPrevious || isRefreshing}
                        onClick={() => setPage((currentPage) => Math.max(0, currentPage - 1))}
                        size="default"
                        type="button"
                        variant="outline"
                      >
                        Previous
                      </Button>
                    </PaginationItem>
                    <PaginationItem>
                      <Button
                        className={styles.paginationButton}
                        disabled={!canGoNext || isRefreshing}
                        onClick={() => setPage((currentPage) => currentPage + 1)}
                        size="default"
                        type="button"
                      >
                        Next
                      </Button>
                    </PaginationItem>
                  </PaginationContent>
                </Pagination>
              </div>
            </Card>
          ) : null}
        </section>
      </div>

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open && !isDeleting) setDeleteTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete document?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently deletes {deleteTarget?.filename ?? "this document"} and its processed content.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction disabled={isDeleting} onClick={(event) => {
              event.preventDefault();
              void handleDelete();
            }}>
              {isDeleting ? "Deleting..." : "Delete document"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog
        open={detailsId !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDetailsId(null);
            setDetailsDocument(null);
            setDetailsError(null);
          }
        }}
      >
        <DialogContent className={styles.detailsDialog}>
          <DialogHeader>
            <DialogTitle>{detailsDocument?.filename ?? "Document details"}</DialogTitle>
            <DialogDescription>Metadata returned by the document service.</DialogDescription>
          </DialogHeader>
          {isDetailsLoading ? (
            <div className={styles.detailsLoading} role="status">
              <LoaderCircle className="animate-spin" aria-hidden="true" />
              Loading details...
            </div>
          ) : detailsError ? (
            <DocumentsState description={detailsError} icon={AlertCircle} title="Details unavailable" />
          ) : detailsDocument ? (
            <dl className={styles.detailsGrid}>
              <dt>File type</dt>
              <dd>{detailsDocument.content_type}</dd>
              <dt>Size</dt>
              <dd>{formatBytes(detailsDocument.size_bytes)}</dd>
              <dt>Status</dt>
              <dd><DocumentStatusBadge status={detailsDocument.status} /></dd>
              <dt>Created</dt>
              <dd>{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(detailsDocument.created_at))}</dd>
              <dt>Updated</dt>
              <dd>{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(detailsDocument.updated_at))}</dd>
              {detailsDocument.error_message ? <><dt>Error</dt><dd className={styles.detailError}>{detailsDocument.error_message}</dd></> : null}
            </dl>
          ) : null}
        </DialogContent>
      </Dialog>
    </section>
  );
}
