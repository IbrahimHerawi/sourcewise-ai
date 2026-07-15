import type {
  CollectionResponse,
  DocumentStatus,
  DocumentSummaryResponse,
} from "@/lib/api";

export type { CollectionResponse, DocumentStatus, DocumentSummaryResponse } from "@/lib/api";

export type PendingUpload = {
  id: string;
  file: File;
  status: "ready" | "uploading";
  error?: string;
};

export type DocumentCollection = CollectionResponse;

export type DocumentRecord = DocumentSummaryResponse;
