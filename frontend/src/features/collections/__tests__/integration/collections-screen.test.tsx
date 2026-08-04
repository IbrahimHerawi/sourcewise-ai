import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CollectionsScreen } from "@/features/collections/components/collections-screen";
import { installTestAuthSession } from "@test/helpers/auth";
import { renderWithDashboardHeader } from "@test/render/render-with-dashboard-header";

const { logoutMock, pushMock, replaceMock } = vi.hoisted(() => ({
  logoutMock: vi.fn(),
  pushMock: vi.fn(),
  replaceMock: vi.fn(),
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({ logout: logoutMock }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
  usePathname: () => "/dashboard/collections",
  useSearchParams: () => new URLSearchParams(),
}));

const collection = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "Quarterly Research",
  description: "Current-quarter evidence.",
  created_at: "2026-07-01T12:00:00Z",
  updated_at: "2026-07-02T12:00:00Z",
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

function installCollectionsApi(overrides?: (url: string, init?: RequestInit) => Response | undefined) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const overridden = overrides?.(url, init);
    if (overridden) return overridden;
    if (url.includes("/api/v1/collections?") && !init?.method) {
      return jsonResponse({ items: [collection], limit: 20, offset: 0, total: 1 });
    }
    if (url.endsWith("/api/v1/collections") && init?.method === "POST") {
      return jsonResponse({ ...collection, name: "Evidence Archive" }, 201);
    }
    if (url.endsWith(collection.id) && init?.method === "PATCH") {
      return jsonResponse({ ...collection, name: "Quarterly Insights" });
    }
    if (url.endsWith(collection.id) && init?.method === "DELETE") {
      return new Response(null, { status: 204 });
    }
    throw new Error(`Unexpected request: ${init?.method ?? "GET"} ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function collectionArticle(name: string): HTMLElement {
  const article = screen.getByRole("heading", { name }).closest("article");
  if (!article) throw new Error(`Collection article not found for ${name}`);
  return article;
}

describe("CollectionsScreen API integration", () => {
  beforeEach(() => {
    installTestAuthSession();
    logoutMock.mockReset();
    pushMock.mockReset();
    replaceMock.mockReset();
  });

  it("loads the authenticated collection page and renders backend-owned fields", async () => {
    const fetchMock = installCollectionsApi();
    renderWithDashboardHeader(<CollectionsScreen />);

    expect(screen.getByText("Loading collections")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: collection.name })).toBeVisible();
    expect(screen.getByText(collection.description)).toBeVisible();
    expect(screen.queryByText(/documents/i)).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/collections?limit=20&offset=0",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    const request = fetchMock.mock.calls[0];
    expect(new Headers(request[1]?.headers).get("Authorization")).toBe("Bearer test-token");
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
    expect(screen.queryByText(/document count|question count|ready/i)).not.toBeInTheDocument();
  });

  it("renders a successful empty page and paginates with limit and offset", async () => {
    const user = userEvent.setup();
    let empty = true;
    const fetchMock = installCollectionsApi((url) => {
      if (url.includes("/api/v1/collections?")) {
        if (empty) return jsonResponse({ items: [], limit: 20, offset: 0, total: 0 });
        const offset = new URL(url, "http://localhost").searchParams.get("offset");
        return jsonResponse({
          items: [{ ...collection, id: offset === "20" ? "77777777-7777-4777-8777-777777777777" : collection.id }],
          limit: 20,
          offset: Number(offset),
          total: 21,
        });
      }
    });
    const emptyView = renderWithDashboardHeader(<CollectionsScreen />);
    expect(await screen.findByRole("heading", { name: "No collections yet" })).toBeVisible();
    emptyView.unmount();

    empty = false;
    renderWithDashboardHeader(<CollectionsScreen />);
    await screen.findByRole("heading", { name: collection.name });
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(replaceMock).toHaveBeenCalledWith("/dashboard/collections?page=2", { scroll: false });
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) =>
      String(url).includes("/collections?limit=20&offset=20")
    )).toBe(true));
  });

  it("creates with the real request contract and preserves the dialog on a backend conflict", async () => {
    const user = userEvent.setup();
    let conflict = true;
    const fetchMock = installCollectionsApi((url, init) => {
      if (url.endsWith("/api/v1/collections") && init?.method === "POST" && conflict) {
        conflict = false;
        return jsonResponse(
          { error: { code: "collection_name_conflict", message: "Name already exists" } },
          409,
        );
      }
    });
    renderWithDashboardHeader(<CollectionsScreen />);
    await screen.findByRole("heading", { name: collection.name });

    await user.click(screen.getByRole("button", { name: "Create Collection" }));
    await user.type(screen.getByLabelText("Name"), "  Evidence Archive  ");
    await user.type(screen.getByLabelText("Description (optional)"), "  Interview evidence  ");
    await user.click(screen.getByRole("button", { name: "Create Collection" }));

    expect(await screen.findByText(/name is already in use/i)).toBeVisible();
    expect(screen.getByRole("dialog", { name: "Create collection" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Create Collection" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    const posts = fetchMock.mock.calls.filter(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(posts.at(-1)?.[1]?.body))).toEqual({
      name: "Evidence Archive",
      description: "Interview evidence",
    });
  });

  it("validates confirmed length rules locally and patches only changed fields", async () => {
    const user = userEvent.setup();
    const fetchMock = installCollectionsApi();
    renderWithDashboardHeader(<CollectionsScreen />);
    await screen.findByRole("heading", { name: collection.name });

    await user.click(within(collectionArticle(collection.name)).getByRole("button", { name: "Edit" }));
    const name = screen.getByLabelText("Name");
    fireEvent.change(name, { target: { value: "n".repeat(256) } });
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(screen.getByText("Name must be 255 characters or fewer.")).toBeVisible();

    await user.clear(name);
    await user.type(name, "Quarterly Insights");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    const patchCall = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(JSON.parse(String(patchCall?.[1]?.body))).toEqual({ name: "Quarterly Insights" });
  });

  it("maps backend validation details to the shared form fields", async () => {
    const user = userEvent.setup();
    installCollectionsApi((url, init) => {
      if (url.endsWith("/api/v1/collections") && init?.method === "POST") {
        return jsonResponse({
          error: {
            code: "validation_error",
            message: "Request validation failed.",
            details: {
              errors: [{
                type: "string_too_long",
                loc: ["body", "description"],
                msg: "Description is invalid on the server.",
                input: "invalid",
              }],
            },
          },
        }, 422);
      }
    });
    renderWithDashboardHeader(<CollectionsScreen />);
    await screen.findByRole("heading", { name: collection.name });
    await user.click(screen.getByRole("button", { name: "Create Collection" }));
    await user.type(screen.getByLabelText("Name"), "Evidence Archive");
    await user.click(screen.getByRole("button", { name: "Create Collection" }));

    expect(await screen.findByText("Description is invalid on the server.")).toBeVisible();
    expect(screen.getByRole("dialog", { name: "Create collection" })).toBeVisible();
  });

  it("confirms permanent collection deletion and refetches the current page", async () => {
    const user = userEvent.setup();
    let deleted = false;
    const fetchMock = installCollectionsApi((url, init) => {
      if (url.endsWith(collection.id) && init?.method === "DELETE") {
        deleted = true;
        return new Response(null, { status: 204 });
      }
      if (url.includes("/api/v1/collections?") && deleted) {
        return jsonResponse({ items: [], limit: 20, offset: 0, total: 0 });
      }
    });
    renderWithDashboardHeader(<CollectionsScreen />);
    await screen.findByRole("heading", { name: collection.name });

    await user.click(within(collectionArticle(collection.name)).getByRole("button", { name: "Delete" }));
    expect(screen.getByText(/remain and become unassigned/i)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Delete collection" }));

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) =>
        String(url).endsWith(collection.id) && init?.method === "DELETE"
      )).toBe(true);
    });
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("/collections?")).length).toBe(2);
    expect(await screen.findByRole("heading", { name: "No collections yet" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: collection.name })).not.toBeInTheDocument();
  });

  it("shows a genuine failed-query state, retries it, and logs out on 401", async () => {
    const user = userEvent.setup();
    let attempts = 0;
    installCollectionsApi((url) => {
      if (url.endsWith("/api/v1/auth/refresh")) {
        return jsonResponse(
          {
            error: {
              code: "invalid_refresh_token",
              message: "Refresh token is invalid or expired.",
            },
          },
          401,
        );
      }
      if (url.includes("/api/v1/collections?")) {
        attempts += 1;
        if (attempts === 1) {
          return jsonResponse({ error: { code: "unauthorized", message: "Session expired" } }, 401);
        }
      }
    });
    renderWithDashboardHeader(<CollectionsScreen />);

    expect(await screen.findByRole("heading", { name: "Collections couldn’t load" })).toBeVisible();
    expect(logoutMock).toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("heading", { name: collection.name })).toBeVisible();
  });
});
