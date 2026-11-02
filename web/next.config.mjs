import { loadConfiguration } from "./scripts/configuration.mjs";

loadConfiguration();

const nextConfig = {
  async redirects() {
    return [
      { source: "/admin", destination: "/admin/home", permanent: false },
      { source: "/user/:path*", destination: "/admin/:path*", permanent: false },
    ];
  },
  // Explicitly expose only these non-secret shared limits to the browser.
  env: {
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL || "",
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || process.env.SUPABASE_PUBLISHABLE_KEY || "",
    NEXT_PUBLIC_API_PAGE_SIZE: process.env.API_PAGE_SIZE || "",
    NEXT_PUBLIC_DOCUMENT_BATCH_LIMIT: process.env.DOCUMENT_BATCH_LIMIT || "",
    NEXT_PUBLIC_DOCUMENT_EXTENSIONS: process.env.DOCUMENT_EXTENSIONS || "",
    NEXT_PUBLIC_DOCUMENT_MAX_BYTES: process.env.DOCUMENT_MAX_BYTES || "",
    NEXT_PUBLIC_IMAGE_MAX_BYTES: process.env.IMAGE_MAX_BYTES || "",
    NEXT_PUBLIC_IMAGE_CONTENT_TYPES: process.env.IMAGE_CONTENT_TYPES || "",
    NEXT_PUBLIC_CHAT_MAX_MESSAGE_LENGTH: process.env.CHAT_MAX_MESSAGE_LENGTH || "",
  },
  experimental: {
    optimizePackageImports: ["@chakra-ui/react"],
  },
}

export default nextConfig;


