import type { DocumentCollection } from "@/features/documents/types";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import styles from "./ask-question.module.css";

export function QuestionContextSelector({
  collections,
  disabled,
  error,
  onChange,
  selectedCollectionId,
}: {
  collections: readonly DocumentCollection[];
  disabled: boolean;
  error?: string;
  onChange: (collectionId: string | null) => void;
  selectedCollectionId: string | null;
}) {
  const selectedCollection = collections.find(
    (collection) => collection.id === selectedCollectionId,
  );
  const selectedLabel = selectedCollectionId
    ? (selectedCollection?.name ?? "Selected collection")
    : undefined;

  return (
    <div className={styles.contextField}>
      <label htmlFor="question-context">Collection</label>
      <Select
        disabled={disabled}
        onValueChange={onChange}
        value={selectedCollectionId ?? ""}
      >
        <SelectTrigger
          aria-describedby={error ? "question-context-error" : undefined}
          aria-invalid={Boolean(error)}
          aria-required="true"
          className={styles.contextTrigger}
          id="question-context"
        >
          <SelectValue placeholder="Select collection">
            {selectedLabel}
          </SelectValue>
        </SelectTrigger>
        <SelectContent className={styles.contextMenu}>
          {collections.map((collection) => (
            <SelectItem key={collection.id} value={collection.id}>
              {collection.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {error ? (
        <p
          className={styles.fieldError}
          id="question-context-error"
          role="alert"
        >
          {error}
        </p>
      ) : null}
    </div>
  );
}
