import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AskQuestionScreen } from "@/features/questions/components/ask-question-screen";
import { getAccessibilityViolations } from "@test/helpers/accessibility";
import { installTestAuthSession } from "@test/helpers/auth";
import { renderWithDashboardHeader } from "@test/render/render-with-dashboard-header";

const { logoutMock, replaceMock } = vi.hoisted(() => ({
  logoutMock: vi.fn(),
  replaceMock: vi.fn(),
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({ logout: logoutMock }),
}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/ask-question",
  useRouter: () => ({ replace: replaceMock }),
  useSearchParams: () => new URLSearchParams(),
}));

const collectionId = "11111111-1111-4111-8111-111111111111";

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}

function installContextApi() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/collections?")) {
        return jsonResponse({
          items: [
            {
              id: collectionId,
              name: "Research",
              description: null,
              created_at: "2026-07-01T12:00:00Z",
              updated_at: "2026-07-02T12:00:00Z",
            },
          ],
          limit: 100,
          offset: 0,
          total: 1,
        });
      }
      if (url.includes("/documents?")) {
        return jsonResponse({
          items: [],
          limit: 100,
          offset: 0,
          total: 0,
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    }),
  );
}

describe("Ask Question accessibility", () => {
  beforeEach(() => {
    installTestAuthSession();
    logoutMock.mockReset();
    replaceMock.mockReset();
    installContextApi();
  });

  it("has no detectable axe violations in the loaded no-ready-source state", async () => {
    const view = renderWithDashboardHeader(<AskQuestionScreen />);
    await screen.findByText("No documents have been uploaded");

    expect(await getAccessibilityViolations(view.container)).toEqual([]);
  });

  it("supports keyboard input, collection selection, and disabled-action semantics", async () => {
    const user = userEvent.setup();
    renderWithDashboardHeader(<AskQuestionScreen />);
    await screen.findByText("No documents have been uploaded");

    const question = screen.getByLabelText("Ask your question");
    const selector = screen.getByLabelText("Collection");
    const submit = screen.getByRole("button", { name: "Ask question" });
    expect(submit).toBeDisabled();

    question.focus();
    await user.type(question, "What is supported?");
    expect(submit).toBeEnabled();

    selector.focus();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("option", { name: "All documents" })).toBeVisible();
    expect(screen.getByRole("option", { name: "Research" })).toBeVisible();
    await user.keyboard("{Escape}");
    expect(selector).toHaveFocus();
  });
});
