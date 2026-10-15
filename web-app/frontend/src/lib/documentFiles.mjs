import { DOCUMENT_EXTENSIONS, DOCUMENT_MAX_BYTES } from "./config.mjs";

export function validateDocumentFile(file) {
  if (!file) return "Choose a document to upload.";
  if (!DOCUMENT_EXTENSIONS.some((extension) => file.name.toLowerCase().endsWith(extension)))
    return `Choose a supported document: ${DOCUMENT_EXTENSIONS.join(", ")}.`;
  if (file.size > DOCUMENT_MAX_BYTES)
    return `The document exceeds the ${DOCUMENT_MAX_BYTES} byte limit.`;
  if (file.size === 0) return "The selected document is empty.";
  return "";
}

