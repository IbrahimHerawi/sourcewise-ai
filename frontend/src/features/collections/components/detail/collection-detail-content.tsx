import type {
  CollectionDetailTab,
} from "@/features/collections/collection-detail-types";
import type {
  CollectionDocument,
  PaginatedResponse,
  QuestionHistoryItem,
} from "@/features/collections/collections-api-types";
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
} from "./collection-detail-states";
import styles from "./collection-detail.module.css";

type CollectionDetailContentProps = {
  onAsk: () => void;
  documents: PaginatedResponse<CollectionDocument>;
  documentPage: number;
  history: PaginatedResponse<QuestionHistoryItem>;
  historyPage: number;
  onDelete: (opener: HTMLButtonElement) => void;
  onDeleteDocument: (document: CollectionDocument) => void;
  onDeleteHistory: (item: QuestionHistoryItem) => void;
  onEdit: (opener: HTMLButtonElement) => void;
  onDocumentPageChange: (page: number) => void;
  onHistoryPageChange: (page: number) => void;
  onTabChange: (tab: CollectionDetailTab) => void;
  onUpload: () => void;
  onViewDocument: (document: CollectionDocument) => void;
  onViewHistory: (item: QuestionHistoryItem) => void;
  activeTab: CollectionDetailTab;
};

const PAGE_SIZE = 20;

export function CollectionDetailContent({
  activeTab,
  documents,
  documentPage,
  history,
  historyPage,
  onAsk,
  onDelete,
  onDeleteDocument,
  onDeleteHistory,
  onEdit,
  onDocumentPageChange,
  onHistoryPageChange,
  onTabChange,
  onUpload,
  onViewDocument,
  onViewHistory,
}: CollectionDetailContentProps) {
  let content;
  if (activeTab === "history") {
    const pageCount = Math.max(1, Math.ceil(history.total / history.limit));
    if (history.items.length === 0) {
      content = (
        <>
          <CollectionSectionHeader countLabel="0 questions" title="Question history" />
          <NoQuestionHistoryState onAsk={onAsk} />
        </>
      );
    } else {
      content = (
        <>
          <CollectionSectionHeader
            countLabel={`Showing ${formatResultRange(historyPage, PAGE_SIZE, history.total)} of ${history.total}`}
            title="Question history"
          />
          <CollectionHistoryList
            items={history.items}
            onDelete={onDeleteHistory}
            onViewDetails={onViewHistory}
          />
          {pageCount > 1 ? (
            <CollectionPagination
              currentPage={historyPage}
              onPageChange={onHistoryPageChange}
              pageCount={pageCount}
            />
          ) : null}
        </>
      );
    }
  } else if (documents.items.length === 0) {
    content = (
      <>
        <CollectionSectionHeader countLabel="0 documents" title="Documents" />
        <CollectionDetailEmptyState onUpload={onUpload} />
      </>
    );
  } else {
    const pageCount = Math.max(1, Math.ceil(documents.total / documents.limit));
    content = (
      <>
        <CollectionSectionHeader
          countLabel={`Showing ${formatResultRange(documentPage, PAGE_SIZE, documents.total)} of ${documents.total}`}
          title="Documents"
        />
        <CollectionDocumentList
          documents={documents.items}
          onDelete={onDeleteDocument}
          onViewDetails={onViewDocument}
        />
        {pageCount > 1 ? (
          <CollectionPagination
            currentPage={documentPage}
            onPageChange={onDocumentPageChange}
            pageCount={pageCount}
          />
        ) : null}
      </>
    );
  }

  return (
    <>
      <CollectionSummary
        documentTotal={documents.total}
        onAsk={onAsk}
        onDelete={onDelete}
        onEdit={onEdit}
        questionTotal={history.total}
      />
      <CollectionDetailTabs
        activeTab={activeTab}
        documentTotal={documents.total}
        onTabChange={onTabChange}
        questionTotal={history.total}
      >
        <div className={styles.tabPanel}>{content}</div>
      </CollectionDetailTabs>
    </>
  );
}
