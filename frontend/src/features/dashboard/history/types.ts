export type HistoryEntry = {
  id: string;
  documentId: string;
  question: string;
  answer: string;
  createdAt: string;
  model: string;
  provider: string;
  sourceCount: number;
  sources: readonly string[];
  isExpandable?: boolean;
};

export type HistoryDocumentFilter = {
  id: string;
  label: string;
};
