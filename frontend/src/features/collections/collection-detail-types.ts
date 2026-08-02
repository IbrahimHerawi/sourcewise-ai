import type { Collection } from "@/features/collections/collection-types";

export type CollectionDetailTab = "documents" | "history";

export type DocumentStatus = "ready" | "processing" | "pending";

export type CollectionDocument = {
  id: string;
  name: string;
  metadata: string;
  progress?: number;
  status: DocumentStatus;
};

export type CollectionHistoryItem = {
  answer: string;
  askedAt: string;
  citationCount: number;
  id: string;
  question: string;
};

export type CollectionDetail = Collection & {
  documentTotal: number;
  documents: readonly CollectionDocument[];
  history: readonly CollectionHistoryItem[];
  questionTotal: number;
  readyDocumentCount: number;
};

export type CollectionDetailViewState =
  | { status: "loading" }
  | { status: "documents"; collection: CollectionDetail }
  | { status: "history"; collection: CollectionDetail }
  | { status: "empty"; collection: CollectionDetail }
  | { status: "no-ready-documents"; collection: CollectionDetail }
  | { status: "no-question-history"; collection: CollectionDetail }
  | { status: "not-found" }
  | { status: "server-error" };

export type ResolvedCollectionDetailState = Exclude<
  CollectionDetailViewState,
  { status: "loading" | "not-found" | "server-error" }
>;
