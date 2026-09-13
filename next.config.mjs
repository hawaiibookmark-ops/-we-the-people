/** @type {import('next').NextConfig} */
// No basePath: the Pages artifact root is index.html so custom-domain apex `/` is 200.
// Production/CI sets assetPrefix to the project path (not the github.io origin).
// github.io resolves /-we-the-people/_next from the artifact root; getwethepeople.com
// resolves the same URL from the dual-published out/-we-the-people/_next copy.
// Do not point assetPrefix at https://*.github.io — once the domain is attached,
// github.io 301s to apex and those asset URLs die.
const pagesExport =
  process.env.GITHUB_ACTIONS === "true" || process.env.WTP_PAGES_EXPORT === "true";

const nextConfig = {
  output: "export",
  trailingSlash: true,
  ...(pagesExport ? { assetPrefix: "/-we-the-people" } : {}),
  images: { unoptimized: true },
};

export default nextConfig;
