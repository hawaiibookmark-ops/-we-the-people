import type { Metadata } from "next";
import Script from "next/script";
import "./globals.css";
import { Header, Footer } from "@/components/Chrome";

export const metadata: Metadata = {
  title: "We The People — nonpartisan voter hub",
  description:
    "Official-source voter lookup for the November 3, 2026 general election. Hawaiʻi gold template. No scores. No ads.",
  metadataBase: new URL("https://getwethepeople.com"),
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Script id="github-io-path-prefix" strategy="beforeInteractive">
          {`(function(){var p="/-we-the-people";if(!location.hostname.endsWith("github.io"))return;document.addEventListener("click",function(e){var t=e.target;var a=t&&t.closest?t.closest("a"):null;if(!a)return;var h=a.getAttribute("href");if(!h||h.charAt(0)!=="/"||h.indexOf("//")===0||h.indexOf(p)===0)return;a.setAttribute("href",p+h);},true);})();`}
        </Script>
        <Header />
        <main className="wrap">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
