"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent,
} from "react";
import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";
import { DashboardPage } from "@/features/dashboard/components/dashboard-page";
import { useDashboardHeader } from "@/features/dashboard/components/dashboard-header-context";
import { useCollectionsDialog } from "@/features/collections/hooks/use-collections-dialog";
import { useCollectionsPage } from "@/features/collections/hooks/use-collections-api";
import { CollectionButton } from "./collection-button";
import { CollectionsContent } from "./collections-content";
import { CollectionsDialogs } from "./dialogs/collections-dialogs";
import styles from "./collections-screen.module.css";

type CollectionsScreenProps = {
  initialPage?: number;
};

const PAGE_SIZE = 20;

export function CollectionsScreen({ initialPage = 1 }: CollectionsScreenProps) {
  const router = useRouter();
  const { logout } = useAuth();
  const [currentPage, setCurrentPage] = useState(initialPage);
  const headerActionRef = useRef<HTMLButtonElement>(null);
  const requestState = useCollectionsPage(
    PAGE_SIZE,
    (currentPage - 1) * PAGE_SIZE,
  );
  const { closeDialog, dialog, openDialog } = useCollectionsDialog({
    fallbackFocusRef: headerActionRef,
    initialDialog: null,
  });

  useEffect(() => {
    if (requestState.status === "error" && requestState.error instanceof ApiError) {
      if (requestState.error.status === 401) logout();
    }
  }, [logout, requestState.error, requestState.status]);

  const changePage = useCallback(
    (page: number) => {
      const safePage = Math.max(1, page);
      setCurrentPage(safePage);
      router.replace(
        safePage === 1 ? "/dashboard/collections" : `/dashboard/collections?page=${safePage}`,
        { scroll: false },
      );
    },
    [router],
  );

  useEffect(() => {
    if (requestState.status !== "success" || requestState.data.total === 0) return;
    const lastPage = Math.ceil(requestState.data.total / requestState.data.limit);
    if (currentPage > lastPage) changePage(lastPage);
  }, [changePage, currentPage, requestState.data, requestState.status]);

  const refreshAndClose = () => {
    closeDialog();
    void requestState.refetch().catch(() => undefined);
  };

  const handleCreated = () => {
    closeDialog();
    if (currentPage === 1) void requestState.refetch().catch(() => undefined);
    else changePage(1);
  };

  const handleDeleted = () => {
    closeDialog();
    if (
      currentPage > 1 &&
      requestState.status === "success" &&
      requestState.data.items.length === 1
    ) {
      changePage(currentPage - 1);
    } else {
      void requestState.refetch().catch(() => undefined);
    }
  };

  const handleOpenCreate = useCallback(
    (event: MouseEvent<HTMLButtonElement>) =>
      openDialog({ type: "create" }, event.currentTarget),
    [openDialog],
  );
  const headerAction = useMemo(
    () => (
      <CollectionButton onClick={handleOpenCreate} ref={headerActionRef}>
        <Plus aria-hidden="true" />
        Create Collection
      </CollectionButton>
    ),
    [handleOpenCreate],
  );
  const headerConfiguration = useMemo(
    () => ({ actions: headerAction }),
    [headerAction],
  );
  useDashboardHeader(headerConfiguration);

  return (
    <DashboardPage>
      <div className={styles.content}>
        <CollectionsContent
          currentPage={currentPage}
          onPageChange={changePage}
          onOpenDialog={openDialog}
          onRetry={() => void requestState.refetch().catch(() => undefined)}
          requestState={requestState}
        />
      </div>
      <CollectionsDialogs
        dialog={dialog}
        onClose={closeDialog}
        onCreated={handleCreated}
        onDeleted={handleDeleted}
        onUpdated={refreshAndClose}
      />
    </DashboardPage>
  );
}
