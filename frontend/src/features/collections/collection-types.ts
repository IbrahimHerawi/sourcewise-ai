export type Collection = {
  id: string;
  name: string;
  description?: string;
  created: string;
  updated: string;
};

export type CollectionsViewState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "not-found" }
  | { status: "success"; collections: Collection[] };
