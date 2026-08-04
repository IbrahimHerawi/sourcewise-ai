import type { FormEvent, ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import type { DocumentCollection } from "@/features/documents/types";
import { CollectionButton } from "@/features/collections/components/collection-button";
import {
  normalizeQuestion,
  QUESTION_MAX_LENGTH,
} from "../question-validation";
import { QuestionContextSelector } from "./question-context-selector";
import styles from "./ask-question.module.css";

export function AskQuestionForm({
  collections,
  contextFeedback,
  contextSelectionDisabled,
  inputError,
  isPending,
  isSubmitDisabled,
  onContextChange,
  onQuestionBlur,
  onQuestionChange,
  onSubmit,
  question,
  selectedCollectionId,
}: {
  collections: readonly DocumentCollection[];
  contextFeedback?: ReactNode;
  contextSelectionDisabled: boolean;
  inputError?: string;
  isPending: boolean;
  isSubmitDisabled: boolean;
  onContextChange: (collectionId: string | null) => void;
  onQuestionBlur: () => void;
  onQuestionChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  question: string;
  selectedCollectionId: string | null;
}) {
  const characterCount = normalizeQuestion(question).length;
  const describedBy = [
    "question-character-count",
    inputError ? "question-input-error" : null,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <section aria-label="Ask a question" className={styles.questionCard}>
      <form onSubmit={onSubmit}>
        <div className={styles.questionField}>
          <label className="sr-only" htmlFor="question-input">
            Ask your question
          </label>
          <div className={styles.textareaShell}>
            <Textarea
              aria-describedby={describedBy}
              aria-invalid={Boolean(inputError)}
              aria-required="true"
              disabled={isPending}
              id="question-input"
              onBlur={onQuestionBlur}
              onChange={(event) => onQuestionChange(event.target.value)}
              placeholder="Ask about a fact, decision, or theme in your documents…"
              value={question}
            />
            <span
              className={`${styles.characterCount} ${
                characterCount > QUESTION_MAX_LENGTH
                  ? styles.characterCountInvalid
                  : ""
              }`}
              id="question-character-count"
            >
              {characterCount.toLocaleString()} /{" "}
              {QUESTION_MAX_LENGTH.toLocaleString()} characters
            </span>
          </div>
          {inputError ? (
            <p
              className={styles.fieldError}
              id="question-input-error"
              role="alert"
            >
              {inputError}
            </p>
          ) : null}
        </div>

        <div className={styles.contextActions}>
          <QuestionContextSelector
            collections={collections}
            disabled={isPending || contextSelectionDisabled}
            onChange={onContextChange}
            selectedCollectionId={selectedCollectionId}
          />

          <div className={styles.formActions}>
            <CollectionButton disabled={isSubmitDisabled} type="submit">
              {isPending ? (
                <>
                  <Loader2
                    aria-hidden="true"
                    className={styles.spinner}
                  />
                  Answering…
                </>
              ) : (
                "Ask question"
              )}
            </CollectionButton>
          </div>
        </div>

        {contextFeedback}
      </form>
    </section>
  );
}
