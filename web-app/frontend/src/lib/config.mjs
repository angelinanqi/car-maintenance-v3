// Use explicit property access so Next.js can inline public build-time settings.
function positiveInteger(name, raw, fallback) {
  const value = Number(raw || fallback);
  if (!Number.isSafeInteger(value) || value < 1) {
    throw new Error(name + " must be a positive integer");
  }
  return value;
}

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");
export const CHAT_MAX_MESSAGE_LENGTH = positiveInteger("CHAT_MAX_MESSAGE_LENGTH", process.env.NEXT_PUBLIC_CHAT_MAX_MESSAGE_LENGTH, 4000);
export const CHAT_HISTORY_LIMIT = positiveInteger("CHAT_HISTORY_LIMIT", process.env.NEXT_PUBLIC_CHAT_HISTORY_LIMIT, 6);
export const DOCUMENT_MAX_FILES = positiveInteger("NEXT_PUBLIC_DOCUMENT_MAX_FILES", process.env.NEXT_PUBLIC_DOCUMENT_MAX_FILES, 20);
export const DOCUMENT_MAX_BYTES = positiveInteger("NEXT_PUBLIC_DOCUMENT_MAX_BYTES", process.env.NEXT_PUBLIC_DOCUMENT_MAX_BYTES, 52428800);
export const DOCUMENT_EXTENSIONS = (process.env.NEXT_PUBLIC_DOCUMENT_EXTENSIONS || ".pdf,.md")
  .split(",").map((extension) => extension.trim().toLowerCase()).filter(Boolean);
// Configuration can restrict supported formats, but cannot add a new parser.
if (!DOCUMENT_EXTENSIONS.length || DOCUMENT_EXTENSIONS.some((extension) => ![".pdf", ".md"].includes(extension))) {
  throw new Error("NEXT_PUBLIC_DOCUMENT_EXTENSIONS must contain .pdf and/or .md");
}

export const API_PAGE_SIZE = positiveInteger("API_PAGE_SIZE", process.env.NEXT_PUBLIC_API_PAGE_SIZE, 100);
export const DOCUMENT_BATCH_LIMIT = positiveInteger("DOCUMENT_BATCH_LIMIT", process.env.NEXT_PUBLIC_DOCUMENT_BATCH_LIMIT, 20);
export const CONTENT_POLL_MS = positiveInteger("NEXT_PUBLIC_CONTENT_POLL_MS", process.env.NEXT_PUBLIC_CONTENT_POLL_MS, 3000);
export const IMAGE_MAX_BYTES = positiveInteger("IMAGE_MAX_BYTES", process.env.NEXT_PUBLIC_IMAGE_MAX_BYTES, 10485760);
export const IMAGE_CONTENT_TYPES = (process.env.NEXT_PUBLIC_IMAGE_CONTENT_TYPES || "image/jpeg,image/png,image/webp,image/gif").split(",").map((value) => value.trim());
