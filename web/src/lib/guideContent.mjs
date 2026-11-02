export function hasGuideContent(html) {
  if (/<(?:img|iframe)\b[^>]*\bsrc=["'][^"']+["']/i.test(html)) return true;
  return Boolean(
    html
      .replace(/<[^>]*>/g, "")
      .replace(/&nbsp;|&#160;|&#xA0;/gi, " ")
      .trim(),
  );
}
