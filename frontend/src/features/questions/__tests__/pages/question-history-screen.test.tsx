import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QuestionHistoryScreen } from "@/features/questions/components/question-history-screen";
import { renderWithDashboardHeader } from "@test/render/render-with-dashboard-header";

const { logoutMock, replaceMock } = vi.hoisted(() => ({
  logoutMock: vi.fn(),
  replaceMock: vi.fn(),
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({ logout: logoutMock }),
}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/history",
  useRouter: () => ({ replace: replaceMock }),
  useSearchParams: () => new URLSearchParams(),
}));

const questionId = "11111111-1111-4111-8111-111111111111";
const collectionId = "22222222-2222-4222-8222-222222222222";
const documentId = "33333333-3333-4333-8333-333333333333";
const chunkId = "44444444-4444-4444-8444-444444444444";
const historyItem = {
  question_id: questionId,
  collection_id: collectionId,
  question: "What changed this quarter?",
  answer: "Revenue increased while churn declined.",
  citations: [
    {
      rank: 1,
      document_id: documentId,
      document_filename: "market-report.pdf",
      chunk_id: chunkId,
      chunk_index: 7,
      excerpt: "Revenue grew by twelve percent.",
      distance: 0.12,
    },
  ],
  created_at: "2026-07-02T12:00:00Z",
  provider: "openai",
  model: "gpt-test",
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

type HistoryApiOverride = (
  url: string,
  init?: RequestInit,
) => Promise<Response> | Response | undefined;

function installHistoryApi(override?: HistoryApiOverride) {
  let listRequests = 0;
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const overridden = await override?.(url, init);
      if (overridden) return overridden;
      if (url.includes("/api/v1/questions/history?") && !init?.method) {
        listRequests += 1;
        return jsonResponse({
          items: listRequests > 1 ? [] : [historyItem],
          limit: 20,
          offset: 0,
          total: listRequests > 1 ? 0 : 1,
        });
      }
      if (
        url.endsWith(`/api/v1/questions/history/${questionId}`) &&
        !init?.method
      ) {
        return jsonResponse(historyItem);
      }
      if (
        url.endsWith(`/api/v1/questions/history/${questionId}`) &&
        init?.method === "DELETE"
      ) {
        return new Response(null, { status: 204 });
      }
      throw new Error(`Unexpected request: ${init?.method ?? "GET"} ${url}`);
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("QuestionHistoryScreen", () => {
  beforeEach(() => {
    localStorage.setItem("sourcewise_token", "test-token");
    logoutMock.mockReset();
    replaceMock.mockReset();
  });

  it("loads unfiltered history and opens exact persisted citation details", async () => {
    const user = userEvent.setup();
    const fetchMock = installHistoryApi();
    renderWithDashboardHeader(<QuestionHistoryScreen />);

    expect(screen.getByText("Loading question history…")).toBeInTheDocument();
    await user.click(
      await screen.findByRole("button", { name: historyItem.question }),
    );
    const dialog = await screen.findByRole("dialog", {
      name: "Question details",
    });
    expect(within(dialog).getByText(historyItem.answer)).toBeVisible();
    expect(within(dialog).getByText(historyItem.citations[0].excerpt)).toBeVisible();
    expect(within(dialog).getByText("market-report.pdf")).toBeVisible();
    expect(within(dialog).queryByText(/collection name|source url|page/i)).not.toBeInTheDocument();

    const listCall = fetchMock.mock.calls.find(([url]) =>
      String(url).includes("/questions/history?"),
    );
    expect(String(listCall?.[0])).toContain(
      "/questions/history?limit=20&offset=0",
    );
    expect(new Headers(listCall?.[1]?.headers).get("Authorization")).toBe(
      "Bearer test-token",
    );
    expect(listCall?.[1]?.cache).toBe("no-store");
  });

  it("deletes by backend question id and refreshes the public list", async () => {
    const user = userEvent.setup();
    const fetchMock = installHistoryApi();
    renderWithDashboardHeader(<QuestionHistoryScreen />);
    await screen.findByRole("button", { name: historyItem.question });

    await user.click(
      screen.getByRole("button", {
        name: `Actions for question: ${historyItem.question}`,
      }),
    );
    await user.click(
      screen.getByRole("menuitem", { name: "Delete history item" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Delete history item" }),
    );

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) =>
            String(url).endsWith(`/questions/history/${questionId}`) &&
            init?.method === "DELETE",
        ),
      ).toBe(true),
    );
    expect(await screen.findByRole("heading", { name: "No question history" })).toBeVisible();
    expect(
      fetchMock.mock.calls.filter(([url]) =>
        String(url).includes("/questions/history?"),
      ),
    ).toHaveLength(2);
  });

  it("renders the successful empty state without production mock history", async () => {
    installHistoryApi((url, init) => {
      if (url.includes("/questions/history?") && !init?.method) {
        return jsonResponse({ items: [], limit: 20, offset: 0, total: 0 });
      }
    });
    renderWithDashboardHeader(<QuestionHistoryScreen />);

    expect(
      await screen.findByRole("heading", { name: "No question history" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Ask a question" })).toHaveAttribute(
      "href",
      "/dashboard/ask-question",
    );
  });

  it("paginates with real limit and offset values", async () => {
    const user = userEvent.setup();
    const fetchMock = installHistoryApi((url, init) => {
      if (url.includes("/questions/history?") && !init?.method) {
        const offset = Number(
          new URL(url, "http://localhost").searchParams.get("offset"),
        );
        return jsonResponse({
          items: [historyItem],
          limit: 20,
          offset,
          total: 21,
        });
      }
    });
    renderWithDashboardHeader(<QuestionHistoryScreen />);
    await screen.findByRole("button", { name: historyItem.question });

    await user.click(screen.getByRole("button", { name: "Go to next page" }));
    expect(replaceMock).toHaveBeenCalledWith("/dashboard/history?page=2", {
      scroll: false,
    });
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) =>
          String(url).includes("/questions/history?limit=20&offset=20"),
        ),
      ).toBe(true),
    );
  });

  it("uses safe authorization errors and logs out on authentication failure", async () => {
    const fetchMock = installHistoryApi((url, init) => {
      if (url.includes("/questions/history?") && !init?.method) {
        return jsonResponse(
          {
            error: {
              code: "forbidden",
              message: "SENTINEL_RAW_HISTORY_ERROR",
            },
          },
          403,
        );
      }
    });
    const firstView = renderWithDashboardHeader(<QuestionHistoryScreen />);
    expect(
      await screen.findByRole("heading", {
        name: "Question history isn’t available",
      }),
    ).toBeVisible();
    expect(screen.queryByText("SENTINEL_RAW_HISTORY_ERROR")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
    firstView.unmount();

    fetchMock.mockImplementation(async () =>
      jsonResponse(
        {
          error: {
            code: "unauthorized",
            message: "SENTINEL_RAW_AUTH_ERROR",
          },
        },
        401,
      ),
    );
    renderWithDashboardHeader(<QuestionHistoryScreen />);
    await waitFor(() => expect(logoutMock).toHaveBeenCalled());
    expect(screen.queryByText("SENTINEL_RAW_AUTH_ERROR")).not.toBeInTheDocument();
  });
});
