import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AskCollectionPage } from "@/features/collections/components/ask/ask-collection-page";
import { renderWithDashboardHeader } from "@test/render/render-with-dashboard-header";

const { logoutMock } = vi.hoisted(() => ({ logoutMock: vi.fn() }));
vi.mock("@/hooks/use-auth", () => ({ useAuth: () => ({ logout: logoutMock }) }));
vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/ask-question",
  useSearchParams: () => new URLSearchParams(),
}));

const collectionId = "11111111-1111-4111-8111-111111111111";
const collection = {
  id: collectionId,
  name: "Quarterly Research",
  description: null,
  created_at: "2026-07-01T12:00:00Z",
  updated_at: "2026-07-02T12:00:00Z",
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

describe("AskCollectionPage", () => {
  beforeEach(() => {
    localStorage.setItem("sourcewise_token", "test-token");
    logoutMock.mockReset();
  });

  it("requires collection context when opened without an identifier", () => {
    renderWithDashboardHeader(<AskCollectionPage />);
    expect(screen.getByRole("heading", { name: "Choose a collection first" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Browse Collections" })).toHaveAttribute(
      "href",
      "/dashboard/collections",
    );
  });

  it("submits the non-streaming scoped question contract and renders returned citations", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith(`/api/v1/collections/${collectionId}`)) return jsonResponse(collection);
      if (url.endsWith("/api/v1/questions/ask") && init?.method === "POST") {
        return jsonResponse({
          question_id: "33333333-3333-4333-8333-333333333333",
          collection_id: collectionId,
          answer: "Revenue grew.",
          citations: [{
            rank: 1,
            document_id: "22222222-2222-4222-8222-222222222222",
            document_filename: "report.pdf",
            chunk_id: "chunk-1",
            chunk_index: 2,
            excerpt: "Revenue grew by twelve percent.",
            distance: 0.1,
          }],
          created_at: "2026-07-02T12:00:00Z",
          provider: "openai",
          model: "gpt-test",
        });
      }
      throw new Error(`Unexpected request: ${init?.method ?? "GET"} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithDashboardHeader(<AskCollectionPage collectionId={collectionId} />);
    await screen.findByRole("heading", { level: 2, name: `Ask ${collection.name}` });

    await user.type(screen.getByLabelText("Question"), "  What changed?  ");
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    expect(await screen.findByText("Revenue grew.")).toBeVisible();
    expect(screen.getByText("Revenue grew by twelve percent.")).toBeVisible();

    const askCall = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(askCall?.[1]?.body))).toEqual({
      question: "What changed?",
      collection_id: collectionId,
    });
    expect(screen.queryByText(/conversation|streaming|typing/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/page 2|source url/i)).not.toBeInTheDocument();
  });

  it("shows a non-streaming pending state and accepts a fallback answer with no citations", async () => {
    const user = userEvent.setup();
    let resolveAsk: ((response: Response) => void) | undefined;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith(`/api/v1/collections/${collectionId}`)) {
        return Promise.resolve(jsonResponse(collection));
      }
      if (url.endsWith("/api/v1/questions/ask") && init?.method === "POST") {
        return new Promise<Response>((resolve) => {
          resolveAsk = resolve;
        });
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    }));
    renderWithDashboardHeader(<AskCollectionPage collectionId={collectionId} />);
    await screen.findByRole("heading", { level: 2, name: `Ask ${collection.name}` });
    await user.type(screen.getByLabelText("Question"), "What is available?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));

    expect(screen.getByRole("button", { name: "Answering…" })).toBeDisabled();
    expect(screen.getByText("Reviewing available context")).toBeVisible();
    resolveAsk?.(jsonResponse({
      question_id: "33333333-3333-4333-8333-333333333333",
      collection_id: collectionId,
      answer: "I could not find enough ready document context to answer this question.",
      citations: [],
      created_at: "2026-07-02T12:00:00Z",
      provider: null,
      model: null,
    }));

    expect(await screen.findByText(/could not find enough ready document context/i)).toBeVisible();
    expect(screen.getByText(/No supporting excerpts were found/i)).toBeVisible();
    expect(screen.getByText("No citations were returned for this answer.")).toBeVisible();
  });

  it("validates the backend-confirmed question constraints before submission", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith(`/api/v1/collections/${collectionId}`)) return jsonResponse(collection);
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithDashboardHeader(<AskCollectionPage collectionId={collectionId} />);
    await screen.findByRole("heading", { level: 2, name: `Ask ${collection.name}` });

    await user.click(screen.getByRole("button", { name: "Ask question" }));
    expect(screen.getByText("Enter a question.")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "q".repeat(4_001) },
    });
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    expect(screen.getByText("Question must be 4,000 characters or fewer.")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("keeps backend failures inline and allows a real retry by resubmission", async () => {
    const user = userEvent.setup();
    let askAttempts = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith(`/api/v1/collections/${collectionId}`)) return jsonResponse(collection);
      if (url.endsWith("/api/v1/questions/ask") && init?.method === "POST") {
        askAttempts += 1;
        return jsonResponse({ error: { code: "provider_error", message: "Answer service unavailable" } }, 503);
      }
      throw new Error(`Unexpected request: ${url}`);
    }));
    renderWithDashboardHeader(<AskCollectionPage collectionId={collectionId} />);
    await screen.findByRole("heading", { level: 2, name: `Ask ${collection.name}` });

    await user.type(screen.getByLabelText("Question"), "What changed?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    expect(await screen.findByText("Answer service unavailable")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    await waitFor(() => expect(askAttempts).toBe(2));
  });
});
