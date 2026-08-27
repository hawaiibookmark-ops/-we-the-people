import type { Metadata } from "next";
import "./globals.css";
import { Header, Footer } from "@/components/Chrome";

export const metadata: Metadata = {
  title: "We The People — nonpartisan voter hub",
  description:
    "Official-source voter lookup for the November 3, 2026 general election. Hawaiʻi gold template. No scores. No ads.",
  metadataBase: new URL("https://hawaiibookmark-ops.github.io/-we-the-people/"),
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Header />
        <main className="wrap">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
