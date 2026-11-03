import { DOCUMENT_MAX_BYTES, IMAGE_MAX_BYTES, IMAGE_CONTENT_TYPES } from './config.mjs';

export const EMERGENCY_MEDIA_ACCEPT = [...IMAGE_CONTENT_TYPES, 'video/mp4'];
export const meaningfulVideoDescription = value => {
  const words = (value || '').toLowerCase().match(/[\p{L}\p{N}_]+/gu) || [];
  return words.length >= 6 && new Set(words).size >= 5 && value.trim().length >= 30;
};
export function validateEmergencyFile(file) {
  const extension = file.name.split('.').pop().toLowerCase();
  const formats = { png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', webp: 'image/webp', gif: 'image/gif', mp4: 'video/mp4' };
  const mime = formats[extension];
  if (!mime || !EMERGENCY_MEDIA_ACCEPT.includes(mime) || (file.type && file.type !== mime))
    return 'Choose a PNG, JPEG, WebP, GIF image or an MP4 video file. External media links are not supported.';
  const limit = mime === 'video/mp4' ? DOCUMENT_MAX_BYTES : IMAGE_MAX_BYTES;
  if (!file.size || file.size > limit) return `Choose a nonempty ${mime === 'video/mp4' ? 'video' : 'image'} up to ${Math.floor(limit / 1048576)} MB.`;
  return '';
}
export function emergencyMediaError(steps) {
  for (const step of steps) {
    if (step.imageUrl) return 'Replace the legacy image link with a direct upload, or remove it.';
    for (const item of step.media || []) {
      if (!item.asset_id) return 'Replace external emergency media links with direct file uploads.';
      if (!item.title?.trim()) return 'Add a title for every media file.';
      if (item.kind === 'video' && !meaningfulVideoDescription(item.description))
        return 'Describe the actual actions demonstrated in every video (at least six words and 30 characters).';
    }
  }
  return '';
}
