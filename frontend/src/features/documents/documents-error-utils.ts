import { ApiError } from "@/lib/api";

export type DocumentsErrorContent = {
  description: string;
  title: string;
};

export function getDocumentsListError(error: unknown): DocumentsErrorContent {
  if (error instanceof ApiError) {
    if (error.code === "invalid_response") {
      return {
        title: "Documents couldn’t load",
        description:
          "The server returned document data in an unexpected format. Try again in a moment.",
      };
    }
    if (error.status === 401) {
      return {
        title: "Your session has ended",
        description: "Sign in again to access your documents.",
      };
    }
    if (error.status === 403) {
      return {
        title: "Documents aren’t available",
        description:
          "Your account does not currently have permission to access documents.",
      };
    }
    if (error.status >= 500) {
      return {
        title: "Documents couldn’t load",
        description:
          "The document service is temporarily unavailable. Your saved documents were not changed.",
      };
    }
  }

  if (error instanceof TypeError) {
    return {
      title: "Can’t reach the document service",
      description: "Check your connection, then try loading the documents again.",
    };
  }

  return {
    title: "Documents couldn’t load",
    description:
      "The request could not be completed. Your saved documents were not changed.",
  };
}

export function getDocumentsRefreshError(error: unknown): string {
  if (error instanceof ApiError && error.code === "invalid_response") {
    return "The latest document update could not be read. Existing results are still shown.";
  }
  if (error instanceof TypeError) {
    return "Documents could not be refreshed because the network is unavailable.";
  }
  return "Documents could not be refreshed. Existing results are still shown.";
}

export function getUploadErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "invalid_response") {
      return "The upload confirmation could not be verified. Refresh and review the document list before changing the selection to try again.";
    }
    if (error.status === 413 || error.code === "payload_too_large") {
      return "One or more files is larger than the 10 MB upload limit.";
    }
    if (error.status === 404) {
      return "The selected collection is no longer available. Choose another collection or upload without one.";
    }
    if (error.status === 401) return "Your session has ended. Sign in and try again.";
    if (error.status === 403) {
      return "Your account does not currently have permission to upload documents.";
    }
    if (error.status === 400 || error.status === 422) {
      const message = error.message.toLowerCase();
      if (message.includes("unsupported file extension")) {
        return "One or more files has an unsupported type. Choose PDF, TXT, or MD files.";
      }
      if (message.includes("must not be empty")) {
        return "Empty files cannot be uploaded.";
      }
      if (message.includes("utf-8") || message.includes("nul")) {
        return "TXT and MD files must contain valid UTF-8 text.";
      }
      if (message.includes("pdf content")) {
        return "One of the selected PDF files is not a valid PDF document.";
      }
      return "The server rejected this upload. Review the selected files and try again.";
    }
    if (error.status >= 500) {
      return "The document service could not complete the upload. Try again later.";
    }
  }
  if (error instanceof TypeError) {
    return "The upload could not reach the server. Check your connection and try again.";
  }
  return "The documents could not be uploaded.";
}

export function getDeleteErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) {
      return "This document is no longer available. Refresh the document list.";
    }
    if (error.status === 401) return "Your session has ended. Sign in and try again.";
    if (error.status === 403) {
      return "Your account does not currently have permission to delete documents.";
    }
    if (error.status >= 500) {
      return "The document service could not delete this document. Try again later.";
    }
  }
  if (error instanceof TypeError) {
    return "The delete request could not reach the server. Check your connection and try again.";
  }
  return "The document could not be deleted.";
}
