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
  refresh_token: string;
  token_type: "bearer";
  access_token_expires_in: number;
  refresh_token_expires_in: number;
  user: User;
}

export interface RefreshTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  access_token_expires_in: number;
  refresh_token_expires_in: number;
}

export interface MessageResponse {
  message: string;
}

export interface ResendVerificationResponse extends MessageResponse {
  verification_token?: string;
}

export interface ForgotPasswordResponse extends MessageResponse {
  reset_token?: string;
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

const BASE_URL = "/api/v1";
const ACCESS_TOKEN_REFRESH_WINDOW_MS = 5_000;
const LEGACY_AUTH_TOKEN_STORAGE_KEY = "sourcewise_token";
const REFRESH_SESSION_STORAGE_KEY = "sourcewise_refresh_session";

type TokenPair = Pick<
  RefreshTokenResponse,
  | "access_token"
  | "refresh_token"
  | "access_token_expires_in"
  | "refresh_token_expires_in"
>;

type AuthSession = {
  accessToken: string;
  accessTokenExpiresAt: number;
  id: number;
  refreshToken: string;
  refreshTokenExpiresAt: number;
};

type StoredRefreshSession = Pick<
  AuthSession,
  "refreshToken" | "refreshTokenExpiresAt"
>;

type AuthFailureHandler = () => void;

let authSession: AuthSession | null = null;
let nextAuthSessionId = 1;
let authStateVersion = 0;
let refreshRequest: Promise<string> | null = null;
let restoreRequest: Promise<boolean> | null = null;
let authFailureHandler: AuthFailureHandler | null = null;

class StaleAuthSessionError extends Error {
  constructor() {
    super("The authentication session changed while the request was in progress.");
    this.name = "StaleAuthSessionError";
  }
}

function invalidRefreshTokenError(): ApiError {
  return new ApiError(
    "Refresh token is invalid or expired.",
    "invalid_refresh_token",
    401,
  );
}

function isPositiveFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}

function validateTokenPair(value: TokenPair): void {
  if (
    typeof value.access_token !== "string" ||
    !value.access_token ||
    typeof value.refresh_token !== "string" ||
    !value.refresh_token ||
    !isPositiveFiniteNumber(value.access_token_expires_in) ||
    !isPositiveFiniteNumber(value.refresh_token_expires_in)
  ) {
    throw new ApiError(
      "The server returned an invalid authentication response.",
      "invalid_response",
      200,
    );
  }
}

function clearStoredRefreshSession(): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.removeItem(REFRESH_SESSION_STORAGE_KEY);
  } catch {
    // Storage cleanup must not prevent the in-memory session from being cleared.
  }
}

function storeRefreshSession(session: StoredRefreshSession): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(
      REFRESH_SESSION_STORAGE_KEY,
      JSON.stringify({
        refreshToken: session.refreshToken,
        refreshTokenExpiresAt: session.refreshTokenExpiresAt,
      } satisfies StoredRefreshSession),
    );
  } catch {
    // Authentication still works in memory when browser storage is unavailable.
  }
}

function readStoredRefreshSession(): StoredRefreshSession | null {
  if (typeof window === "undefined") return null;

  try {
    const rawValue = sessionStorage.getItem(REFRESH_SESSION_STORAGE_KEY);
    if (!rawValue) return null;

    const value = JSON.parse(rawValue) as Partial<StoredRefreshSession>;
    if (
      typeof value.refreshToken !== "string" ||
      value.refreshToken.length < 32 ||
      value.refreshToken.length > 512 ||
      !isPositiveFiniteNumber(value.refreshTokenExpiresAt)
    ) {
      clearStoredRefreshSession();
      return null;
    }

    return {
      refreshToken: value.refreshToken,
      refreshTokenExpiresAt: value.refreshTokenExpiresAt,
    };
  } catch {
    clearStoredRefreshSession();
    return null;
  }
}

function beginAuthSession(tokenPair: TokenPair): void {
  validateTokenPair(tokenPair);
  const now = Date.now();
  authStateVersion += 1;
  refreshRequest = null;
  authSession = {
    accessToken: tokenPair.access_token,
    accessTokenExpiresAt: now + tokenPair.access_token_expires_in * 1_000,
    id: nextAuthSessionId++,
    refreshToken: tokenPair.refresh_token,
    refreshTokenExpiresAt: now + tokenPair.refresh_token_expires_in * 1_000,
  };
  storeRefreshSession(authSession);
}

function rotateAuthSession(tokenPair: TokenPair, sessionId: number): string {
  validateTokenPair(tokenPair);
  if (authSession?.id !== sessionId) {
    throw new StaleAuthSessionError();
  }

  const now = Date.now();
  authStateVersion += 1;
  authSession = {
    accessToken: tokenPair.access_token,
    accessTokenExpiresAt: now + tokenPair.access_token_expires_in * 1_000,
    id: sessionId,
    refreshToken: tokenPair.refresh_token,
    refreshTokenExpiresAt: now + tokenPair.refresh_token_expires_in * 1_000,
  };
  storeRefreshSession(authSession);
  return tokenPair.access_token;
}

export function clearAuthSession(): void {
  authStateVersion += 1;
  authSession = null;
  refreshRequest = null;
  restoreRequest = null;
  clearStoredRefreshSession();
}

export function hasAuthSession(): boolean {
  return authSession !== null;
}

export function setAuthFailureHandler(
  handler: AuthFailureHandler | null,
): () => void {
  authFailureHandler = handler;
  return () => {
    if (authFailureHandler === handler) {
      authFailureHandler = null;
    }
  };
}

export function clearLegacyAuthStorage(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(LEGACY_AUTH_TOKEN_STORAGE_KEY);
  } catch {
    // Legacy storage cleanup must not block authentication.
  }
}

function invalidateAuthSession(sessionId?: number): void {
  if (sessionId !== undefined && authSession?.id !== sessionId) {
    return;
  }
  clearAuthSession();
  authFailureHandler?.();
}

/**
 * Installs a complete in-memory token pair.
 *
 * Authentication entry points use this internally. It is exported so API
 * contract tests and non-React consumers can initialize the same client
 * without creating a second request path.
 */
export function setAuthSession(tokenPair: TokenPair): void {
  beginAuthSession(tokenPair);
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

async function parseApiResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorData: ErrorResponse | undefined;
    try {
      errorData = (await response.json()) as ErrorResponse;
    } catch {
      throw new ApiError(
        response.statusText || "Request failed",
        "request_error",
        response.status,
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

    throw new ApiError(message, code, response.status, details);
  }

  if (response.status === 204) {
    return {} as T;
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError(
      "The server returned an invalid response.",
      "invalid_response",
      response.status,
    );
  }
}

function fetchApiResponse(
  path: string,
  options: RequestInit,
  accessToken?: string,
): Promise<Response> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  } else {
    headers.delete("Authorization");
  }

  return fetch(`${BASE_URL}${path}`, {
    cache: "no-store",
    credentials: "same-origin",
    ...options,
    headers,
  });
}

async function isAccessTokenUnauthorized(response: Response): Promise<boolean> {
  if (response.status !== 401) return false;

  try {
    const payload = (await response.clone().json()) as ErrorResponse;
    return payload.error?.code === "unauthorized";
  } catch {
    return false;
  }
}

async function refreshAccessToken(sessionId: number): Promise<string> {
  if (refreshRequest) {
    return refreshRequest;
  }

  const session = authSession;
  if (!session || session.id !== sessionId) {
    throw new StaleAuthSessionError();
  }
  if (session.refreshTokenExpiresAt <= Date.now()) {
    invalidateAuthSession(sessionId);
    throw invalidRefreshTokenError();
  }

  const refreshToken = session.refreshToken;
  const currentRefreshRequest = (async () => {
    try {
      const response = await fetchApiResponse(
        "/auth/refresh",
        {
          method: "POST",
          body: JSON.stringify({ refresh_token: refreshToken }),
        },
      );
      const tokenPair = await parseApiResponse<RefreshTokenResponse>(response);

      if (
        authSession?.id !== sessionId ||
        authSession.refreshToken !== refreshToken
      ) {
        throw new StaleAuthSessionError();
      }

      return rotateAuthSession(tokenPair, sessionId);
    } catch (error) {
      if (
        authSession?.id === sessionId &&
        authSession.refreshToken === refreshToken
      ) {
        // A failed rotating-token exchange is not safe to retry: the server
        // may have consumed the token even if the response was lost.
        invalidateAuthSession(sessionId);
      }
      throw error;
    }
  })();
  refreshRequest = currentRefreshRequest;
  try {
    return await currentRefreshRequest;
  } finally {
    if (refreshRequest === currentRefreshRequest) {
      refreshRequest = null;
    }
  }
}

async function restoreAuthSession(): Promise<boolean> {
  if (authSession) {
    return true;
  }
  if (restoreRequest) {
    return restoreRequest;
  }

  const storedSession = readStoredRefreshSession();
  if (!storedSession) {
    return false;
  }
  if (storedSession.refreshTokenExpiresAt <= Date.now()) {
    clearStoredRefreshSession();
    return false;
  }

  const restoreAuthStateVersion = authStateVersion;
  const refreshToken = storedSession.refreshToken;
  const currentRestoreRequest = (async () => {
    try {
      const response = await fetchApiResponse(
        "/auth/refresh",
        {
          method: "POST",
          body: JSON.stringify({ refresh_token: refreshToken }),
        },
      );
      const tokenPair = await parseApiResponse<RefreshTokenResponse>(response);

      if (
        authStateVersion !== restoreAuthStateVersion ||
        readStoredRefreshSession()?.refreshToken !== refreshToken
      ) {
        throw new StaleAuthSessionError();
      }

      beginAuthSession(tokenPair);
      return true;
    } catch (error) {
      if (authStateVersion !== restoreAuthStateVersion) {
        throw new StaleAuthSessionError();
      }

      // As with an in-memory rotation, an ambiguous failure is unsafe to
      // retry because the server may already have consumed this token.
      clearStoredRefreshSession();
      if (
        error instanceof ApiError &&
        error.status === 401 &&
        error.code === "invalid_refresh_token"
      ) {
        return false;
      }
      throw error;
    }
  })();

  restoreRequest = currentRestoreRequest;
  try {
    return await currentRestoreRequest;
  } finally {
    if (restoreRequest === currentRestoreRequest) {
      restoreRequest = null;
    }
  }
}

type ApiRequestConfig = {
  auth?: "none" | "required";
};

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  config: ApiRequestConfig = {},
): Promise<T> {
  if (config.auth === "none") {
    return parseApiResponse<T>(await fetchApiResponse(path, options));
  }

  const initialSession = authSession;
  if (!initialSession) {
    return parseApiResponse<T>(await fetchApiResponse(path, options));
  }

  const sessionId = initialSession.id;
  let accessToken = initialSession.accessToken;
  let refreshedBeforeRequest = false;

  if (
    initialSession.accessTokenExpiresAt <=
    Date.now() + ACCESS_TOKEN_REFRESH_WINDOW_MS
  ) {
    accessToken = await refreshAccessToken(sessionId);
    refreshedBeforeRequest = true;
  }

  if (authSession?.id !== sessionId) {
    throw new StaleAuthSessionError();
  }

  const response = await fetchApiResponse(path, options, accessToken);
  if (authSession?.id !== sessionId) {
    throw new StaleAuthSessionError();
  }
  if (!(await isAccessTokenUnauthorized(response))) {
    return parseApiResponse<T>(response);
  }

  if (refreshedBeforeRequest) {
    invalidateAuthSession(sessionId);
    return parseApiResponse<T>(response);
  }

  const currentSession = authSession;
  if (!currentSession || currentSession.id !== sessionId) {
    return parseApiResponse<T>(response);
  }

  if (currentSession.accessToken !== accessToken) {
    accessToken = currentSession.accessToken;
  } else {
    accessToken = await refreshAccessToken(sessionId);
  }

  if (authSession?.id !== sessionId) {
    throw new StaleAuthSessionError();
  }

  const retryResponse = await fetchApiResponse(path, options, accessToken);
  if (authSession?.id !== sessionId) {
    throw new StaleAuthSessionError();
  }
  if (await isAccessTokenUnauthorized(retryResponse)) {
    invalidateAuthSession(sessionId);
  }
  return parseApiResponse<T>(retryResponse);
}

export const api = {
  async register(payload: RegisterRequest): Promise<RegisterResponse> {
    return apiRequest<RegisterResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }, { auth: "none" });
  },

  async login(payload: LoginRequest): Promise<LoginResponse> {
    const loginAuthStateVersion = authStateVersion;
    const response = await apiRequest<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }, { auth: "none" });
    if (authStateVersion !== loginAuthStateVersion) {
      throw new StaleAuthSessionError();
    }
    beginAuthSession(response);
    return response;
  },

  async verifyEmail(token: string): Promise<MessageResponse> {
    return apiRequest<MessageResponse>("/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    }, { auth: "none" });
  },

  async resendVerification(email: string): Promise<ResendVerificationResponse> {
    return apiRequest<ResendVerificationResponse>("/auth/resend-verification", {
      method: "POST",
      body: JSON.stringify({ email }),
    }, { auth: "none" });
  },

  async forgotPassword(email: string): Promise<ForgotPasswordResponse> {
    return apiRequest<ForgotPasswordResponse>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }, { auth: "none" });
  },

  async resetPassword(token: string, newPassword: string): Promise<MessageResponse> {
    return apiRequest<MessageResponse>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, new_password: newPassword }),
    }, { auth: "none" });
  },

  async getMe(): Promise<User> {
    return apiRequest<User>("/auth/me", {
      method: "GET",
    });
  },

  restoreSession(): Promise<boolean> {
    return restoreAuthSession();
  },

  async logout(): Promise<void> {
    const refreshToken =
      authSession?.refreshToken ?? readStoredRefreshSession()?.refreshToken;
    clearAuthSession();
    if (!refreshToken) return;

    await apiRequest<Record<string, never>>(
      "/auth/logout",
      {
        method: "POST",
        body: JSON.stringify({ refresh_token: refreshToken }),
      },
      { auth: "none" },
    );
  },
};
