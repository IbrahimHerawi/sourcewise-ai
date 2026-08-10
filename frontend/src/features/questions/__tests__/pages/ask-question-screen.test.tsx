import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AskQuestionScreen } from "@/features/questions/components/ask-question-screen";
import { installTestAuthSession } from "@test/helpers/auth";
import { renderWithDashboardHeader } from "@test/render/render-with-dashboard-header";

const { logoutMock, replaceMock } = vi.hoisted(() => ({
  logoutMock: vi.fn(),
  replaceMock: vi.fn(),
}));
vi.mock("@/hooks/use-auth", () => ({ useAuth: () => ({ logout: logoutMock }) }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
  usePathname: () => "/dashboard/ask-question",
  useSearchParams: () => new URLSearchParams(),
}));

const collectionId = "11111111-1111-4111-8111-111111111111";
const secondCollectionId = "22222222-2222-4222-8222-222222222222";
const documentId = "33333333-3333-4333-8333-333333333333";
const secondDocumentId = "44444444-4444-4444-8444-444444444444";
const questionId = "55555555-5555-4555-8555-555555555555";
const chunkId = "66666666-6666-4666-8666-666666666666";
const collection = {
  id: collectionId,
  name: "Quarterly Research",
  description: null,
  created_at: "2026-07-01T12:00:00Z",
  updated_at: "2026-07-02T12:00:00Z",
};
const secondCollection = {
  ...collection,
  id: secondCollectionId,
  name: "Customer Evidence",
};
const readyDocument = {
  id: documentId,
  collection_id: collectionId,
  filename: "report.pdf",
  original_extension: ".pdf",
  content_type: "application/pdf",
  size_bytes: 2_048,
  status: "READY",
  error_message: null,
  created_at: "2026-07-01T12:00:00Z",
  updated_at: "2026-07-02T12:00:00Z",
};
const pendingDocument = {
  ...readyDocument,
  id: secondDocumentId,
  collection_id: secondCollectionId,
  filename: "notes.txt",
  original_extension: ".txt",
  content_type: "text/plain",
  status: "PROCESSING",
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

function answerResponse(overrides: Record<string, unknown> = {}) {
  return {
    question_id: questionId,
    collection_id: collectionId,
    answer: "Revenue grew.",
    citations: [
      {
        rank: 1,
        document_id: documentId,
        document_filename: "report.pdf",
        chunk_id: chunkId,
        chunk_index: 2,
        excerpt: "Revenue grew by twelve percent.",
        distance: 0.1,
      },
    ],
    created_at: "2026-07-02T12:00:00Z",
    provider: null,
    model: null,
    ...overrides,
  };
}

type QuestionApiOptions = {
  ask?: (init: RequestInit) => Promise<Response> | Response;
  collections?: unknown;
  documents?: unknown;
};

function installQuestionApi(options: QuestionApiOptions = {}) {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/v1/collections?") && !init?.method) {
        return jsonResponse(
          options.collections ?? {
            items: [collection, secondCollection],
            limit: 100,
            offset: 0,
            total: 2,
          },
        );
      }
      if (url.includes("/api/v1/documents?") && !init?.method) {
        return jsonResponse(
          options.documents ?? {
            items: [readyDocument, pendingDocument],
            limit: 100,
            offset: 0,
            total: 2,
          },
        );
      }
      if (url.endsWith("/api/v1/questions/ask") && init?.method === "POST") {
        return options.ask?.(init) ?? jsonResponse(answerResponse());
      }
      throw new Error(`Unexpected request: ${init?.method ?? "GET"} ${url}`);
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("AskQuestionScreen", () => {
  beforeEach(() => {
    installTestAuthSession();
    logoutMock.mockReset();
    replaceMock.mockReset();
  });

  it("loads collections and document readiness through authenticated, uncached requests", async () => {
    const fetchMock = installQuestionApi();
    renderWithDashboardHeader(<AskQuestionScreen />);

    expect(screen.getByText("Loading the question form")).toBeInTheDocument();
    expect(
      await screen.findByText(
        "Select a collection to see which ready documents will be searched.",
      ),
    ).toBeVisible();
    expect(screen.getByLabelText("Collection")).toHaveTextContent(
      "Select collection",
    );
    expect(
      screen.queryByRole("option", { name: "All documents" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask question" })).toBeDisabled();

    const contextCalls = fetchMock.mock.calls.filter(([url]) =>
      /\/(collections|documents)\?/.test(String(url)),
    );
    expect(contextCalls).toHaveLength(2);
    for (const [, init] of contextCalls) {
      expect(new Headers(init?.headers).get("Authorization")).toBe(
        "Bearer test-token",
      );
      expect(init?.cache).toBe("no-store");
      expect(init?.signal).toBeInstanceOf(AbortSignal);
    }
  });

  it("submits the exact non-streaming collection contract and renders backend citations", async () => {
    const user = userEvent.setup();
    const fetchMock = installQuestionApi();
    renderWithDashboardHeader(
      <AskQuestionScreen initialCollectionId={collectionId} />,
    );
    await screen.findByText(
      `1 ready document will be searched in ${collection.name}.`,
    );

    await user.type(screen.getByLabelText("Ask your question"), "  What changed?  ");
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    expect(await screen.findByText("Revenue grew.")).toBeVisible();
    expect(screen.getByText("Revenue grew by twelve percent.")).toBeVisible();
    expect(screen.getByText("report.pdf")).toBeVisible();
    expect(screen.getByText("Chunk 2")).toBeVisible();
    expect(screen.getByText("Cosine distance 0.100")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "View saved answer in History" }),
    ).toHaveAttribute("href", "/dashboard/history");

    const askCall = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(askCall?.[1]?.body))).toEqual({
      question: "What changed?",
      collection_id: collectionId,
    });
    expect(new Headers(askCall?.[1]?.headers).get("Authorization")).toBe(
      "Bearer test-token",
    );
    expect(screen.queryByText(/conversation|streaming|typing/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/page 2|source url/i)).not.toBeInTheDocument();
    expect(document.activeElement).toBe(
      screen.getByRole("region", { name: "Answer" }),
    );
  });

  it("renders the backend generation provider and model when they are present", async () => {
    const user = userEvent.setup();
    installQuestionApi({
      ask: () =>
        jsonResponse(
          answerResponse({
            provider: "openai",
            model: "gpt-test",
          }),
        ),
    });
    renderWithDashboardHeader(
      <AskQuestionScreen initialCollectionId={collectionId} />,
    );
    await screen.findByText(/ready document will be searched/i);
    await user.type(
      screen.getByLabelText("Ask your question"),
      "Which model answered?",
    );
    await user.click(screen.getByRole("button", { name: "Ask question" }));

    expect(
      await screen.findByText("Generated with OpenAI · gpt-test"),
    ).toBeVisible();
  });

  it("prevents duplicate submissions and announces the non-streaming pending state", async () => {
    const user = userEvent.setup();
    let resolveAsk: ((response: Response) => void) | undefined;
    const fetchMock = installQuestionApi({
      ask: () =>
        new Promise<Response>((resolve) => {
          resolveAsk = resolve;
        }),
    });
    renderWithDashboardHeader(
      <AskQuestionScreen initialCollectionId={collectionId} />,
    );
    await screen.findByText(/ready document will be searched/i);
    await user.type(
      screen.getByLabelText("Ask your question"),
      "What is available?",
    );
    await user.click(screen.getByRole("button", { name: "Ask question" }));

    expect(screen.getByRole("button", { name: "Answering…" })).toBeDisabled();
    expect(screen.getByText(`Reviewing ${collection.name}`)).toBeVisible();
    const form = screen.getByRole("button", { name: "Answering…" }).closest("form");
    if (!form) throw new Error("Question form not found");
    fireEvent.submit(form);
    expect(
      fetchMock.mock.calls.filter(([, init]) => init?.method === "POST"),
    ).toHaveLength(1);
    resolveAsk?.(jsonResponse(answerResponse({ answer: "Complete.", citations: [] })));

    expect(await screen.findByText("Complete.")).toBeVisible();
  });

  it("enforces the backend question constraints with associated accessible errors", async () => {
    const user = userEvent.setup();
    const fetchMock = installQuestionApi();
    renderWithDashboardHeader(<AskQuestionScreen />);
    await screen.findByText(/select a collection to see which ready documents/i);
    const input = screen.getByLabelText("Ask your question");
    expect(screen.getByRole("button", { name: "Ask question" })).toBeDisabled();

    await user.type(input, "   ");
    await user.tab();
    expect(screen.getByText("Enter a question.")).toBeVisible();
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription(/Enter a question/);

    fireEvent.change(input, {
      target: { value: "q".repeat(4_001) },
    });
    fireEvent.blur(input);
    expect(screen.getByText("Question must be 4,000 characters or fewer.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Ask question" })).toBeDisabled();
    expect(
      fetchMock.mock.calls.filter(([, init]) => init?.method === "POST"),
    ).toHaveLength(0);

    fireEvent.change(input, { target: { value: "What changed?" } });
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    expect(screen.getByText("Select a collection.")).toBeVisible();
    expect(screen.getByLabelText("Collection")).toHaveAccessibleDescription(
      "Select a collection.",
    );

    await user.click(screen.getByLabelText("Collection"));
    await user.click(
      screen.getByRole("option", { name: collection.name }),
    );
    expect(screen.queryByText("Select a collection.")).not.toBeInTheDocument();
  });

  it("keeps input after a provider failure, hides raw errors, and retries only a safe failure", async () => {
    const user = userEvent.setup();
    let askAttempts = 0;
    installQuestionApi({
      ask: () => {
        askAttempts += 1;
        return askAttempts === 1
          ? jsonResponse(
              {
                error: {
                  code: "question_answering_unavailable",
                  message: "SENTINEL_RAW_PROVIDER_ERROR",
                },
              },
              503,
            )
          : jsonResponse(answerResponse());
      },
    });
    renderWithDashboardHeader(
      <AskQuestionScreen initialCollectionId={collectionId} />,
    );
    await screen.findByText(/ready document will be searched/i);

    const input = screen.getByLabelText("Ask your question");
    await user.type(input, "What changed?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    expect(
      await screen.findByText("Question answering is temporarily unavailable"),
    ).toBeVisible();
    expect(screen.queryByText("SENTINEL_RAW_PROVIDER_ERROR")).not.toBeInTheDocument();
    expect(input).toHaveValue("What changed?");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(askAttempts).toBe(2));
    expect(await screen.findByText("Revenue grew.")).toBeVisible();
  });

  it("does not offer a fake retry for an ambiguous network failure", async () => {
    const user = userEvent.setup();
    installQuestionApi({
      ask: () => Promise.reject(new TypeError("SENTINEL_NETWORK_DETAIL")),
    });
    renderWithDashboardHeader(
      <AskQuestionScreen initialCollectionId={collectionId} />,
    );
    await screen.findByText(/ready document will be searched/i);

    const input = screen.getByLabelText("Ask your question");
    await user.type(input, "Was this saved?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));

    expect(await screen.findByText("Can’t reach the answer service")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
    expect(screen.queryByText("SENTINEL_NETWORK_DETAIL")).not.toBeInTheDocument();
    expect(input).toHaveValue("Was this saved?");
  });

  it.each([
    {
      code: "validation_error",
      expectedTitle: "The question couldn’t be submitted",
      retry: false,
      status: 422,
    },
    {
      code: "rate_limited",
      expectedTitle: "Question limit reached",
      retry: true,
      status: 429,
    },
    {
      code: "internal_server_error",
      expectedTitle: "The question couldn’t be answered",
      retry: false,
      status: 500,
    },
  ])(
    "handles a $status response without exposing backend details",
    async ({ code, expectedTitle, retry, status }) => {
      const user = userEvent.setup();
      installQuestionApi({
        ask: () =>
          jsonResponse(
            { error: { code, message: `SENTINEL_RAW_${status}` } },
            status,
          ),
      });
      renderWithDashboardHeader(
        <AskQuestionScreen initialCollectionId={collectionId} />,
      );
      await screen.findByText(/ready document will be searched/i);
      await user.type(
        screen.getByLabelText("Ask your question"),
        "What changed?",
      );
      await user.click(screen.getByRole("button", { name: "Ask question" }));

      expect(await screen.findByText(expectedTitle)).toBeVisible();
      expect(screen.queryByText(`SENTINEL_RAW_${status}`)).not.toBeInTheDocument();
      if (retry) {
        expect(screen.getByRole("button", { name: "Try again" })).toBeVisible();
      } else {
        expect(
          screen.queryByRole("button", { name: "Try again" }),
        ).not.toBeInTheDocument();
      }
    },
  );

  it("requires a collection when no collection options are available", async () => {
    const user = userEvent.setup();
    installQuestionApi({
      collections: { items: [], limit: 100, offset: 0, total: 0 },
      documents: {
        items: [pendingDocument],
        limit: 100,
        offset: 0,
        total: 1,
      },
      ask: () =>
        jsonResponse(
          answerResponse({
            collection_id: null,
            answer: "I could not find the answer in the uploaded documents.",
            citations: [],
          }),
        ),
    });
    renderWithDashboardHeader(<AskQuestionScreen />);

    expect(
      await screen.findByText(
        "Select a collection to see which ready documents will be searched.",
      ),
    ).toBeVisible();
    expect(screen.getByLabelText("Collection")).toHaveTextContent(
      "Select collection",
    );
    await user.type(
      screen.getByLabelText("Ask your question"),
      "What is available?",
    );
    expect(screen.getByRole("button", { name: "Ask question" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    expect(
      screen.getByText("Select a collection."),
    ).toBeVisible();
    expect(
      vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === "POST"),
    ).toHaveLength(0);
  });

  it("preserves a linked scope when collections fail and handles source authorization safely", async () => {
    installQuestionApi({
      collections: {
        error: {
          code: "service_unavailable",
          message: "SENTINEL_COLLECTION_ERROR",
        },
      },
      documents: {
        error: { code: "forbidden", message: "SENTINEL_FORBIDDEN_ERROR" },
      },
    });
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/collections?")) {
          return jsonResponse(
            {
              error: {
                code: "service_unavailable",
                message: "SENTINEL_COLLECTION_ERROR",
              },
            },
            503,
          );
        }
        if (url.includes("/documents?")) {
          return jsonResponse(
            {
              error: {
                code: "forbidden",
                message: "SENTINEL_FORBIDDEN_ERROR",
              },
            },
            403,
          );
        }
        throw new Error(`Unexpected request: ${init?.method ?? "GET"} ${url}`);
      },
    );

    renderWithDashboardHeader(
      <AskQuestionScreen initialCollectionId={collectionId} />,
    );
    expect(await screen.findByText("Collections couldn’t load")).toBeVisible();
    expect(screen.getByText("Documents aren’t available")).toBeVisible();
    expect(screen.queryByText(/SENTINEL_/)).not.toBeInTheDocument();
    expect(screen.getByLabelText("Collection")).toHaveTextContent(
      "Selected collection",
    );
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("logs out on authentication failure and rejects mismatched response identifiers", async () => {
    const user = userEvent.setup();
    const fetchMock = installQuestionApi({
      ask: () =>
        jsonResponse(
          answerResponse({
            collection_id: secondCollectionId,
          }),
        ),
    });
    renderWithDashboardHeader(
      <AskQuestionScreen initialCollectionId={collectionId} />,
    );
    await screen.findByText(/ready document will be searched/i);
    await user.type(screen.getByLabelText("Ask your question"), "What changed?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    expect(await screen.findByText("The answer couldn’t be verified")).toBeVisible();

    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/auth/refresh")) {
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
      if (String(input).includes("/collections?")) {
        return jsonResponse(
          {
            error: { code: "unauthorized", message: "SENTINEL_AUTH_ERROR" },
          },
          401,
        );
      }
      return jsonResponse({
        items: [],
        limit: 100,
        offset: 0,
        total: 0,
      });
    });
    renderWithDashboardHeader(<AskQuestionScreen />);
    await waitFor(() => expect(logoutMock).toHaveBeenCalled());
    expect(screen.queryByText("SENTINEL_AUTH_ERROR")).not.toBeInTheDocument();
  });

  it("aborts an in-flight answer request when the page unmounts", async () => {
    const user = userEvent.setup();
    let answerSignal: AbortSignal | undefined;
    installQuestionApi({
      ask: (init) => {
        answerSignal = init.signal as AbortSignal;
        return new Promise<Response>(() => undefined);
      },
    });
    const view = renderWithDashboardHeader(
      <AskQuestionScreen initialCollectionId={collectionId} />,
    );
    await screen.findByText(/ready document will be searched/i);
    await user.type(screen.getByLabelText("Ask your question"), "Keep working?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    expect(answerSignal?.aborted).toBe(false);

    view.unmount();
    expect(answerSignal?.aborted).toBe(true);
  });

  it("renders multiple citations and an empty backend answer without crashing", async () => {
    const user = userEvent.setup();
    const secondChunkId = "77777777-7777-4777-8777-777777777777";
    installQuestionApi({
      ask: () =>
        jsonResponse(
          answerResponse({
            answer: "",
            citations: [
              answerResponse().citations[0],
              {
                rank: 2,
                document_id: documentId,
                document_filename: "report.pdf",
                chunk_id: secondChunkId,
                chunk_index: 4,
                excerpt: "A second exact excerpt.",
                distance: 0.2,
              },
            ],
          }),
        ),
    });
    renderWithDashboardHeader(
      <AskQuestionScreen initialCollectionId={collectionId} />,
    );
    await screen.findByText(/ready document will be searched/i);
    await user.type(screen.getByLabelText("Ask your question"), "What changed?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));

    expect(await screen.findByText("The server returned an empty answer.")).toBeVisible();
    const citations = screen.getByRole("region", {
      name: "Supporting excerpts",
    });
    expect(within(citations).getAllByRole("listitem")).toHaveLength(2);
    expect(within(citations).getByText("A second exact excerpt.")).toBeVisible();
  });
});
