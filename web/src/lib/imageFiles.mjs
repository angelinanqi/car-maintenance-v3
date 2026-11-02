import { IMAGE_CONTENT_TYPES, IMAGE_MAX_BYTES } from "./config.mjs";

export const IMAGE_UPLOAD_LIMITS = `Accepted: ${IMAGE_CONTENT_TYPES.map((type) => type.replace("image/", "").toUpperCase()).join(", ")}. Maximum ${IMAGE_MAX_BYTES / 1024 / 1024} MB per file; 1 file per upload.`;

export function validateImageFile(file) {
  if (!file) return "Choose an image to upload.";
  if (!IMAGE_CONTENT_TYPES.includes(file.type)) return `Unsupported image format. ${IMAGE_UPLOAD_LIMITS}`;
  if (file.size > IMAGE_MAX_BYTES) return `Image is too large. ${IMAGE_UPLOAD_LIMITS}`;
  if (file.size === 0) return "The selected image is empty. Choose another image.";
  return "";
}
