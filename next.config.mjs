/** @type {import('next').NextConfig} */
// Custom domain apex is `/`. On github.io project Pages the app still lives at `/-we-the-people/`.
// CI sets assetPrefix so one export loads JS/CSS from the known-working github.io origin on both hosts.
const assetPrefix =
  process.env.GITHUB_ACTIONS === "true"
    ? "https://hawaiibookmark-ops.github.io/-we-the-people"
    : "";

const nextConfig = {
  output: "export",
  trailingSlash: true,
  ...(assetPrefix ? { assetPrefix } : {}),
  images: { unoptimized: true },
};

export default nextConfig;
