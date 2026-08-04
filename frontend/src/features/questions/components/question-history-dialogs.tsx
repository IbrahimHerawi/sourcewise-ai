"use client";

import { useCallback, useRef } from "react";
import { CircleAlert, Loader2 } from "lucide-react";
import { CollectionButton } from "@/features/collections/components/collection-button";
import {
  CollectionDialog,
  CollectionDialogCancel,
  CollectionDialogFooter,
} from "@/features/collections/components/dialogs/collection-dialog";
import { useApiMutation, useApiRequest } from "@/hooks/use-api-request";
import { formatDateTime } from "@/lib/formatters";
import { getQuestionHistoryErrorContent } from "../question-error-utils";
import {
  deleteQuestionHistoryItemApi,
  getQuestionHistoryItemApi,
} from "../questions-api";
import type { QuestionHistoryItem } from "../questions-api-types";
import { CitationList } from "./citation-list";
import styles from "./question-history-dialogs.module.css";

export function QuestionHistoryDetailsDialog({
  questionId,
  onClose,
}: {
  questionId: string;
  onClose: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const request = useCallback(
    (signal: AbortSignal) =>
      getQuestionHistoryItemApi(questionId, signal),
    [questionId],
  );
  const state = useApiRequest(request);

  return (
    <CollectionDialog
      description="The saved question, answer, and citation snapshots."
      initialFocusRef={closeRef}
      onClose={onClose}
      title="Question details"
    >
      {state.status === "loading" ? (
        <div
          aria-busy="true"
          aria-live="polite"
          className={styles.loading}
          role="status"
        >
          <Loader2 aria-hidden="true" />
          <span>Loading question details…</span>
        </div>
      ) : state.status === "error" ? (
        <div className={styles.error} role="alert">
          <CircleAlert aria-hidden="true" />
          <p>{getQuestionHistoryErrorContent(state.error).description}</p>
          <CollectionButton
            onClick={() => void state.refetch().catch(() => undefined)}
          >
            Try again
          </CollectionButton>
        </div>
      ) : (
        <QuestionHistoryDetails item={state.data} />
      )}
      <CollectionDialogFooter>
        <CollectionDialogCancel ref={closeRef}>Close</CollectionDialogCancel>
      </CollectionDialogFooter>
    </CollectionDialog>
  );
}

function QuestionHistoryDetails({ item }: { item: QuestionHistoryItem }) {
  return (
    <div className={styles.details}>
      <div>
        <span className={styles.label}>Question</span>
        <h3>{item.question}</h3>
      </div>
      <div>
        <span className={styles.label}>Answer</span>
        <p className={styles.fullAnswer}>{item.answer}</p>
      </div>
      <div className={styles.answerMetadata}>
        <time dateTime={item.created_at}>{formatDateTime(item.created_at)}</time>
        {item.provider && item.model ? (
          <span>
            {item.provider} · {item.model}
          </span>
        ) : null}
      </div>
      <section aria-labelledby={`history-citations-${item.question_id}`}>
        <h4 id={`history-citations-${item.question_id}`}>Citations</h4>
        <CitationList citations={item.citations} />
      </section>
    </div>
  );
}

export function DeleteQuestionHistoryDialog({
  item,
  onClose,
  onDeleted,
}: {
  item: QuestionHistoryItem;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const mutation = useApiMutation((questionId: string, signal) =>
    deleteQuestionHistoryItemApi(questionId, signal),
  );

  return (
    <CollectionDialog
      description="Delete this saved question, its answer, and citation snapshots permanently?"
      descriptionVariant="warning"
      initialFocusRef={cancelRef}
      onClose={onClose}
      role="alertdialog"
      title="Delete history item?"
    >
      <p className={styles.confirmationSubject}>{item.question}</p>
      <CollectionDialogFooter>
        <CollectionDialogCancel disabled={mutation.isPending} ref={cancelRef} />
        <CollectionButton
          disabled={mutation.isPending}
          onClick={() =>
            void mutation
              .mutate(item.question_id)
              .then(onDeleted)
              .catch(() => undefined)
          }
          tone="solid-danger"
          type="button"
        >
          {mutation.isPending ? "Deleting…" : "Delete history item"}
        </CollectionButton>
      </CollectionDialogFooter>
      {mutation.error ? (
        <p className={styles.mutationError} role="alert">
          {getQuestionHistoryErrorContent(mutation.error).description}
        </p>
      ) : null}
    </CollectionDialog>
  );
}
