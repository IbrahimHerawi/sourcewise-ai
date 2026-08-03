"use client";

import { AskQuestionScreen } from "@/features/questions/components/ask-question-screen";

/** Compatibility entry point for collection-detail callers and existing previews. */
export function AskCollectionPage({ collectionId }: { collectionId?: string }) {
  return <AskQuestionScreen initialCollectionId={collectionId} />;
}
