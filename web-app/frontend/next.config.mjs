import { fileURLToPath } from "node:url";
import nextEnv from "@next/env";

nextEnv.loadEnvConfig(
  fileURLToPath(new URL("../../", import.meta.url)),
  process.env.NODE_ENV === "development",
);

const nextConfig = {
  // Explicitly expose only these non-secret shared limits to the browser.
  env: {
    NEXT_PUBLIC_API_PAGE_SIZE: process.env.API_PAGE_SIZE || "",
    NEXT_PUBLIC_DOCUMENT_BATCH_LIMIT: process.env.DOCUMENT_BATCH_LIMIT || "",
    NEXT_PUBLIC_DOCUMENT_EXTENSIONS: process.env.DOCUMENT_EXTENSIONS || "",
    NEXT_PUBLIC_DOCUMENT_MAX_BYTES: process.env.DOCUMENT_MAX_BYTES || "",
    NEXT_PUBLIC_IMAGE_MAX_BYTES: process.env.IMAGE_MAX_BYTES || "",
    NEXT_PUBLIC_IMAGE_CONTENT_TYPES: process.env.IMAGE_CONTENT_TYPES || "",
    NEXT_PUBLIC_CHAT_MAX_MESSAGE_LENGTH: process.env.CHAT_MAX_MESSAGE_LENGTH || "",
    NEXT_PUBLIC_CHAT_HISTORY_LIMIT: process.env.CHAT_HISTORY_LIMIT || "",
  },
  turbopack: { root: fileURLToPath(new URL("./", import.meta.url)) },
  experimental: {
    optimizePackageImports: ["@chakra-ui/react"],
  },
}

export default nextConfig;


