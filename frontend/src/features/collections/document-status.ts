import type { DocumentStatus } from "@/features/collections/collections-api-types";

export const DOCUMENT_STATUS_PRESENTATION = {
  PENDING: { label: "Pending", tone: "pending" },
  PROCESSING: { label: "Processing", tone: "processing" },
  READY: { label: "Ready", tone: "ready" },
  FAILED: { label: "Failed", tone: "failed" },
} as const satisfies Record<
  DocumentStatus,
  { label: string; tone: "pending" | "processing" | "ready" | "failed" }
>;

export function safeDocumentFailureMessage(message: string | null): string {
  return message?.trim() || "This document could not be processed.";
}
