// Layout may position authorised attachments, but cannot replace the answer text.
export function chatLayout(answer, sections, attachments) {
  const originals = Array.isArray(attachments) ? attachments.filter(Boolean) : [];
  const fallback = { sections: [], remainingAttachments: originals };
  if (!Array.isArray(sections) || !sections.length || sections.length > 16 ||
      sections.some(section => !section || typeof section.text !== 'string' || !section.text.trim()) ||
      sections.map(section => section.text).join('\n\n') !== answer) return fallback;
  const available = new Map(originals.filter(item => typeof item.reference_label === 'string')
    .map(item => [item.reference_label, item]));
  const used = new Set();
  const placed = sections.map(section => {
    const labels = Array.isArray(section.reference_labels) ? section.reference_labels.slice(0, 5) : [];
    const selected = [];
    for (const label of labels) {
      if (typeof label === 'string' && /^V[1-9]\d*$/.test(label) && available.has(label) && !used.has(label)) {
        selected.push(available.get(label));
        used.add(label);
      }
    }
    return { text: section.text, attachments: selected };
  });
  return { sections: placed, remainingAttachments: originals.filter(item => !used.has(item.reference_label)) };
}
