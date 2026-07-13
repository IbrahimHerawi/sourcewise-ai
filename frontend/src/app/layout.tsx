import type { Metadata } from "next";
import { Geist_Mono, Manrope } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";

// Google Sans Flex is a proprietary Google brand font and is NOT distributed
// via the public Google Fonts API, so next/font/google cannot load it. We load
// Manrope (a clean, geometric, variable Google Font that closely matches the
// Google Sans aesthetic) as the consistent rendered font, and declare
// "Google Sans Flex" / "Google Sans" as the preferred families in the CSS
// stack (globals.css) so devices that have them installed use them instead.
const manrope = Manrope({
  variable: "--font-manrope",
  subsets: ["latin"],
  weight: ["200", "300", "400", "500", "600", "700", "800"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${manrope.variable} ${geistMono.variable}`}
    >
      <body className="font-sans antialiased bg-background text-foreground">
        {children}
        <Toaster />
      </body>
    </html>
  );
}
