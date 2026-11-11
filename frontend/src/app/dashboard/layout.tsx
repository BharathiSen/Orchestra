import type { Metadata } from "next";
import type { ReactNode } from "react";

// The page is a client component, so its title is declared here. The root
// layout's template renders it as "Dashboard · Orchestra".
export const metadata: Metadata = {
  title: "Dashboard",
  // Signed-in area: nothing here is useful to a search engine.
  robots: { index: false, follow: false },
};

export default function Layout({ children }: { children: ReactNode }) {
  return children;
}
