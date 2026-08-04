import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  api,
  apiRequest,
  hasAuthSession,
  setAuthFailureHandler,
  setAuthSession,
} from "@/lib/api";

const originalRefreshToken =
  "original-refresh-token-with-at-least-thirty-two-characters";
const rotatedRefreshToken =
  "rotated-refresh-token-with-at-least-thirty-two-characters";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

function unauthorizedResponse(code = "unauthorized"): Response {
  return jsonResponse(
    {
      error: {
        code,
        message: "Authentication credentials could not be validated.",
      },
    },
    401,
  );
}

function tokenPair(
  accessToken: string,
  refreshToken: string,
  accessTokenExpiresIn = 1_800,
) {
  return {
    access_token: accessToken,
    refresh_token: refreshToken,
    token_type: "bearer" as const,
    access_token_expires_in: accessTokenExpiresIn,
    refresh_token_expires_in: 2_592_000,
  };
}

function installSession(accessToken = "access-token-a", expiresIn = 1_800): void {
  setAuthSession(tokenPair(accessToken, originalRefreshToken, expiresIn));
}

function requestUrl(input: RequestInfo | URL): string {
  return typeof input === "string" ? input : input.toString();
}

function bearerToken(init?: RequestInit): string | null {
  return new Headers(init?.headers).get("Authorization");
}

describe("authenticated API client", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("keeps login tokens in memory and refreshes an expired access token before requesting", async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = requestUrl(input);
        if (url.endsWith("/auth/login")) {
          return jsonResponse({
            ...tokenPair("access-token-a", originalRefreshToken, 1),
            user: {
              id: "11111111-1111-4111-8111-111111111111",
              first_name: "Test",
              last_name: "User",
              email: "test@example.com",
              is_email_verified: true,
              is_active: true,
              created_at: "2026-08-04T00:00:00Z",
            },
          });
        }
        if (url.endsWith("/auth/refresh")) {
          expect(init?.credentials).toBe("same-origin");
          expect(JSON.parse(String(init?.body))).toEqual({
            refresh_token: originalRefreshToken,
          });
          return jsonResponse(tokenPair("access-token-b", rotatedRefreshToken));
        }
        if (url.endsWith("/protected")) {
          expect(bearerToken(init)).toBe("Bearer access-token-b");
          return jsonResponse({ ok: true });
        }
        throw new Error(`Unexpected request: ${url}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    await api.login({ email: "test@example.com", password: "password" });
    const result = await apiRequest<{ ok: boolean }>("/protected");

    expect(result).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(localStorage.length).toBe(0);
  });

  it("rotates the refresh token and retries the original request exactly once", async () => {
    installSession();
    const calls: Array<{ authorization: string | null; url: string; body?: string }> = [];
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = requestUrl(input);
        calls.push({
          authorization: bearerToken(init),
          url,
          body: typeof init?.body === "string" ? init.body : undefined,
        });

        if (url.endsWith("/auth/refresh")) {
          return jsonResponse(tokenPair("access-token-b", rotatedRefreshToken));
        }
        if (url.endsWith("/protected") && bearerToken(init) === "Bearer access-token-a") {
          return unauthorizedResponse();
        }
        if (url.endsWith("/protected")) {
          return jsonResponse({ ok: true });
        }
        if (url.endsWith("/auth/logout")) {
          return new Response(null, { status: 204 });
        }
        throw new Error(`Unexpected request: ${url}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiRequest("/protected")).resolves.toEqual({ ok: true });
    await api.logout();

    expect(calls.filter(({ url }) => url.endsWith("/protected"))).toHaveLength(2);
    expect(calls.find(({ url }) => url.endsWith("/auth/refresh"))?.body).toBe(
      JSON.stringify({ refresh_token: originalRefreshToken }),
    );
    expect(calls.find(({ url }) => url.endsWith("/auth/logout"))?.body).toBe(
      JSON.stringify({ refresh_token: rotatedRefreshToken }),
    );
    expect(hasAuthSession()).toBe(false);
  });

  it("shares one refresh across simultaneous access-token failures", async () => {
    installSession();
    let resolveRefresh!: (response: Response) => void;
    const pendingRefresh = new Promise<Response>((resolve) => {
      resolveRefresh = resolve;
    });
    let refreshCalls = 0;
    let protectedCalls = 0;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = requestUrl(input);
        if (url.endsWith("/auth/refresh")) {
          refreshCalls += 1;
          return pendingRefresh;
        }
        if (url.endsWith("/protected")) {
          protectedCalls += 1;
          return bearerToken(init) === "Bearer access-token-a"
            ? unauthorizedResponse()
            : jsonResponse({ ok: true });
        }
        throw new Error(`Unexpected request: ${url}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    const firstRequest = apiRequest("/protected");
    const secondRequest = apiRequest("/protected");
    await vi.waitFor(() => expect(refreshCalls).toBe(1));
    resolveRefresh(jsonResponse(tokenPair("access-token-b", rotatedRefreshToken)));

    await expect(Promise.all([firstRequest, secondRequest])).resolves.toEqual([
      { ok: true },
      { ok: true },
    ]);
    expect(refreshCalls).toBe(1);
    expect(protectedCalls).toBe(4);
  });

  it("does not refresh an unrelated 401 response", async () => {
    installSession();
    const fetchMock = vi.fn(async () => unauthorizedResponse("billing_required"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiRequest("/protected")).rejects.toMatchObject({
      code: "billing_required",
      status: 401,
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(hasAuthSession()).toBe(true);
  });

  it.each([
    {
      name: "an invalid, expired, revoked, or reused refresh token",
      refreshResult: () =>
        jsonResponse(
          {
            error: {
              code: "invalid_refresh_token",
              message: "Refresh token is invalid or expired.",
            },
          },
          401,
        ),
    },
    {
      name: "an ambiguous refresh network failure",
      refreshResult: () => Promise.reject(new TypeError("Network unavailable")),
    },
  ])("clears authentication after $name", async ({ refreshResult }) => {
    installSession();
    const onAuthFailure = vi.fn();
    setAuthFailureHandler(onAuthFailure);
    let protectedCalls = 0;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL) => {
        const url = requestUrl(input);
        if (url.endsWith("/auth/refresh")) {
          return refreshResult();
        }
        protectedCalls += 1;
        return unauthorizedResponse();
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiRequest("/protected")).rejects.toBeInstanceOf(Error);
    expect(protectedCalls).toBe(1);
    expect(onAuthFailure).toHaveBeenCalledTimes(1);
    expect(hasAuthSession()).toBe(false);
  });

  it("stops after one refresh and one retry instead of entering a refresh loop", async () => {
    installSession();
    const onAuthFailure = vi.fn();
    setAuthFailureHandler(onAuthFailure);
    let refreshCalls = 0;
    let protectedCalls = 0;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL) => {
        const url = requestUrl(input);
        if (url.endsWith("/auth/refresh")) {
          refreshCalls += 1;
          return jsonResponse(tokenPair("access-token-b", rotatedRefreshToken));
        }
        protectedCalls += 1;
        return unauthorizedResponse();
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiRequest("/protected")).rejects.toMatchObject({
      code: "unauthorized",
      status: 401,
    });
    expect(refreshCalls).toBe(1);
    expect(protectedCalls).toBe(2);
    expect(onAuthFailure).toHaveBeenCalledTimes(1);
    expect(hasAuthSession()).toBe(false);
  });

  it("does not restore tokens from a refresh response that arrives after logout", async () => {
    installSession();
    let resolveRefresh!: (response: Response) => void;
    const pendingRefresh = new Promise<Response>((resolve) => {
      resolveRefresh = resolve;
    });
    let refreshStarted = false;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL) => {
        const url = requestUrl(input);
        if (url.endsWith("/auth/refresh")) {
          refreshStarted = true;
          return pendingRefresh;
        }
        if (url.endsWith("/auth/logout")) {
          return new Response(null, { status: 204 });
        }
        return unauthorizedResponse();
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    const staleRequest = apiRequest("/protected");
    await vi.waitFor(() => expect(refreshStarted).toBe(true));
    await api.logout();
    resolveRefresh(jsonResponse(tokenPair("access-token-b", rotatedRefreshToken)));

    await expect(staleRequest).rejects.toThrow(
      "authentication session changed",
    );
    expect(hasAuthSession()).toBe(false);
  });

  it("does not establish a login whose response arrives after logout", async () => {
    let resolveLogin!: (response: Response) => void;
    const pendingLogin = new Promise<Response>((resolve) => {
      resolveLogin = resolve;
    });
    let loginStarted = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = requestUrl(input);
        if (url.endsWith("/auth/login")) {
          loginStarted = true;
          return pendingLogin;
        }
        throw new Error(`Unexpected request: ${url}`);
      }),
    );

    const staleLogin = api.login({
      email: "test@example.com",
      password: "password",
    });
    await vi.waitFor(() => expect(loginStarted).toBe(true));
    await api.logout();
    resolveLogin(
      jsonResponse({
        ...tokenPair("access-token-a", originalRefreshToken),
        user: {
          id: "11111111-1111-4111-8111-111111111111",
          first_name: "Test",
          last_name: "User",
          email: "test@example.com",
          is_email_verified: true,
          is_active: true,
          created_at: "2026-08-04T00:00:00Z",
        },
      }),
    );

    await expect(staleLogin).rejects.toThrow("authentication session changed");
    expect(hasAuthSession()).toBe(false);
  });

  it("clears local state even when backend logout fails", async () => {
    installSession();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Network unavailable");
      }),
    );

    await expect(api.logout()).rejects.toBeInstanceOf(TypeError);
    expect(hasAuthSession()).toBe(false);
  });
});
