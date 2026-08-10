import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "SourceWise — Chat with your documents, powered by AI",
  description:
    "Upload PDF, Markdown, and TXT files, then ask anything. SourceWise's AI answers strictly from your documents — accurate, sourced, and instant.",
  keywords: ["SourceWise", "AI document chat", "PDF Q&A", "document AI", "knowledge base", "AI assistant"],
  authors: [{ name: "SourceWise" }],
  openGraph: {
    title: "SourceWise — Chat with your documents, powered by AI",
    description:
      "Upload PDF, Markdown, and TXT files, then ask anything. Get AI answers grounded only in your documents.",
    images: [
      {
        url: "/brand/sourcewise-social-card.png",
        width: 1200,
        height: 630,
        alt: "SourceWise",
      },
    ],
    siteName: "SourceWise",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "SourceWise — Chat with your documents, powered by AI",
    description:
      "Upload PDF, Markdown, and TXT files, then ask anything. Get AI answers grounded only in your documents.",
    images: ["/brand/sourcewise-social-card.png"],
  },
};

export default function MarketingLayout({ children }: { children: ReactNode }) {
  return children;
}
