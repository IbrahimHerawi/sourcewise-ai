export type CollectionDetailTab = "documents" | "history";

export function parseCollectionDetailTab(value: unknown): CollectionDetailTab {
  return value === "history" ? "history" : "documents";
}
