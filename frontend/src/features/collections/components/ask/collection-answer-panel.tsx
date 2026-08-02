import type { QuestionAnswer } from "@/features/collections/collections-api-types";
import { formatDateTime } from "@/features/collections/collection-formatters";
import { CitationList } from "../detail/citation-list";
import styles from "./ask-collection-page.module.css";

export function CollectionAnswerPanel({ answer }: { answer: QuestionAnswer }) {
  return (
    <section className={styles.answerPanel} aria-labelledby="collection-answer-title">
      <div className={styles.answerHeader}>
        <h2 id="collection-answer-title">Answer</h2>
        <time dateTime={answer.created_at}>{formatDateTime(answer.created_at)}</time>
      </div>
      <p className={styles.answerText}>{answer.answer}</p>
      {!answer.citations.length ? (
        <p className={styles.contextNote}>
          No supporting excerpts were found in the collection’s currently ready documents.
        </p>
      ) : null}
      <div className={styles.citationsSection}>
        <h3>Citations</h3>
        <CitationList citations={answer.citations} />
      </div>
    </section>
  );
}
