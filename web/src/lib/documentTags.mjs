export const cleanTag = (value) => value.trim().replace(/\s+/g, " ");
export const tagKey = (value) => cleanTag(value).toLocaleLowerCase("en");

export function uniqueTags(tags) {
  const labels = new Map();
  for (const tag of tags) {
    const key = tagKey(tag);
    if (key && !labels.has(key)) labels.set(key, cleanTag(tag));
  }
  return [...labels.values()];
}

export function documentTagSummary(documents) {
  const labels = new Map();
  for (const document of documents) {
    for (const name of uniqueTags(document.tags || [])) {
      const key = tagKey(name);
      const label = labels.get(key) || { name, count: 0 };
      labels.set(key, { ...label, count: label.count + 1 });
    }
  }
  return [...labels.values()].sort((a, b) => a.name.localeCompare(b.name));
}
