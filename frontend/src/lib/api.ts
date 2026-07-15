export interface User {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  is_email_verified: boolean;
  is_active: boolean;
  created_at: string;
}

export interface RegisterRequest {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterResponse {
  user: User;
  message: string;
  verification_token?: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  user: User;
}

export interface MessageResponse {
  message: string;
}

export interface ResendVerificationResponse extends MessageResponse {
  verification_token?: string;
}

export type DocumentStatus = "PENDING" | "PROCESSING" | "READY" | "FAILED";

export interface DocumentSummaryResponse {
  id: string;
  collection_id: string | null;
  filename: string;
  original_extension: string;
  content_type: string;
  size_bytes: number;
  status: DocumentStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedDocumentListResponse {
  items: DocumentSummaryResponse[];
  limit: number;
  offset: number;
  total: number;
}

export interface DocumentUploadItemResponse {
  document_id: string;
  filename: string;
  collection_id: string | null;
  status: DocumentStatus;
}

export interface DocumentUploadResponse {
  items: DocumentUploadItemResponse[];
}

export interface CollectionResponse {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedCollectionListResponse {
  items: CollectionResponse[];
  limit: number;
  offset: number;
  total: number;
}

export interface CitationResponse {
  rank: number;
  document_id: string;
  document_filename: string;
  chunk_id: string;
  chunk_index: number;
  excerpt: string;
  distance: number;
}

export interface QuestionHistoryItemResponse {
  question_id: string;
  collection_id: string | null;
  question: string;
  answer: string;
  citations: CitationResponse[];
  created_at: string;
  provider: "openai" | "ollama" | null;
  model: string | null;
}

export interface PaginatedQuestionHistoryResponse {
  items: QuestionHistoryItemResponse[];
  limit: number;
  offset: number;
  total: number;
}

export interface ApiErrorDetail {
  type: string;
  loc: (string | number)[];
  msg: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}

export interface ApiErrorDetails {
  errors?: ApiErrorDetail[];
  [key: string]: unknown;
}

export class ApiError extends Error {
  code: string;
  details?: ApiErrorDetails;
  status: number;

  constructor(message: string, code: string, status: number, details?: ApiErrorDetails) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof ApiError)) {
    return fallback;
  }

  const validationMessages = error.details?.errors
    ?.map((detail) => {
      const field = detail.loc.at(-1);
      return field ? `${String(field)}: ${detail.msg}` : detail.msg;
    })
    .filter(Boolean);

  if (validationMessages?.length) {
    return validationMessages.join(" ");
  }

  return error.message || fallback;
}

export const AUTH_TOKEN_STORAGE_KEY = "sourcewise_token";

const BASE_URL = "/api/v1";

export function getStoredAuthToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    return localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function storeAuthToken(token: string): void {
  try {
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
  } catch {
    throw new Error("Authentication storage is unavailable.");
  }
}

export function clearStoredAuthToken(): void {
  try {
    localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
  } catch {
    // Clearing an unavailable storage area should not prevent logout or recovery.
  }
}

type ErrorResponse = {
  error?: {
    code?: unknown;
    message?: unknown;
    details?: unknown;
  };
  detail?: unknown;
};

function isApiErrorDetails(value: unknown): value is ApiErrorDetails {
  return typeof value === "object" && value !== null;
}

function asMessage(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const token = getStoredAuthToken();

  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorData: ErrorResponse | undefined;
    try {
      errorData = (await response.json()) as ErrorResponse;
    } catch {
      throw new ApiError(
        response.statusText || "Request failed",
        "request_error",
        response.status
      );
    }

    const errorPayload = errorData?.error || {};
    const message =
      asMessage(errorPayload.message) ??
      asMessage(errorData?.detail) ??
      "An unexpected error occurred";
    const code = asMessage(errorPayload.code) ?? "unknown_error";
    const details = isApiErrorDetails(errorPayload.details)
      ? errorPayload.details
      : undefined;

    throw new ApiError(
      message,
      code,
      response.status,
      details,
    );
  }

  // Handle empty content / 204 responses
  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  async register(payload: RegisterRequest): Promise<RegisterResponse> {
    return request<RegisterResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async login(payload: LoginRequest): Promise<LoginResponse> {
    return request<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async verifyEmail(token: string): Promise<MessageResponse> {
    return request<MessageResponse>("/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    });
  },

  async resendVerification(email: string): Promise<ResendVerificationResponse> {
    return request<ResendVerificationResponse>("/auth/resend-verification", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
  },

  async getMe(): Promise<User> {
    return request<User>("/auth/me", {
      method: "GET",
    });
  },

  async listDocuments({
    limit = 20,
    offset = 0,
    collectionId,
  }: {
    limit?: number;
    offset?: number;
    collectionId?: string;
  } = {}): Promise<PaginatedDocumentListResponse> {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    });
    if (collectionId) {
      params.set("collection_id", collectionId);
    }

    return request<PaginatedDocumentListResponse>(`/documents?${params.toString()}`, {
      method: "GET",
    });
  },

  async uploadDocuments(
    files: readonly File[],
    collectionId?: string,
  ): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    if (collectionId) {
      formData.append("collection_id", collectionId);
    }

    return request<DocumentUploadResponse>("/documents/upload", {
      method: "POST",
      body: formData,
    });
  },

  async getDocument(documentId: string): Promise<DocumentSummaryResponse> {
    return request<DocumentSummaryResponse>(`/documents/${encodeURIComponent(documentId)}`, {
      method: "GET",
    });
  },

  async deleteDocument(documentId: string): Promise<void> {
    await request<void>(`/documents/${encodeURIComponent(documentId)}`, {
      method: "DELETE",
    });
  },

  async listCollections({
    limit = 100,
    offset = 0,
  }: {
    limit?: number;
    offset?: number;
  } = {}): Promise<PaginatedCollectionListResponse> {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    });

    return request<PaginatedCollectionListResponse>(`/collections?${params.toString()}`, {
      method: "GET",
    });
  },

  async listQuestionHistory({
    limit = 20,
    offset = 0,
    documentId,
  }: {
    limit?: number;
    offset?: number;
    documentId?: string;
  } = {}): Promise<PaginatedQuestionHistoryResponse> {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    });
    if (documentId) {
      params.set("document_id", documentId);
    }

    return request<PaginatedQuestionHistoryResponse>(`/questions/history?${params.toString()}`, {
      method: "GET",
    });
  },
};
