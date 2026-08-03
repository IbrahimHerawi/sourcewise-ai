"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { DashboardPage } from "@/features/dashboard/components/dashboard-page";
import { useDocumentCollections } from "@/features/documents/hooks/use-documents-api";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";
import { AskQuestionForm } from "./ask-question-form";
import {
  AskQuestionErrorState,
  AskQuestionSkeleton,
  QuestionGeneratingState,
} from "./ask-question-states";
import { QuestionAnswerPanel } from "./question-answer-panel";
import { useAskQuestion } from "../hooks/use-ask-question";
import {
  getQuestionCollectionsError,
  getQuestionErrorContent,
} from "../question-error-utils";
import {
  normalizeQuestion,
  validateQuestion,
} from "../question-validation";
import styles from "./ask-question.module.css";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isUuid(value: string | undefined): value is string {
  return Boolean(value && UUID_PATTERN.test(value));
}

export function AskQuestionScreen({
  initialCollectionId,
}: {
  initialCollectionId?: string;
}) {
  const router = useRouter();
  const { logout } = useAuth();
  const [question, setQuestion] = useState("");
  const [inputError, setInputError] = useState<string>();
  const [selectionNotice, setSelectionNotice] = useState<string | undefined>(
    initialCollectionId && !isUuid(initialCollectionId)
      ? "The linked collection was invalid, so all documents are selected."
      : undefined,
  );
  const [selectedCollectionId, setSelectedCollectionId] = useState<
    string | null
  >(isUuid(initialCollectionId) ? initialCollectionId : null);
  const failureRef = useRef<HTMLDivElement>(null);

  const collectionsRequest = useDocumentCollections();
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
          "The linked collection is no longer available, so all documents are selected.",
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
    if (
      collectionsRequest.status === "error" &&
      selectedCollectionId !== null
    ) {
      setSelectedCollectionId(null);
      setSelectionNotice(
        "Collections could not be loaded, so all documents are selected.",
      );
      resetQuestionRequest();
      router.replace("/dashboard/ask-question", { scroll: false });
    }
  }, [
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
  const scopeLabel = selectedCollection?.name ?? "All documents";

  const changeContext = (collectionId: string | null) => {
    setSelectedCollectionId(collectionId);
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
    if (validationError) {
      setInputError(validationError);
      return;
    }

    const normalized = normalizeQuestion(question);
    setInputError(undefined);
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

  if (collectionsRequest.status === "loading") {
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

  const questionError =
    questionRequest.state.status === "failed"
      ? getQuestionErrorContent(questionRequest.state.error)
      : undefined;
  const questionErrorAction =
    questionRequest.state.status === "failed" &&
    questionRequest.state.error instanceof ApiError &&
    (questionRequest.state.error.code === "invalid_response" ||
      questionRequest.state.error.status === 401 ||
      questionRequest.state.error.status === 403)
      ? undefined
      : questionRequest.state.status === "failed" &&
          questionRequest.state.error instanceof ApiError &&
          questionRequest.state.error.status === 404
        ? () => changeContext(null)
        : submitQuestion;

  return (
    <DashboardPage>
      <div className={styles.pageContent}>
        <AskQuestionForm
          collections={collections}
          contextFeedback={collectionFeedback}
          contextSelectionDisabled={collectionsRequest.status !== "success"}
          inputError={inputError}
          isPending={questionRequest.isPending}
          onContextChange={changeContext}
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
                ? "Search all documents"
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
