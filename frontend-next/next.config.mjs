/** @type {import("next").NextConfig} */
const nextConfig = {
  output: "export",
  reactStrictMode: true,
  trailingSlash: true,
  basePath: "/app",
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
