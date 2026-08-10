"use client";

import type { ComponentProps, ReactNode, RefObject } from "react";
import { X } from "lucide-react";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { CollectionButton } from "../collection-button";
import styles from "../collection-dialogs.module.css";

type CollectionDialogProps = {
  children: ReactNode;
  description: string;
  descriptionVariant?: "body" | "hidden" | "warning";
  footer?: ReactNode;
  initialFocusRef: RefObject<HTMLElement | null>;
  onClose: () => void;
  role?: "dialog" | "alertdialog";
  title: string;
};

export function CollectionDialog({
  children,
  description,
  descriptionVariant = "hidden",
  footer,
  initialFocusRef,
  onClose,
  role = "dialog",
  title,
}: CollectionDialogProps) {
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        className={styles.modal}
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          initialFocusRef.current?.focus();
        }}
        role={role}
        showCloseButton={false}
      >
        <DialogHeader className={styles.header}>
          <DialogTitle className={styles.title}>{title}</DialogTitle>
          <DialogClose asChild>
            <button aria-label="Close" className={styles.closeButton} type="button">
              <X aria-hidden="true" className={styles.closeIcon} />
            </button>
          </DialogClose>
        </DialogHeader>
        <div className={styles.scrollRegion}>
          <DialogDescription
            className={
              descriptionVariant === "warning"
                ? styles.retentionWarning
                : descriptionVariant === "body"
                  ? styles.descriptionBody
                  : "sr-only"
            }
          >
            {description}
          </DialogDescription>
          {children}
        </div>
        {footer}
      </DialogContent>
    </Dialog>
  );
}

export function CollectionDialogFooter({
  className,
  ...props
}: ComponentProps<typeof DialogFooter>) {
  return <DialogFooter className={cn(styles.footer, className)} {...props} />;
}

export function CollectionDialogCancel({
  children = "Cancel",
  ...props
}: ComponentProps<typeof CollectionButton>) {
  return (
    <DialogClose asChild>
      <CollectionButton {...props} tone="secondary" type="button">
        {children}
      </CollectionButton>
    </DialogClose>
  );
}
