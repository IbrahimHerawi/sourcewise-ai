"use client";

import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import type { CollectionsDialogState } from "@/features/collections/collection-dialog-state";

type UseCollectionsDialogOptions = {
  fallbackFocusRef: RefObject<HTMLElement | null>;
  initialDialog: CollectionsDialogState | null;
};

export function useCollectionsDialog({
  fallbackFocusRef,
  initialDialog,
}: UseCollectionsDialogOptions) {
  const [dialog, setDialog] = useState<CollectionsDialogState | null>(
    initialDialog,
  );
  const openerRef = useRef<HTMLElement | null>(null);
  const previousDialogRef = useRef(dialog);

  useEffect(() => {
    if (previousDialogRef.current && !dialog) {
      const opener = openerRef.current;
      const focusTarget = opener?.isConnected ? opener : fallbackFocusRef.current;

      focusTarget?.focus();
      openerRef.current = null;
    }

    previousDialogRef.current = dialog;
  }, [dialog, fallbackFocusRef]);

  const openDialog = useCallback(
    (nextDialog: CollectionsDialogState, opener: HTMLElement) => {
      openerRef.current = opener;
      setDialog(nextDialog);
    },
    [],
  );

  const closeDialog = useCallback(() => setDialog(null), []);

  return { closeDialog, dialog, openDialog };
}
