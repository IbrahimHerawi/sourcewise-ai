"use client"

import { useToast } from "@/hooks/use-toast"
import { CircleAlert, CircleCheck, CircleX, Info, LoaderCircle } from "lucide-react"
import {
  Toast,
  ToastProvider,
  ToastTitle,
  type ToastVariant,
  ToastViewport,
} from "@/components/ui/toast"

function ToastIcon({ variant }: { variant: ToastVariant }) {
  const iconVariant =
    variant === "default" || variant === "success"
      ? "success"
      : variant === "error" || variant === "destructive"
        ? "error"
        : variant
  const className = `toast-notification__icon toast-notification__icon--${iconVariant}`

  if (variant === "loading") {
    return <LoaderCircle aria-hidden="true" className={`${className} animate-spin`} />
  }

  if (variant === "warning") {
    return <CircleAlert aria-hidden="true" className={className} />
  }

  if (variant === "info") {
    return <Info aria-hidden="true" className={className} />
  }

  if (variant === "error" || variant === "destructive") {
    return <CircleX aria-hidden="true" className={className} />
  }

  return <CircleCheck aria-hidden="true" className={className} />
}

export function Toaster() {
  const { toasts } = useToast()

  return (
    <ToastProvider>
      {toasts.map(function ({ id, title, description, action, variant, ...props }) {
        const toastVariant = variant ?? "default"
        const message = title && description
          ? <>{title} — {description}</>
          : title ?? description

        return (
          <Toast key={id} variant={toastVariant} {...props}>
            <ToastIcon variant={toastVariant} />
            <div className="toast-notification__content">
              {message && <ToastTitle>{message}</ToastTitle>}
            </div>
            {action}
          </Toast>
        )
      })}
      <ToastViewport />
    </ToastProvider>
  )
}
