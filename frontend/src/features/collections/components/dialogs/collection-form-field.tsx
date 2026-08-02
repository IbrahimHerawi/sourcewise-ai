"use client";

import type { ChangeEvent, RefObject } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import styles from "../collection-dialogs.module.css";

type CollectionFormFieldProps = {
  controlRef?: RefObject<HTMLInputElement | null>;
  error?: string;
  helper: string;
  id: string;
  label: string;
  maxLength: number;
  onChange: (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
  required?: boolean;
  type?: "input" | "textarea";
  value: string;
};

export function CollectionFormField({
  controlRef,
  error,
  helper,
  id,
  label,
  maxLength,
  onChange,
  required = false,
  type = "input",
  value,
}: CollectionFormFieldProps) {
  const helperId = `${id}-helper`;
  const controlProps = {
    "aria-describedby": helperId,
    "aria-invalid": Boolean(error),
    id,
    maxLength,
    onChange,
    required,
    value,
  };

  return (
    <div className={styles.field}>
      <Label className={styles.label} htmlFor={id}>
        {label}
      </Label>
      {type === "textarea" ? (
        <Textarea className={styles.textarea} {...controlProps} />
      ) : (
        <Input
          autoComplete="off"
          className={styles.input}
          ref={controlRef}
          {...controlProps}
        />
      )}
      <p className={error ? styles.fieldError : styles.helper} id={helperId}>
        {error ?? helper}
      </p>
    </div>
  );
}
