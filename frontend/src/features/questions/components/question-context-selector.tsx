import type { DocumentCollection } from "@/features/documents/types";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import styles from "./ask-question.module.css";

const ALL_DOCUMENTS_VALUE = "all-documents";

export function QuestionContextSelector({
  collections,
  disabled,
  onChange,
  selectedCollectionId,
}: {
  collections: readonly DocumentCollection[];
  disabled: boolean;
  onChange: (collectionId: string | null) => void;
  selectedCollectionId: string | null;
}) {
  return (
    <div className={styles.contextField}>
      <label htmlFor="question-context">Collection</label>
      <Select
        disabled={disabled}
        onValueChange={(value) =>
          onChange(value === ALL_DOCUMENTS_VALUE ? null : value)
        }
        value={selectedCollectionId ?? ALL_DOCUMENTS_VALUE}
      >
        <SelectTrigger className={styles.contextTrigger} id="question-context">
          <SelectValue />
        </SelectTrigger>
        <SelectContent className={styles.contextMenu}>
          <SelectItem value={ALL_DOCUMENTS_VALUE}>All documents</SelectItem>
          {collections.map((collection) => (
            <SelectItem key={collection.id} value={collection.id}>
              {collection.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
