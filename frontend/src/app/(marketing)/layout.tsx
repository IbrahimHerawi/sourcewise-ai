import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "SourceWise — Chat with your documents, powered by AI",
  description:
    "Upload PDF, Markdown, and TXT files, then ask anything. SourceWise's AI answers strictly from your documents — accurate, sourced, and instant.",
  keywords: ["SourceWise", "AI document chat", "PDF Q&A", "document AI", "knowledge base", "AI assistant"],
  authors: [{ name: "SourceWise" }],
  icons: {
    icon: "https://z-cdn.chatglm.cn/z-ai/static/logo.svg",
  },
  openGraph: {
    title: "SourceWise — Chat with your documents, powered by AI",
    description:
      "Upload PDF, Markdown, and TXT files, then ask anything. Get AI answers grounded only in your documents.",
    url: "https://chat.z.ai",
    siteName: "SourceWise",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "SourceWise — Chat with your documents, powered by AI",
    description:
      "Upload PDF, Markdown, and TXT files, then ask anything. Get AI answers grounded only in your documents.",
  },
};

export default function MarketingLayout({ children }: { children: ReactNode }) {
  return children;
}
