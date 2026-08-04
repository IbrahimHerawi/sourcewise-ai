"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { CircleAlert, Loader2, MessageCircleQuestion } from "lucide-react";
import { useRouter } from "next/navigation";
import { CollectionButton } from "@/features/collections/components/collection-button";
import { DashboardPagination } from "@/features/dashboard/components/dashboard-pagination";
import {
  DeleteQuestionHistoryDialog,
  QuestionHistoryDetailsDialog,
} from "./question-history-dialogs";
import { DashboardPage } from "@/features/dashboard/components/dashboard-page";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";
import { useQuestionHistory } from "../hooks/use-question-history";
import { getQuestionHistoryErrorContent } from "../question-error-utils";
import type { QuestionHistoryItem } from "../questions-api-types";
import { QuestionHistoryList } from "./question-history-list";
import styles from "./question-history.module.css";

const PAGE_SIZE = 20;

type HistoryDialogState =
  | { item: QuestionHistoryItem; type: "delete" | "details" }
  | null;

export function QuestionHistoryScreen({
  initialPage = 1,
}: {
  initialPage?: number;
}) {
  const router = useRouter();
  const { logout } = useAuth();
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [dialog, setDialog] = useState<HistoryDialogState>(null);
  const request = useQuestionHistory(
    PAGE_SIZE,
    (currentPage - 1) * PAGE_SIZE,
  );

  useEffect(() => {
    if (
      request.status === "error" &&
      request.error instanceof ApiError &&
      request.error.status === 401
    ) {
      logout();
    }
  }, [logout, request.error, request.status]);

  const changePage = useCallback(
    (page: number) => {
      const safePage = Math.max(1, page);
      setCurrentPage(safePage);
      router.replace(
        safePage === 1
          ? "/dashboard/history"
          : `/dashboard/history?page=${safePage}`,
        { scroll: false },
      );
    },
    [router],
  );

  useEffect(() => {
    if (request.status !== "success" || request.data.total === 0) return;
    const lastPage = Math.ceil(request.data.total / request.data.limit);
    if (currentPage > lastPage) changePage(lastPage);
  }, [changePage, currentPage, request.data, request.status]);

  if (request.status === "loading") {
    return (
      <DashboardPage>
        <div
          aria-busy="true"
          aria-live="polite"
          className={styles.loadingState}
          role="status"
        >
          <Loader2 aria-hidden="true" />
          <span>Loading question history…</span>
        </div>
      </DashboardPage>
    );
  }

  if (request.status === "error") {
    const error = getQuestionHistoryErrorContent(request.error);
    return (
      <DashboardPage>
        <section
          aria-labelledby="question-history-error-title"
          className={styles.messageState}
          role="alert"
        >
          <CircleAlert aria-hidden="true" />
          <h2 id="question-history-error-title">{error.title}</h2>
          <p>{error.description}</p>
          {request.error instanceof ApiError &&
          (request.error.status === 401 || request.error.status === 403) ? null : (
            <CollectionButton
              onClick={() => void request.refetch().catch(() => undefined)}
            >
              Try again
            </CollectionButton>
          )}
        </section>
      </DashboardPage>
    );
  }

  const pageCount = Math.max(1, Math.ceil(request.data.total / request.data.limit));

  return (
    <DashboardPage>
      {request.data.items.length === 0 ? (
        <section
          aria-labelledby="question-history-empty-title"
          className={styles.messageState}
        >
          <MessageCircleQuestion aria-hidden="true" />
          <h2 id="question-history-empty-title">No question history</h2>
          <p>Ask a question to create your first saved answer.</p>
          <CollectionButton asChild>
            <Link href="/dashboard/ask-question">Ask a question</Link>
          </CollectionButton>
        </section>
      ) : (
        <section
          aria-label="Question history"
          className={styles.historyContent}
        >
          <QuestionHistoryList
            items={request.data.items}
            onDelete={(item) => setDialog({ item, type: "delete" })}
            onViewDetails={(item) => setDialog({ item, type: "details" })}
          />
          <DashboardPagination
            ariaLabel="Question history pagination"
            currentPage={currentPage}
            onPageChange={changePage}
            pageCount={pageCount}
            pageSize={PAGE_SIZE}
            total={request.data.total}
          />
        </section>
      )}

      {dialog?.type === "details" ? (
        <QuestionHistoryDetailsDialog
          onClose={() => setDialog(null)}
          questionId={dialog.item.question_id}
        />
      ) : null}
      {dialog?.type === "delete" ? (
        <DeleteQuestionHistoryDialog
          item={dialog.item}
          onClose={() => setDialog(null)}
          onDeleted={() => {
            setDialog(null);
            if (currentPage > 1 && request.data.items.length === 1) {
              changePage(currentPage - 1);
            } else {
              void request.refetch().catch(() => undefined);
            }
          }}
        />
      ) : null}
    </DashboardPage>
  );
}
