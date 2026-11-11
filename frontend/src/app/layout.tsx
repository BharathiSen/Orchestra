import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans, Space_Grotesk } from "next/font/google";

import DemoBanner from "@/components/DemoBanner";
import "./globals.css";

// Downloaded at build time and served from this origin: no third-party
// request, nothing for the CSP to block, and size-adjusted fallbacks so text
// does not shift when the webfont arrives.
const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  weight: ["500", "700"],
  variable: "--font-space",
  display: "swap",
});

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-geist-sans",
  display: "swap",
});

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
    <html lang="en" className={`${spaceGrotesk.variable} ${plexSans.variable}`}>
      <body className="font-sans">
        <DemoBanner />
        {children}
      </body>
    </html>
  );
}
