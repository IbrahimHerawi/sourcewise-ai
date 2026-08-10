import type { DocumentStatus } from "./types";

type DocumentStatusPresentation = {
  actions: readonly ("details" | "delete")[];
  label: string;
  pollingRequired: boolean;
  processingMessage: string | null;
  tone: "pending" | "processing" | "ready" | "failed" | "unknown";
};

export const DOCUMENT_STATUS_PRESENTATION = {
  PENDING: {
    actions: ["details", "delete"],
    label: "Pending",
    pollingRequired: true,
    processingMessage: "Waiting to be processed.",
    tone: "pending",
  },
  PROCESSING: {
    actions: ["details", "delete"],
    label: "Processing",
    pollingRequired: true,
    processingMessage: "Preparing this document for answers.",
    tone: "processing",
  },
  READY: {
    actions: ["details", "delete"],
    label: "Ready",
    pollingRequired: false,
    processingMessage: null,
    tone: "ready",
  },
  FAILED: {
    actions: ["details", "delete"],
    label: "Failed",
    pollingRequired: false,
    processingMessage: null,
    tone: "failed",
  },
  UNKNOWN: {
    actions: ["details", "delete"],
    label: "Unknown",
    pollingRequired: false,
    processingMessage: "The current processing status is unavailable.",
    tone: "unknown",
  },
} as const satisfies Record<DocumentStatus, DocumentStatusPresentation>;

export function safeDocumentFailureMessage(message: string | null): string {
  return message?.trim() || "This document could not be processed.";
}
