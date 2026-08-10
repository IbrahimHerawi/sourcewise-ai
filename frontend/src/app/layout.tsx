import type { Metadata } from "next";
import { Geist_Mono, Inter, Manrope } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";
import { AuthProvider } from "@/contexts/auth-context";

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  ),
  applicationName: "SourceWise",
  title: "SourceWise",
  description:
    "Ask questions and get cited AI answers grounded in your own documents.",
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      {
        url: "/brand/sourcewise-mark-192.png",
        sizes: "192x192",
        type: "image/png",
      },
      {
        url: "/brand/sourcewise-mark-512.png",
        sizes: "512x512",
        type: "image/png",
      },
    ],
    shortcut: "/favicon.ico",
    apple: {
      url: "/apple-touch-icon.png",
      sizes: "180x180",
      type: "image/png",
    },
  },
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    title: "SourceWise",
  },
};

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

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${manrope.variable} ${geistMono.variable} ${inter.variable}`}
    >
      <body className="font-sans antialiased bg-background text-foreground">
        <AuthProvider>
          {children}
          <Toaster />
        </AuthProvider>
      </body>
    </html>
  );
}
