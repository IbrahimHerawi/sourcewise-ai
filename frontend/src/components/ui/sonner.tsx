"use client"

import { useTheme } from "next-themes"
import { Toaster as Sonner, ToasterProps } from "sonner"

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme()

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      style={
        {
          "--normal-bg": "var(--sw-color-background-surface)",
          "--normal-text": "var(--sw-color-text-primary)",
          "--normal-border": "var(--sw-color-border-default)",
        } as React.CSSProperties
      }
      {...props}
    />
  )
}

export { Toaster }
