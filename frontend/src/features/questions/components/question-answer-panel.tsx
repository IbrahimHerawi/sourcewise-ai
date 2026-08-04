import { useEffect, useRef } from "react";
import { BookOpenCheck } from "lucide-react";
import { formatDateTime } from "@/lib/formatters";
import { CitationList } from "./citation-list";
import type {
  AskQuestionState,
} from "../hooks/use-ask-question";
import styles from "./ask-question.module.css";

export function QuestionAnswerPanel({
  state,
}: {
  state: Extract<AskQuestionState, { status: "completed" }>;
}) {
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    panelRef.current?.focus();
  }, [state.answer.question_id]);

  return (
    <section
      aria-labelledby="question-answer-title"
      className={styles.answerCard}
      ref={panelRef}
      tabIndex={-1}
    >
      <div className={styles.answerHeader}>
        <div className={styles.answerIdentity}>
          <span className={styles.answerIcon}>
            <BookOpenCheck aria-hidden="true" />
          </span>
          <div>
            <h2 id="question-answer-title">Answer</h2>
            <p>{state.submission.scopeLabel}</p>
          </div>
        </div>
        <time dateTime={state.answer.created_at}>
          {formatDateTime(state.answer.created_at)}
        </time>
      </div>

      {state.answer.answer.trim() ? (
        <p className={styles.answerText}>{state.answer.answer}</p>
      ) : (
        <div className={styles.emptyAnswer} role="status">
          The server returned an empty answer.
        </div>
      )}

      {state.answer.citations.length > 0 ? (
        <section
          aria-labelledby="answer-citations-title"
          className={styles.citations}
        >
          <div className={styles.citationsHeader}>
            <h3 id="answer-citations-title">Supporting excerpts</h3>
            <span>
              {state.answer.citations.length.toLocaleString()}{" "}
              {state.answer.citations.length === 1 ? "citation" : "citations"}
            </span>
          </div>
          <CitationList citations={state.answer.citations} />
        </section>
      ) : (
        <div className={styles.noCitations} role="status">
          <strong>No supporting excerpts were returned</strong>
          <p>
            The available ready documents did not provide grounded support for
            this answer.
          </p>
        </div>
      )}
    </section>
  );
}
