"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { DashboardPage } from "@/features/dashboard/components/dashboard-page";
import { useDocumentCollections } from "@/features/documents/hooks/use-documents-api";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";
import { isApiUuid } from "@/lib/api-contract";
import { AskQuestionForm } from "./ask-question-form";
import {
  AskQuestionErrorState,
  AskQuestionSkeleton,
  QuestionGeneratingState,
  QuestionSourceState,
} from "./ask-question-states";
import { QuestionAnswerPanel } from "./question-answer-panel";
import { useAskQuestion } from "../hooks/use-ask-question";
import { useQuestionSources } from "../hooks/use-question-sources";
import {
  getQuestionCollectionsError,
  getQuestionErrorContent,
  getQuestionFailureAction,
  getQuestionSourcesError,
} from "../question-error-utils";
import {
  normalizeQuestion,
  validateQuestion,
} from "../question-validation";
import styles from "./ask-question.module.css";

export function AskQuestionScreen({
  initialCollectionId,
}: {
  initialCollectionId?: string;
}) {
  const router = useRouter();
  const { logout } = useAuth();
  const [question, setQuestion] = useState("");
  const [inputError, setInputError] = useState<string>();
  const [collectionError, setCollectionError] = useState<string>();
  const [selectionNotice, setSelectionNotice] = useState<string | undefined>(
    initialCollectionId && !isApiUuid(initialCollectionId)
      ? "The linked collection was invalid. Select a collection to continue."
      : undefined,
  );
  const [selectedCollectionId, setSelectedCollectionId] = useState<
    string | null
  >(isApiUuid(initialCollectionId) ? initialCollectionId : null);
  const failureRef = useRef<HTMLDivElement>(null);

  const collectionsRequest = useDocumentCollections();
  const sourcesRequest = useQuestionSources();
  const questionRequest = useAskQuestion();
  const resetQuestionRequest = questionRequest.reset;

  useEffect(() => {
    if (collectionsRequest.status === "success" && selectedCollectionId) {
      const selectedCollectionExists = collectionsRequest.data.some(
        (collection) => collection.id === selectedCollectionId,
      );
      if (!selectedCollectionExists) {
        setSelectedCollectionId(null);
        setSelectionNotice(
          "The linked collection is no longer available. Select another collection to continue.",
        );
        resetQuestionRequest();
        router.replace("/dashboard/ask-question", { scroll: false });
      }
    }
  }, [
    collectionsRequest.data,
    collectionsRequest.status,
    resetQuestionRequest,
    router,
    selectedCollectionId,
  ]);

  useEffect(() => {
    const errors = [
      collectionsRequest.status === "error"
        ? collectionsRequest.error
        : undefined,
      questionRequest.state.status === "failed"
        ? questionRequest.state.error
        : undefined,
      sourcesRequest.status === "error"
        ? sourcesRequest.error
        : undefined,
    ];
    if (
      errors.some(
        (error) => error instanceof ApiError && error.status === 401,
      )
    ) {
      logout();
    }
  }, [
    collectionsRequest.error,
    collectionsRequest.status,
    logout,
    questionRequest.state,
    sourcesRequest.error,
    sourcesRequest.status,
  ]);

  useEffect(() => {
    if (questionRequest.state.status === "failed") {
      failureRef.current?.focus();
    }
  }, [questionRequest.state]);

  const collections =
    collectionsRequest.status === "success"
      ? collectionsRequest.data
      : [];
  const selectedCollection = collections.find(
    (collection) => collection.id === selectedCollectionId,
  );
  const scopeLabel = selectedCollection?.name ?? "the selected collection";

  const changeContext = (collectionId: string | null) => {
    setSelectedCollectionId(collectionId);
    if (collectionId) setCollectionError(undefined);
    setSelectionNotice(undefined);
    setInputError(undefined);
    resetQuestionRequest();
    router.replace(
      collectionId
        ? `/dashboard/ask-question?collectionId=${encodeURIComponent(collectionId)}`
        : "/dashboard/ask-question",
      { scroll: false },
    );
  };

  const submitQuestion = () => {
    const validationError = validateQuestion(question);
    setInputError(validationError);
    if (!selectedCollectionId) {
      setCollectionError("Select a collection.");
    }
    if (validationError || !selectedCollectionId) {
      return;
    }

    const normalized = normalizeQuestion(question);
    setInputError(undefined);
    setCollectionError(undefined);
    void questionRequest
      .submit({
        collectionId: selectedCollectionId,
        question: normalized,
        scopeLabel,
      })
      .catch(() => undefined);
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    submitQuestion();
  };

  if (
    collectionsRequest.status === "loading" ||
    sourcesRequest.status === "loading"
  ) {
    return (
      <DashboardPage>
        <AskQuestionSkeleton />
      </DashboardPage>
    );
  }

  const collectionFeedback =
    collectionsRequest.status === "error" ? (
      <AskQuestionErrorState
        content={getQuestionCollectionsError(collectionsRequest.error)}
        onRetry={() =>
          void collectionsRequest.refetch().catch(() => undefined)
        }
        retryLabel="Reload collections"
      />
    ) : selectionNotice ? (
      <p className={styles.selectionNotice} role="status">
        {selectionNotice}
      </p>
    ) : undefined;

  const sourceFeedback =
    sourcesRequest.status === "error" ? (
      <AskQuestionErrorState
        content={getQuestionSourcesError(sourcesRequest.error)}
        onRetry={() => void sourcesRequest.refetch().catch(() => undefined)}
        retryLabel="Reload document status"
      />
    ) : (
      selectedCollectionId ? (
        <QuestionSourceState
          documentCount={sourcesRequest.data.documentCount}
          readyCount={
            sourcesRequest.data.readyByCollection[selectedCollectionId] ?? 0
          }
          scopeLabel={scopeLabel}
        />
      ) : (
        <p className={styles.selectionNotice} role="status">
          Select a collection to see which ready documents will be searched.
        </p>
      )
    );

  const questionError =
    questionRequest.state.status === "failed"
      ? getQuestionErrorContent(questionRequest.state.error)
      : undefined;
  const failureAction =
    questionRequest.state.status === "failed"
      ? getQuestionFailureAction(
          questionRequest.state.error,
          questionRequest.state.submission.collectionId,
        )
      : undefined;
  const questionErrorAction =
    failureAction === "select-collection"
      ? () => changeContext(null)
      : failureAction === "retry"
        ? submitQuestion
        : undefined;
  const validationError = validateQuestion(question);

  return (
    <DashboardPage>
      <div className={styles.pageContent}>
        <AskQuestionForm
          collectionError={collectionError}
          collections={collections}
          contextFeedback={
            <>
              {collectionFeedback}
              {sourceFeedback}
            </>
          }
          contextSelectionDisabled={collectionsRequest.status !== "success"}
          inputError={inputError}
          isPending={questionRequest.isPending}
          isSubmitDisabled={
            questionRequest.isPending || validationError !== undefined
          }
          onContextChange={changeContext}
          onQuestionBlur={() => setInputError(validationError)}
          onQuestionChange={(value) => {
            setQuestion(value);
            setInputError(undefined);
            questionRequest.dismissFailure();
          }}
          onSubmit={submit}
          question={question}
          selectedCollectionId={selectedCollectionId}
        />

        {questionRequest.state.status === "submitting" ? (
          <QuestionGeneratingState
            scopeLabel={questionRequest.state.submission.scopeLabel}
          />
        ) : null}

        {questionError ? (
          <AskQuestionErrorState
            content={questionError}
            onRetry={questionErrorAction}
            ref={failureRef}
            retryLabel={
              questionRequest.state.status === "failed" &&
              questionRequest.state.error instanceof ApiError &&
              questionRequest.state.error.status === 404
                ? "Select another collection"
                : "Try again"
            }
          />
        ) : null}

        {questionRequest.state.status === "completed" ? (
          <QuestionAnswerPanel state={questionRequest.state} />
        ) : null}
      </div>
    </DashboardPage>
  );
}
