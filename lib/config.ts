/** Repo path on github.io project Pages. Empty on the custom-domain apex. */
export const REPO_BASE_PATH = "/-we-the-people";
export const CANONICAL_HOST = "getwethepeople.com";
export const CANONICAL_ORIGIN = `https://${CANONICAL_HOST}`;
export const GITHUB_PAGES_ORIGIN = "https://hawaiibookmark-ops.github.io/-we-the-people";

const CUSTOM_HOSTS = new Set([CANONICAL_HOST, `www.${CANONICAL_HOST}`]);

export function siteBase(hostname?: string): string {
  const host = (hostname ?? (typeof window !== "undefined" ? window.location.hostname : "")).toLowerCase();
  if (!host || host === "localhost" || host === "127.0.0.1" || host.endsWith(".localhost")) return "";
  if (CUSTOM_HOSTS.has(host)) return "";
  if (host.endsWith("github.io")) return REPO_BASE_PATH;
  return "";
}

export function sitePath(path: string, hostname?: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${siteBase(hostname)}${p}`;
}

export function siteOrigin(hostname?: string, protocol?: string): string {
  const host = hostname ?? (typeof window !== "undefined" ? window.location.hostname : "");
  if (host && (CUSTOM_HOSTS.has(host.toLowerCase()) || host.toLowerCase().endsWith("github.io"))) {
    const proto = protocol ?? (typeof window !== "undefined" ? window.location.protocol : "https:");
    return `${proto}//${host}${siteBase(host)}`;
  }
  return CANONICAL_ORIGIN;
}

export function dataUrl(file: string): string {
  return `${siteBase()}/data/${file}`;
}

export function partyName(code: string | undefined): string {
  const map: Record<string, string> = {
    D: "Democratic Party",
    R: "Republican Party",
    G: "Green Party",
    L: "Libertarian Party",
    N: "Nonpartisan",
    NON: "Nonpartisan",
  };
  return map[code || ""] || code || "Party not listed on source";
}
