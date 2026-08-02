import type { FormEvent } from "react";
import { CircleAlert, Loader2, Send } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { getApiErrorMessage } from "@/lib/api";
import { CollectionButton } from "../collection-button";
import styles from "./ask-collection-page.module.css";

export const QUESTION_MAX_LENGTH = 4_000;

export function CollectionQuestionForm({
  inputError,
  isPending,
  onChange,
  onSubmit,
  question,
  requestError,
}: {
  inputError?: string;
  isPending: boolean;
  onChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  question: string;
  requestError?: unknown;
}) {
  return (
    <form onSubmit={onSubmit}>
      <label htmlFor="collection-question">Question</label>
      <Textarea
        aria-describedby="collection-question-help"
        aria-invalid={Boolean(inputError)}
        disabled={isPending}
        id="collection-question"
        maxLength={QUESTION_MAX_LENGTH}
        onChange={(event) => onChange(event.target.value)}
        placeholder="What are the main findings across these documents?"
        value={question}
      />
      <div className={styles.formFooter}>
        <p className={inputError ? styles.inputError : undefined} id="collection-question-help">
          {inputError ?? `${question.length.toLocaleString()} / ${QUESTION_MAX_LENGTH.toLocaleString()}`}
        </p>
        <CollectionButton disabled={isPending} type="submit">
          {isPending ? (
            <>
              <Loader2 aria-hidden="true" /> Answering…
            </>
          ) : (
            <>
              <Send aria-hidden="true" /> Ask question
            </>
          )}
        </CollectionButton>
      </div>
      {requestError ? (
        <div className={styles.inlineError} role="alert">
          <CircleAlert aria-hidden="true" />
          <p>
            {getApiErrorMessage(
              requestError,
              "The question could not be answered. Try again.",
            )}
          </p>
        </div>
      ) : null}
    </form>
  );
}
