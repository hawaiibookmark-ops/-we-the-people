"use client";

import { useEffect, useState } from "react";
import { sitePath } from "@/lib/config";

function usePrefixed(path: string): string {
  const [href, setHref] = useState(path);
  useEffect(() => {
    setHref(sitePath(path));
  }, [path]);
  return href;
}

export function Header() {
  const home = usePrefixed("/");
  const pro = usePrefixed("/pro/");
  const about = usePrefixed("/about/");
  return (
    <header className="mast">
      <div className="wrap mast-inner">
        <a className="brand" href={home}>
          <small>A nonpartisan voter hub</small>
          <strong>We The People</strong>
        </a>
        <nav>
          <a href={home}>Lookup</a>
          <a href={pro}>Founding Pro</a>
          <a href={about}>Sources</a>
        </nav>
      </div>
    </header>
  );
}

export function Footer() {
  const about = usePrefixed("/about/");
  const pro = usePrefixed("/pro/");
  return (
    <footer>
      <div className="wrap">
        <p>
          Lookup is always free. Facts are cited to official sources with a retrieval timestamp.
          No scores, no candidate ads, no selling of donor lists or user data.
        </p>
        <p>
          <a href={about}>Methodology and sources</a>
          {" · "}
          <a href={pro}>Founding Pro $5/month</a>
        </p>
      </div>
    </footer>
  );
}
