import Link from "next/link";

export function Header() {
  return (
    <header className="mast">
      <div className="wrap mast-inner">
        <Link className="brand" href="/">
          <small>A nonpartisan voter hub</small>
          <strong>We The People</strong>
        </Link>
        <nav>
          <Link href="/">Lookup</Link>
          <Link href="/pro/">Founding Pro</Link>
          <Link href="/about/">Sources</Link>
        </nav>
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer>
      <div className="wrap">
        <p>
          Lookup is always free. Facts are cited to official sources with a retrieval timestamp.
          No scores, no candidate ads, no selling of donor lists or user data.
        </p>
        <p>
          <Link href="/about/">Methodology and sources</Link>
          {" · "}
          <Link href="/pro/">Founding Pro $5/month</Link>
        </p>
      </div>
    </footer>
  );
}
