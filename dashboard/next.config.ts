import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Ensure markdown content used by server routes is bundled into Vercel lambdas.
  outputFileTracingIncludes: {
    "/**": ["./content/**/*"],
  },
};

export default nextConfig;
