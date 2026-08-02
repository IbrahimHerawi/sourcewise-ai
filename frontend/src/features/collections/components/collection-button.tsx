import type { ComponentProps } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import styles from "./collection-button.module.css";

type CollectionButtonProps = ComponentProps<typeof Button> & {
  shape?: "standard" | "pill";
  tone?: "primary" | "secondary" | "danger" | "outline" | "solid-danger";
};

export function CollectionButton({
  className,
  shape = "standard",
  tone = "primary",
  ...props
}: CollectionButtonProps) {
  return (
    <Button
      className={cn(
        styles.button,
        tone === "secondary" && styles.secondary,
        tone === "danger" && styles.danger,
        tone === "outline" && styles.outline,
        tone === "solid-danger" && styles.solidDanger,
        shape === "pill" && styles.pill,
        className,
      )}
      size="sm"
      {...props}
    />
  );
}
