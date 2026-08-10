import { ApiError } from "@/lib/api";

export type QuestionErrorContent = {
  description: string;
  title: string;
};

export type QuestionFailureAction = "retry" | "select-collection" | undefined;

export function getQuestionFailureAction(
  error: unknown,
  collectionId: string | null,
): QuestionFailureAction {
  if (!(error instanceof ApiError)) return undefined;
  if (error.status === 404 && collectionId) return "select-collection";
  if (
    error.status === 429 ||
    error.status === 502 ||
    error.status === 503 ||
    error.code === "question_answering_unavailable"
  ) {
    return "retry";
  }
  return undefined;
}

export function getQuestionErrorContent(error: unknown): QuestionErrorContent {
  if (error instanceof ApiError) {
    if (error.code === "invalid_response") {
      return {
        title: "The answer couldn’t be verified",
        description:
          "The server response was incomplete. Your question is still here; wait before submitting it again to avoid creating a duplicate.",
      };
    }
    if (error.status === 401) {
      return {
        title: "Your session has ended",
        description: "Sign in again to ask questions.",
      };
    }
    if (error.status === 403) {
      return {
        title: "Question answering isn’t available",
        description:
          "Your account does not currently have permission to ask questions.",
      };
    }
    if (error.status === 404) {
      return {
        title: "That collection is no longer available",
        description:
          "Select another collection, then try again.",
      };
    }
    if (error.status === 400 || error.status === 422) {
      return {
        title: "The question couldn’t be submitted",
        description:
          "Review the question and selected search scope, then try again.",
      };
    }
    if (error.status === 429 || error.code === "rate_limited") {
      return {
        title: "Question limit reached",
        description: "Wait a moment before trying again.",
      };
    }
    if (error.status === 502) {
      return {
        title: "The answer couldn’t be generated",
        description:
          "The answer service could not complete this request. Your question is still here so you can try again.",
      };
    }
    if (
      error.status === 503 ||
      error.code === "question_answering_unavailable"
    ) {
      return {
        title: "Question answering is temporarily unavailable",
        description:
          "The answer service is not responding right now. Your question is still here so you can try again.",
      };
    }
    if (error.status === 504 || error.code === "gateway_timeout") {
      return {
        title: "The answer took too long",
        description:
          "The request timed out. Your question is still here; wait before submitting it again because the result may have been saved.",
      };
    }
    if (error.status >= 500) {
      return {
        title: "The question couldn’t be answered",
        description:
          "The service encountered a problem. Your question is still here; wait before submitting it again because the result may have been saved.",
      };
    }
  }

  if (error instanceof TypeError) {
    return {
      title: "Can’t reach the answer service",
      description:
        "Check your connection. Your question is still here; wait before submitting it again because the result may have been saved.",
    };
  }

  return {
    title: "The question couldn’t be answered",
    description:
      "The request could not be completed. Your question was not cleared.",
  };
}

export function getQuestionCollectionsError(
  error: unknown,
): QuestionErrorContent {
  if (error instanceof ApiError) {
    if (error.code === "invalid_response") {
      return {
        title: "Collections couldn’t be verified",
        description:
          "The server returned collection information in an unexpected format. Try loading it again.",
      };
    }
    if (error.status === 401) {
      return {
        title: "Your session has ended",
        description: "Sign in again to access your collections.",
      };
    }
    if (error.status === 403) {
      return {
        title: "Collections aren’t available",
        description:
          "Your account does not currently have permission to access collections.",
      };
    }
    if (error.status >= 500) {
      return {
        title: "Collections couldn’t load",
        description:
          "Collection choices are temporarily unavailable. The selected scope has been preserved and will be validated when you submit.",
      };
    }
  }

  if (error instanceof TypeError) {
    return {
      title: "Can’t load collections",
      description:
        "Check your connection. The selected scope has been preserved and will be validated when you submit.",
    };
  }

  return {
    title: "Collections couldn’t load",
    description:
      "The selected scope has been preserved and will be validated when you submit.",
  };
}

export function getQuestionSourcesError(error: unknown): QuestionErrorContent {
  if (error instanceof ApiError) {
    if (error.code === "invalid_response") {
      return {
        title: "Document status couldn’t be verified",
        description:
          "The server returned document information in an unexpected format. You can still submit a question; the backend remains authoritative.",
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
        title: "Document status couldn’t load",
        description:
          "Ready-source information is temporarily unavailable. You can still submit a question.",
      };
    }
  }

  if (error instanceof TypeError) {
    return {
      title: "Can’t load document status",
      description:
        "Check your connection. You can still submit a question, but ready-source information is unavailable.",
    };
  }

  return {
    title: "Document status couldn’t load",
    description:
      "Ready-source information is unavailable. You can still submit a question.",
  };
}

export function getQuestionHistoryErrorContent(
  error: unknown,
): QuestionErrorContent {
  if (error instanceof ApiError) {
    if (error.code === "invalid_response") {
      return {
        title: "Question history couldn’t be verified",
        description:
          "The server returned question history in an unexpected format. Try loading it again.",
      };
    }
    if (error.status === 401) {
      return {
        title: "Your session has ended",
        description: "Sign in again to access question history.",
      };
    }
    if (error.status === 403) {
      return {
        title: "Question history isn’t available",
        description:
          "Your account does not currently have permission to access question history.",
      };
    }
    if (error.status === 404) {
      return {
        title: "Question not found",
        description:
          "This saved question may have been deleted or the link may be outdated.",
      };
    }
    if (error.status === 429) {
      return {
        title: "History requests are temporarily limited",
        description: "Wait a moment before trying again.",
      };
    }
    if (error.status >= 500) {
      return {
        title: "Question history couldn’t load",
        description:
          "The history service is temporarily unavailable. Try again later.",
      };
    }
  }

  if (error instanceof TypeError) {
    return {
      title: "Can’t reach question history",
      description: "Check your connection, then try again.",
    };
  }

  return {
    title: "Question history couldn’t load",
    description: "The request could not be completed. Try again later.",
  };
}
