import { beforeEach, describe, expect, it, vi } from "vitest";
import { questionHistoryQueryKeys } from "@/features/questions/hooks/use-question-history";
import { questionSourceQueryKey } from "@/features/questions/hooks/use-question-sources";
import {
  askQuestionApi,
  getQuestionHistoryItemApi,
  listQuestionHistoryApi,
} from "@/features/questions/questions-api";
import { installTestAuthSession } from "@test/helpers/auth";

const collectionId = "11111111-1111-4111-8111-111111111111";
const questionId = "22222222-2222-4222-8222-222222222222";
const documentId = "33333333-3333-4333-8333-333333333333";
const chunkId = "44444444-4444-4444-8444-444444444444";

function answerResponse(overrides: Record<string, unknown> = {}) {
  return {
    question_id: questionId,
    collection_id: null,
    answer: "A grounded answer.",
    citations: [
      {
        rank: 1,
        document_id: documentId,
        document_filename: "source.pdf",
        chunk_id: chunkId,
        chunk_index: 0,
        excerpt: "An exact backend excerpt.",
        distance: 0.12,
      },
    ],
    created_at: "2026-07-02T12:00:00Z",
    provider: null,
    model: null,
    ...overrides,
  };
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

describe("Questions API contract", () => {
  beforeEach(() => {
    installTestAuthSession();
  });

  it("submits only the supported question and optional collection fields", async () => {
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) =>
        jsonResponse(answerResponse({ collection_id: collectionId })),
    );
    vi.stubGlobal("fetch", fetchMock);

    await askQuestionApi({
      collectionId,
      question: "What changed?",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/questions/ask",
      expect.objectContaining({
        body: JSON.stringify({
          question: "What changed?",
          collection_id: collectionId,
        }),
        cache: "no-store",
        method: "POST",
      }),
    );
    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers);
    expect(headers.get("Authorization")).toBe("Bearer test-token");
  });

  it("rejects unexpected providers, missing citation fields, and mismatched scope ids", async () => {
    const invalidResponses = [
      answerResponse({ provider: "unsupported" }),
      answerResponse({
        citations: [{ ...answerResponse().citations[0], excerpt: undefined }],
      }),
      answerResponse({ collection_id: collectionId }),
    ];

    for (const response of invalidResponses) {
      vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(response)));
      await expect(
        askQuestionApi({ collectionId: null, question: "Is this valid?" }),
      ).rejects.toMatchObject({ code: "invalid_response" });
    }
  });

  it("turns malformed successful JSON into a safe invalid-response error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response("{not-json", {
          headers: { "Content-Type": "application/json" },
          status: 200,
        }),
      ),
    );

    await expect(
      askQuestionApi({ collectionId: null, question: "What changed?" }),
    ).rejects.toMatchObject({
      code: "invalid_response",
      status: 200,
    });
  });

  it("uses backend pagination and the optional collection filter exactly", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        items: [],
        limit: 20,
        offset: 40,
        total: 40,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await listQuestionHistoryApi({
      collectionId,
      limit: 20,
      offset: 40,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/questions/history?limit=20&offset=40&collection_id=${collectionId}`,
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("rejects pagination metadata that does not match the requested page", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          items: [],
          limit: 20,
          offset: 0,
          total: 0,
        }),
      ),
    );

    await expect(
      listQuestionHistoryApi({ limit: 20, offset: 20 }),
    ).rejects.toMatchObject({ code: "invalid_response" });
  });

  it("rejects a history detail response for a different question id", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          ...answerResponse({
            question_id: "55555555-5555-4555-8555-555555555555",
          }),
          question: "What changed?",
        }),
      ),
    );

    await expect(
      getQuestionHistoryItemApi(questionId),
    ).rejects.toMatchObject({ code: "invalid_response" });
  });

  it("uses stable, distinct keys for source and history requests", () => {
    expect(questionSourceQueryKey).toEqual(["questions", "sources"]);
    expect(questionHistoryQueryKeys.list(20, 40)).toEqual([
      "questions",
      "history",
      { limit: 20, offset: 40 },
    ]);
    expect(questionHistoryQueryKeys.all).not.toEqual(questionSourceQueryKey);
  });
});
