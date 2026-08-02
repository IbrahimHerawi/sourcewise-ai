"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import { CircleAlert, FolderOpen, Loader2 } from "lucide-react";
import { DashboardPage } from "@/features/dashboard/components/dashboard-page";
import { useDashboardHeader } from "@/features/dashboard/components/dashboard-header-context";
import { askCollection } from "@/features/collections/collections-api";
import type { QuestionAnswer } from "@/features/collections/collections-api-types";
import { useCollectionRecord } from "@/features/collections/hooks/use-collections-api";
import { useApiMutation } from "@/hooks/use-api-request";
import { useAuth } from "@/hooks/use-auth";
import { ApiError, getApiErrorMessage } from "@/lib/api";
import { CollectionButton } from "../collection-button";
import { CollectionDetailSkeleton } from "../detail/collection-detail-states";
import { CollectionAnswerPanel } from "./collection-answer-panel";
import {
  CollectionQuestionForm,
  QUESTION_MAX_LENGTH,
} from "./collection-question-form";
import styles from "./ask-collection-page.module.css";

export function AskCollectionPage({ collectionId }: { collectionId?: string }) {
  useDashboardHeader(useMemo(() => ({ title: "Ask Question" }), []));

  if (!collectionId) {
    return (
      <DashboardPage>
        <section className={styles.chooseState}>
          <FolderOpen aria-hidden="true" />
          <h2>Choose a collection first</h2>
          <p>Open a collection and use “Ask this collection” to ask a grounded question.</p>
          <CollectionButton asChild>
            <Link href="/dashboard/collections">Browse Collections</Link>
          </CollectionButton>
        </section>
      </DashboardPage>
    );
  }

  return <ScopedAskCollection collectionId={collectionId} />;
}

function ScopedAskCollection({ collectionId }: { collectionId: string }) {
  const { logout } = useAuth();
  const collectionRequest = useCollectionRecord(collectionId);
  const [question, setQuestion] = useState("");
  const [inputError, setInputError] = useState<string>();
  const [answer, setAnswer] = useState<QuestionAnswer>();
  const mutation = useApiMutation((value: string, signal) =>
    askCollection(collectionId, value, signal),
  );

  useEffect(() => {
    const error = collectionRequest.status === "error" ? collectionRequest.error : mutation.error;
    if (error instanceof ApiError && error.status === 401) logout();
  }, [collectionRequest, logout, mutation.error]);

  const collection = collectionRequest.status === "success" ? collectionRequest.data : undefined;
  useDashboardHeader(
    useMemo(
      () => ({ title: collection ? `Ask ${collection.name}` : "Ask Question" }),
      [collection],
    ),
  );

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = question.trim();
    if (!normalized) {
      setInputError("Enter a question.");
      return;
    }
    if (normalized.length > QUESTION_MAX_LENGTH) {
      setInputError(`Question must be ${QUESTION_MAX_LENGTH.toLocaleString()} characters or fewer.`);
      return;
    }
    setAnswer(undefined);
    void mutation.mutate(normalized).then(setAnswer).catch(() => undefined);
  };

  if (collectionRequest.status === "loading") {
    return (
      <DashboardPage>
        <CollectionDetailSkeleton />
      </DashboardPage>
    );
  }

  if (collectionRequest.status === "error") {
    const notFound = collectionRequest.error instanceof ApiError && collectionRequest.error.status === 404;
    return (
      <DashboardPage>
        <section className={styles.requestError} role="alert">
          <CircleAlert aria-hidden="true" />
          <h2>{notFound ? "Collection not found" : "Collection couldn’t load"}</h2>
          <p>
            {notFound
              ? "The collection may have been deleted or you may no longer have access."
              : getApiErrorMessage(collectionRequest.error, "Try again in a moment.")}
          </p>
          <CollectionButton
            onClick={() => void collectionRequest.refetch().catch(() => undefined)}
          >
            Try again
          </CollectionButton>
        </section>
      </DashboardPage>
    );
  }

  return (
    <DashboardPage>
      <div className={styles.askLayout}>
        <section className={styles.questionPanel} aria-labelledby="ask-collection-title">
          <div className={styles.intro}>
            <h2 id="ask-collection-title">Ask {collectionRequest.data.name}</h2>
            <p>
              Ask one independent question. SourceWise will use currently available document
              context and return a grounded answer when supporting excerpts are found.
            </p>
          </div>
          <CollectionQuestionForm
            inputError={inputError}
            isPending={mutation.isPending}
            onChange={(value) => {
              setQuestion(value);
              setInputError(undefined);
              mutation.reset();
            }}
            onSubmit={submit}
            question={question}
            requestError={mutation.error}
          />
        </section>

        {mutation.isPending ? (
          <section aria-busy="true" className={styles.answerLoading}>
            <Loader2 aria-hidden="true" />
            <div>
              <strong>Reviewing available context</strong>
              <p>Your answer will appear here when the request completes.</p>
            </div>
          </section>
        ) : null}

        {answer ? <CollectionAnswerPanel answer={answer} /> : null}
      </div>
    </DashboardPage>
  );
}
