import { forwardRef } from "react";
import Link from "next/link";
import { CircleAlert, Loader2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { CollectionButton } from "@/features/collections/components/collection-button";
import type { QuestionErrorContent } from "../question-error-utils";
import styles from "./ask-question.module.css";

export function AskQuestionSkeleton() {
  return (
    <section
      aria-busy="true"
      aria-labelledby="ask-question-loading"
      aria-live="polite"
      className={styles.questionCard}
      role="status"
    >
      <h2 className="sr-only" id="ask-question-loading">
        Loading the question form
      </h2>
      <Skeleton className={styles.skeletonTextarea} />
      <div className={styles.skeletonActions}>
        <div>
          <Skeleton className={styles.skeletonLabel} />
          <Skeleton className={styles.skeletonSelect} />
        </div>
        <Skeleton className={styles.skeletonButton} />
      </div>
      <Skeleton className={styles.skeletonSourceStatus} />
    </section>
  );
}

export function QuestionSourceState({
  documentCount,
  readyCount,
  scopeLabel,
}: {
  documentCount: number;
  readyCount: number;
  scopeLabel: string;
}) {
  if (readyCount > 0) {
    return (
      <p className={styles.sourceStatus} role="status">
        {readyCount.toLocaleString()} ready{" "}
        {readyCount === 1 ? "document" : "documents"} will be searched in{" "}
        {scopeLabel}.
      </p>
    );
  }

  return (
    <div className={styles.noReadySources} role="status">
      <div>
        <strong>
          {documentCount === 0
            ? "No documents have been uploaded"
            : `No ready documents in ${scopeLabel}`}
        </strong>
        <p>
          Questions only retrieve ready documents. You can still submit, but a
          grounded answer requires processed source material.
        </p>
      </div>
      <CollectionButton asChild tone="secondary">
        <Link href="/dashboard/documents">Open Documents</Link>
      </CollectionButton>
    </div>
  );
}

export function QuestionGeneratingState({
  scopeLabel,
}: {
  scopeLabel: string;
}) {
  return (
    <section
      aria-live="polite"
      className={styles.generatingState}
      role="status"
    >
      <span className={styles.generatingIcon}>
        <Loader2 aria-hidden="true" />
      </span>
      <div>
        <strong>Reviewing {scopeLabel}</strong>
        <p>
          SourceWise is finding relevant excerpts and preparing a grounded
          answer.
        </p>
      </div>
    </section>
  );
}

export const AskQuestionErrorState = forwardRef<
  HTMLDivElement,
  {
    content: QuestionErrorContent;
    onRetry?: () => void;
    retryLabel?: string;
  }
>(function AskQuestionErrorState(
  { content, onRetry, retryLabel = "Try again" },
  ref,
) {
  return (
    <div
      className={styles.questionError}
      ref={ref}
      role="alert"
      tabIndex={-1}
    >
      <span className={styles.errorIcon}>
        <CircleAlert aria-hidden="true" />
      </span>
      <div className={styles.errorCopy}>
        <strong>{content.title}</strong>
        <p>{content.description}</p>
      </div>
      {onRetry ? (
        <CollectionButton onClick={onRetry} tone="secondary" type="button">
          {retryLabel}
        </CollectionButton>
      ) : null}
    </div>
  );
});
