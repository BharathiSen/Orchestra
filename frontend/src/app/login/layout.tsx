import type { Metadata } from "next";
import type { ReactNode } from "react";

// The page is a client component, so its title is declared here. The root
// layout's template renders it as "Sign in · Orchestra".
export const metadata: Metadata = {
  title: "Sign in",
};

export default function Layout({ children }: { children: ReactNode }) {
  return children;
}
