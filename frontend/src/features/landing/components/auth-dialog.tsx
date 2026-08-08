"use client";

import * as React from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { AuthPanel, type AuthTab } from "@/features/auth/components/auth-panel";

type AuthDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultTab?: AuthTab;
};

export function AuthDialog({
  open,
  onOpenChange,
  defaultTab = "signin",
}: AuthDialogProps) {
  React.useEffect(() => {
    if (!open) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="border-border bg-card p-0 sm:max-w-md">
        <DialogTitle className="sr-only">SourceWise authentication</DialogTitle>
        <DialogDescription className="sr-only">
          Sign in, create an account, or request a password reset.
        </DialogDescription>
        <AuthPanel
          defaultTab={defaultTab}
          onAuthenticated={() => onOpenChange(false)}
        />
      </DialogContent>
    </Dialog>
  );
}
