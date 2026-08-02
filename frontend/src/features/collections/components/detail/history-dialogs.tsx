"use client";

import { useCallback, useRef } from "react";
import { CircleAlert, Loader2 } from "lucide-react";
import {
  deleteQuestionHistoryItem,
  getQuestionHistoryItem,
} from "@/features/collections/collections-api";
import type { QuestionHistoryItem } from "@/features/collections/collections-api-types";
import { formatDateTime } from "@/features/collections/collection-formatters";
import { useApiMutation, useApiRequest } from "@/hooks/use-api-request";
import { getApiErrorMessage } from "@/lib/api";
import { CollectionButton } from "../collection-button";
import {
  CollectionDialog,
  CollectionDialogCancel,
  CollectionDialogFooter,
} from "../dialogs/collection-dialog";
import { CitationList } from "./citation-list";
import styles from "./collection-detail.module.css";

export function HistoryDetailsDialog({
  questionId,
  onClose,
}: {
  questionId: string;
  onClose: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const request = useCallback(
    (signal: AbortSignal) => getQuestionHistoryItem(questionId, signal),
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
        <div aria-busy="true" className={styles.dialogLoading}>
          <Loader2 aria-hidden="true" />
          <span>Loading question details…</span>
        </div>
      ) : state.status === "error" ? (
        <div className={styles.dialogError} role="alert">
          <CircleAlert aria-hidden="true" />
          <p>{getApiErrorMessage(state.error, "Question details could not be loaded.")}</p>
          <CollectionButton onClick={() => void state.refetch().catch(() => undefined)}>
            Try again
          </CollectionButton>
        </div>
      ) : (
        <HistoryDetails item={state.data} />
      )}
      <CollectionDialogFooter>
        <CollectionDialogCancel ref={closeRef}>Close</CollectionDialogCancel>
      </CollectionDialogFooter>
    </CollectionDialog>
  );
}

function HistoryDetails({ item }: { item: QuestionHistoryItem }) {
  return (
    <div className={styles.historyDetailsBody}>
      <div>
        <span className={styles.detailLabel}>Question</span>
        <h3>{item.question}</h3>
      </div>
      <div>
        <span className={styles.detailLabel}>Answer</span>
        <p className={styles.fullAnswer}>{item.answer}</p>
      </div>
      <div className={styles.answerMetadata}>
        <time dateTime={item.created_at}>{formatDateTime(item.created_at)}</time>
        {item.provider && item.model ? <span>{item.provider} · {item.model}</span> : null}
      </div>
      <section aria-labelledby="history-citations-title">
        <h4 id="history-citations-title">Citations</h4>
        <CitationList citations={item.citations} />
      </section>
    </div>
  );
}

export function DeleteHistoryDialog({
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
    deleteQuestionHistoryItem(questionId, signal),
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
            void mutation.mutate(item.question_id).then(onDeleted).catch(() => undefined)
          }
          tone="solid-danger"
          type="button"
        >
          {mutation.isPending ? "Deleting…" : "Delete history item"}
        </CollectionButton>
      </CollectionDialogFooter>
      {mutation.error ? (
        <p className={styles.dialogMutationError} role="alert">
          {getApiErrorMessage(mutation.error, "The history item could not be deleted.")}
        </p>
      ) : null}
    </CollectionDialog>
  );
}
