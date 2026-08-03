import { ApiError } from "@/lib/api";

export type QuestionErrorContent = {
  description: string;
  title: string;
};

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
          "Choose another collection or search all documents, then try again.",
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
        title: "Too many questions at once",
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
          "The request timed out. Your question is still here so you can try again.",
      };
    }
    if (error.status >= 500) {
      return {
        title: "The question couldn’t be answered",
        description:
          "The service encountered a problem. Your question was not cleared.",
      };
    }
  }

  if (error instanceof TypeError) {
    return {
      title: "Can’t reach the answer service",
      description:
        "Check your connection. Your question is still here so you can try again.",
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
          "The collection service is temporarily unavailable. You can still search all documents.",
      };
    }
  }

  if (error instanceof TypeError) {
    return {
      title: "Can’t load collections",
      description:
        "Check your connection. You can still search all documents.",
    };
  }

  return {
    title: "Collections couldn’t load",
    description:
      "The request could not be completed. You can still search all documents.",
  };
}
