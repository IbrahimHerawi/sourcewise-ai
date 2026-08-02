import { useState } from "react";
import type {
  CollectionDetailTab,
  ResolvedCollectionDetailState,
} from "@/features/collections/collection-detail-types";
import { formatResultRange } from "@/features/collections/collection-detail-utils";
import { CollectionDetailTabs } from "./collection-detail-tabs";
import { CollectionDocumentList } from "./collection-document-list";
import { CollectionHistoryList } from "./collection-history-list";
import { CollectionPagination } from "./collection-pagination";
import { CollectionSectionHeader } from "./collection-section-header";
import { CollectionSummary } from "./collection-summary";
import {
  CollectionDetailEmptyState,
  NoQuestionHistoryState,
  NoReadyDocumentsWarning,
} from "./collection-detail-states";
import styles from "./collection-detail.module.css";

type CollectionDetailContentProps = {
  onAsk: () => void;
  onDelete: (opener: HTMLButtonElement) => void;
  onEdit: (opener: HTMLButtonElement) => void;
  onTabChange: (tab: CollectionDetailTab) => void;
  onUpload: () => void;
  state: ResolvedCollectionDetailState;
};

const PAGE_SIZE = 20;

export function CollectionDetailContent({
  onAsk,
  onDelete,
  onEdit,
  onTabChange,
  onUpload,
  state,
}: CollectionDetailContentProps) {
  const [documentPage, setDocumentPage] = useState(2);
  const [historyPage, setHistoryPage] = useState(2);
  const [showWarning, setShowWarning] = useState(true);
  const { collection } = state;
  const activeTab: CollectionDetailTab =
    state.status === "history" || state.status === "no-question-history"
      ? "history"
      : "documents";

  let content;
  if (state.status === "history") {
    const pageCount = Math.ceil(collection.questionTotal / PAGE_SIZE);
    content = (
      <>
        <CollectionSectionHeader
          countLabel={`Showing ${formatResultRange(historyPage, PAGE_SIZE, collection.questionTotal)} of ${collection.questionTotal}`}
          title="Question history"
        />
        <CollectionHistoryList items={collection.history} />
        <CollectionPagination
          currentPage={historyPage}
          onPageChange={setHistoryPage}
          pageCount={pageCount}
        />
      </>
    );
  } else if (state.status === "no-question-history") {
    content = (
      <>
        <CollectionSectionHeader countLabel="0 questions" title="Question history" />
        <NoQuestionHistoryState
          canAsk={collection.readyDocumentCount > 0}
          onAsk={onAsk}
        />
      </>
    );
  } else if (state.status === "empty") {
    content = (
      <>
        <CollectionSectionHeader countLabel="0 documents" title="Documents" />
        <CollectionDetailEmptyState onUpload={onUpload} />
      </>
    );
  } else if (state.status === "no-ready-documents") {
    content = (
      <>
        <CollectionSectionHeader
          countLabel={`${collection.documentTotal} documents · ${collection.readyDocumentCount} ready`}
          title="Documents"
        />
        {showWarning ? (
          <NoReadyDocumentsWarning onDismiss={() => setShowWarning(false)} />
        ) : null}
        <CollectionDocumentList documents={collection.documents} />
      </>
    );
  } else {
    const pageCount = Math.ceil(collection.documentTotal / PAGE_SIZE);
    content = (
      <>
        <CollectionSectionHeader
          countLabel={`Showing ${formatResultRange(documentPage, PAGE_SIZE, collection.documentTotal)} of ${collection.documentTotal}`}
          title="Documents"
        />
        <CollectionDocumentList documents={collection.documents} />
        <CollectionPagination
          currentPage={documentPage}
          onPageChange={setDocumentPage}
          pageCount={pageCount}
        />
      </>
    );
  }

  return (
    <>
      <CollectionSummary
        collection={collection}
        onAsk={onAsk}
        onDelete={onDelete}
        onEdit={onEdit}
      />
      <CollectionDetailTabs
        activeTab={activeTab}
        collection={collection}
        onTabChange={onTabChange}
      >
        <div className={styles.tabPanel}>{content}</div>
      </CollectionDetailTabs>
    </>
  );
}
