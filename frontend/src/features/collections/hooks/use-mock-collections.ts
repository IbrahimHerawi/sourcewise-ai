"use client";

import { useRef, useState } from "react";
import type { CollectionDraft } from "@/features/collections/collection-validation";
import type {
  Collection,
  CollectionsViewState,
} from "@/features/collections/collection-types";
import {
  createMockCollectionsState,
  mockCollections,
  type CollectionsPreview,
} from "@/features/collections/mock-collections";

export function useMockCollections(initialPreview: CollectionsPreview) {
  const [viewState, setViewState] = useState<CollectionsViewState>(() =>
    createMockCollectionsState(initialPreview),
  );
  const nextLocalId = useRef(0);

  const createCollection = (draft: CollectionDraft) => {
    nextLocalId.current += 1;
    const collection: Collection = {
      id: `local-collection-${nextLocalId.current}`,
      name: draft.name,
      description: draft.description || undefined,
      created: "Created just now",
      updated: "Updated just now",
    };

    setViewState((current) => ({
      status: "success",
      collections:
        current.status === "success"
          ? [collection, ...current.collections]
          : [collection],
    }));
  };

  const updateCollection = (collectionId: string, draft: CollectionDraft) => {
    setViewState((current) =>
      current.status === "success"
        ? {
            status: "success",
            collections: current.collections.map((collection) =>
              collection.id === collectionId
                ? {
                    ...collection,
                    name: draft.name,
                    description: draft.description || undefined,
                    updated: "Updated just now",
                  }
                : collection,
            ),
          }
        : current,
    );
  };

  const deleteCollection = (collectionId: string) => {
    setViewState((current) =>
      current.status === "success"
        ? {
            status: "success",
            collections: current.collections.filter(
              (collection) => collection.id !== collectionId,
            ),
          }
        : current,
    );
  };

  const restoreMockCollections = () => {
    setViewState({ status: "success", collections: [...mockCollections] });
  };

  return {
    createCollection,
    deleteCollection,
    restoreMockCollections,
    updateCollection,
    viewState,
  };
}
