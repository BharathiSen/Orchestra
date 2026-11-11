import type { Metadata } from "next";
import type { ReactNode } from "react";

// The page is a client component, so its title is declared here. The root
// layout's template renders it as "Projects · Orchestra".
export const metadata: Metadata = {
  // Has child routes, so it re-declares the template: a plain string title
  // would stop the root template from reaching them.
  title: { default: "Projects", template: "%s · Orchestra" },
  // Signed-in area: nothing here is useful to a search engine.
  robots: { index: false, follow: false },
};

export default function Layout({ children }: { children: ReactNode }) {
  return children;
}
