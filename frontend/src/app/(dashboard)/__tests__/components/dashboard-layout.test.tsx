import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DashboardLayout from "@/app/(dashboard)/layout";

const { authState, replaceMock } = vi.hoisted(() => ({
  authState: {
    isAuthenticated: false,
    isLoading: false,
  },
  replaceMock: vi.fn(),
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => authState,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
}));

vi.mock("@/features/dashboard/components/dashboard-shell", () => ({
  DashboardShell: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="dashboard-shell">{children}</div>
  ),
}));

describe("DashboardLayout route protection", () => {
  beforeEach(() => {
    authState.isAuthenticated = false;
    authState.isLoading = false;
    replaceMock.mockReset();
  });

  it("replaces an unauthenticated dashboard route with the login landing page", async () => {
    render(
      <DashboardLayout>
        <div>Private content</div>
      </DashboardLayout>,
    );

    expect(screen.queryByText("Private content")).not.toBeInTheDocument();
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/"));
  });

  it("waits for authentication initialization before redirecting", () => {
    authState.isLoading = true;

    render(
      <DashboardLayout>
        <div>Private content</div>
      </DashboardLayout>,
    );

    expect(screen.getByText("Loading workspace...")).toBeVisible();
    expect(screen.queryByText("Private content")).not.toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("renders protected content only for an authenticated session", () => {
    authState.isAuthenticated = true;

    render(
      <DashboardLayout>
        <div>Private content</div>
      </DashboardLayout>,
    );

    expect(screen.getByText("Private content")).toBeVisible();
    expect(replaceMock).not.toHaveBeenCalled();
  });
});
