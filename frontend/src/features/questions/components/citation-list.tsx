import { FileText } from "lucide-react";
import type { Citation } from "../questions-api-types";
import styles from "./citation-list.module.css";

export function CitationList({
  citations,
}: {
  citations: readonly Citation[];
}) {
  if (!citations.length) {
    return (
      <p className={styles.noCitations}>
        No citations were returned for this answer.
      </p>
    );
  }

  return (
    <ol aria-label="Citations" className={styles.citationList}>
      {citations.map((citation) => (
        <li
          className={styles.citationItem}
          key={`${citation.chunk_id}-${citation.rank}`}
        >
          <span className={styles.citationRank}>{citation.rank}</span>
          <div className={styles.citationBody}>
            <div className={styles.citationHeader}>
              <FileText aria-hidden="true" />
              <strong>{citation.document_filename}</strong>
              <span className={styles.citationMetadata}>
                <span>Chunk {citation.chunk_index.toLocaleString()}</span>
                <span aria-hidden="true">·</span>
                <span>
                  Cosine distance{" "}
                  {citation.distance.toLocaleString(undefined, {
                    maximumFractionDigits: 3,
                    minimumFractionDigits: 3,
                  })}
                </span>
              </span>
            </div>
            <blockquote>{citation.excerpt}</blockquote>
          </div>
        </li>
      ))}
    </ol>
  );
}
