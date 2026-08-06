import type { Metadata, Viewport } from "next";

import DemoBanner from "@/components/DemoBanner";
import "./globals.css";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:13000";

const TITLE = "Orchestra — AI Engineering Platform";
const DESCRIPTION =
  "Design, run, evaluate, and debug LangGraph agents. Multi-agent pipelines with " +
  "memory, RAG on Postgres + pgvector, and full execution tracing with replay.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: TITLE,
    template: "%s · Orchestra",
  },
  description: DESCRIPTION,
  applicationName: "Orchestra",
  keywords: [
    "AI engineering",
    "LangGraph",
    "multi-agent",
    "RAG",
    "pgvector",
    "LLM observability",
    "agent tracing",
  ],
  openGraph: {
    type: "website",
    siteName: "Orchestra",
    title: TITLE,
    description: DESCRIPTION,
    url: SITE_URL,
    locale: "en_US",
  },
  twitter: {
    card: "summary",
    title: TITLE,
    description: DESCRIPTION,
  },
  robots: {
    index: true,
    follow: true,
  },
};

export const viewport: Viewport = {
  themeColor: "#0d9488",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="font-sans">
        <DemoBanner />
        {children}
      </body>
    </html>
  );
}
