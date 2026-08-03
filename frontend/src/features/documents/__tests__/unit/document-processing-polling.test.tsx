import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useDocumentProcessingPolling } from "@/features/documents/hooks/use-document-processing-polling";
import type {
  DocumentStatus,
  PaginatedDocuments,
} from "@/features/documents/types";
import { readyDocument } from "../test-data";

function page(status: DocumentStatus): PaginatedDocuments {
  return {
    items: [{ ...readyDocument, status }],
    limit: 20,
    offset: 0,
    total: 1,
  };
}

function PollingHarness({
  isRefreshing = false,
  refetch,
  status,
}: {
  isRefreshing?: boolean;
  refetch: (
    options?: { silent?: boolean },
  ) => Promise<PaginatedDocuments>;
  status: DocumentStatus;
}) {
  useDocumentProcessingPolling({
    data: page(status),
    isRefreshing,
    refetch,
  });
  return null;
}

describe("document processing polling", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it.each(["PENDING", "PROCESSING"] as const)(
    "starts for %s and uses a silent refresh",
    async (status) => {
      vi.useFakeTimers();
      const refetch = vi.fn().mockResolvedValue(page("READY"));
      render(<PollingHarness refetch={refetch} status={status} />);

      await vi.advanceTimersByTimeAsync(2_500);

      expect(refetch).toHaveBeenCalledTimes(1);
      expect(refetch).toHaveBeenCalledWith({ silent: true });
    },
  );

  it.each(["READY", "FAILED", "UNKNOWN"] as const)(
    "does not poll terminal status %s",
    async (status) => {
      vi.useFakeTimers();
      const refetch = vi.fn().mockResolvedValue(page(status));
      render(<PollingHarness refetch={refetch} status={status} />);

      await vi.advanceTimersByTimeAsync(10_000);

      expect(refetch).not.toHaveBeenCalled();
    },
  );

  it("stops after completion and while a refresh is in flight", async () => {
    vi.useFakeTimers();
    const refetch = vi.fn().mockResolvedValue(page("READY"));
    const view = render(
      <PollingHarness refetch={refetch} status="PENDING" />,
    );

    await vi.advanceTimersByTimeAsync(2_500);
    view.rerender(
      <PollingHarness
        isRefreshing
        refetch={refetch}
        status="PENDING"
      />,
    );
    await vi.advanceTimersByTimeAsync(10_000);
    expect(refetch).toHaveBeenCalledTimes(1);

    view.rerender(<PollingHarness refetch={refetch} status="READY" />);
    await vi.advanceTimersByTimeAsync(10_000);
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("clears pending polling on unmount", async () => {
    vi.useFakeTimers();
    const refetch = vi.fn().mockResolvedValue(page("READY"));
    const view = render(
      <PollingHarness refetch={refetch} status="PROCESSING" />,
    );

    view.unmount();
    await vi.advanceTimersByTimeAsync(10_000);

    expect(refetch).not.toHaveBeenCalled();
  });
});
