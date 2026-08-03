import { forwardRef } from "react";
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
      className={styles.questionCard}
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
    </section>
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
