import type {
  CollectionDetail,
  CollectionDetailTab,
  CollectionDetailViewState,
  CollectionDocument,
  CollectionHistoryItem,
  ResolvedCollectionDetailState,
} from "@/features/collections/collection-detail-types";
import { mockCollections } from "@/features/collections/mock-collections";

export type CollectionDetailPreview =
  | "documents"
  | "history"
  | "empty"
  | "no-ready-documents"
  | "no-question-history"
  | "loading"
  | "not-found"
  | "server-error";

const readyDocuments: readonly CollectionDocument[] = [
  { id: "market-signals", name: "Market Signals Q3.pdf", metadata: "28 pages · Updated 8 min ago", status: "ready" },
  { id: "policy-landscape", name: "Policy Landscape.pdf", metadata: "16 pages · Updated yesterday", status: "ready" },
  { id: "customer-discovery-notes", name: "Customer Discovery Notes.md", metadata: "42 pages · Updated 18 Jul 2026", status: "ready" },
  { id: "pricing-research", name: "Pricing Research.xlsx", metadata: "9 pages · Updated 16 Jul 2026", status: "ready" },
  { id: "investor-briefing", name: "Investor Briefing.pdf", metadata: "34 pages · Updated 14 Jul 2026", status: "ready" },
  { id: "regulatory-watch", name: "Regulatory Watch.pdf", metadata: "21 pages · Updated 12 Jul 2026", status: "ready" },
];

const processingDocuments: readonly CollectionDocument[] = [
  { id: "weekly-policy-digest", name: "Weekly Policy Digest.pdf", metadata: "Processing · 64%", progress: 64, status: "processing" },
  { id: "regulatory-briefing", name: "Regulatory Briefing.pdf", metadata: "Processing · 22%", progress: 22, status: "processing" },
  { id: "sector-guidance-notes", name: "Sector Guidance Notes.pdf", metadata: "Queued for processing", status: "pending" },
];

const historyItems: readonly CollectionHistoryItem[] = [
  {
    id: "policy-changes",
    question: "What changed in the policy landscape this quarter?",
    answer: "The collection points to three material changes: tighter disclosure rules, revised sector guidance, and a shorter compliance window. The policy brief and regulatory watch provide the strongest support.",
    citationCount: 4,
    askedAt: "Asked 8 min ago",
  },
  {
    id: "market-signals",
    question: "Which market signals should shape Q3 planning?",
    answer: "Demand is steady in enterprise accounts while mid-market conversion has softened. Pricing research suggests protecting the core offer and testing a narrower entry tier.",
    citationCount: 5,
    askedAt: "Asked yesterday",
  },
  {
    id: "discovery-disagreement",
    question: "Where do the discovery notes disagree with the investor briefing?",
    answer: "Discovery interviews emphasize implementation friction; the investor briefing frames adoption as primarily budget constrained. Both agree that onboarding speed is the clearest near-term lever.",
    citationCount: 3,
    askedAt: "Asked 18 Jul 2026",
  },
];

function collectionIdentity(collectionId: string) {
  return mockCollections.find((collection) => collection.id === collectionId);
}

function populatedCollection(collectionId: string): CollectionDetail | undefined {
  const identity = collectionIdentity(collectionId);
  if (!identity) return undefined;

  return {
    ...identity,
    documentTotal: 223,
    documents: readyDocuments,
    history: historyItems,
    questionTotal: 47,
    readyDocumentCount: 223,
  };
}

function previewCollection(
  collectionId: string,
  preview: CollectionDetailPreview,
): CollectionDetail | undefined {
  const base = populatedCollection(collectionId);
  if (!base) return undefined;

  if (preview === "empty") {
    return { ...base, documentTotal: 0, documents: [], history: [], questionTotal: 0, readyDocumentCount: 0 };
  }

  if (preview === "no-ready-documents") {
    return {
      ...base,
      name: "Policy Monitoring",
      documentTotal: 3,
      documents: processingDocuments,
      history: [],
      questionTotal: 0,
      readyDocumentCount: 0,
    };
  }

  if (preview === "no-question-history") {
    return {
      ...base,
      name: "Customer Evidence",
      documentTotal: 6,
      questionTotal: 0,
      history: [],
      readyDocumentCount: 6,
    };
  }

  return base;
}

export function createCollectionDetailState(
  collectionId: string,
  preview: CollectionDetailPreview,
): CollectionDetailViewState {
  if (preview === "loading") return { status: "loading" };
  if (preview === "server-error") return { status: "server-error" };
  if (preview === "not-found") return { status: "not-found" };

  const collection = previewCollection(collectionId, preview);
  if (!collection) return { status: "not-found" };

  return { status: preview, collection } as ResolvedCollectionDetailState;
}

export function createTabState(
  collection: CollectionDetail,
  tab: CollectionDetailTab,
): ResolvedCollectionDetailState {
  if (tab === "history") {
    return collection.questionTotal === 0
      ? { status: "no-question-history", collection }
      : { status: "history", collection };
  }

  if (collection.documentTotal === 0) return { status: "empty", collection };
  if (collection.readyDocumentCount === 0) {
    return { status: "no-ready-documents", collection };
  }
  return { status: "documents", collection };
}

export function parseCollectionDetailPreview(
  value: unknown,
  tab: CollectionDetailTab,
): CollectionDetailPreview {
  if (
    value === "documents" ||
    value === "history" ||
    value === "empty" ||
    value === "no-ready-documents" ||
    value === "no-question-history" ||
    value === "loading" ||
    value === "not-found" ||
    value === "server-error"
  ) {
    return value;
  }
  return tab;
}

export function parseCollectionDetailTab(value: unknown): CollectionDetailTab {
  return value === "history" ? "history" : "documents";
}
