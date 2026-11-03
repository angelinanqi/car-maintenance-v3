"use client";

import { useEffect, useState } from "react";
import { Box, Button, Field, Input, Stack, Text, Textarea, Flex } from "@chakra-ui/react";
import { Checkbox } from "@/components/ui/checkbox";
import { AdminSelect } from "./NativeControls";

const newMedia = (kind, url = "", section_id = null) => ({
  id: crypto.randomUUID(), kind, url, title: "", description: "", vehicle_context: "",
  source_reference: "", section_id, reviewed: false, start_seconds: 0, transcript: [],
});

export default function ContentMediaEditor({ value = [], onChange, content, examples = [], imageUrl, uploadImage }) {
  const [sections, setSections] = useState([]);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const limit = content === undefined ? 10 : 30;
  useEffect(() => {
    const document = new DOMParser().parseFromString(content || "", "text/html");
    setSections([...document.querySelectorAll("h2[data-section-id]")].map(heading => ({
      id: heading.getAttribute("data-section-id"), title: heading.textContent,
    })));
  }, [content]);
  function update(id, patch) {
    onChange(value.map(item => item.id === id ? { ...item, ...patch, reviewed: false } : item));
  }
  function discover() {
    const found = [];
    for (const html of [content || "", ...examples]) {
      const document = new DOMParser().parseFromString(html, "text/html");
      let sectionId = null;
      for (const element of document.querySelectorAll("h2, img, iframe")) {
        if (element.tagName === "H2") { sectionId = element.getAttribute("data-section-id"); continue; }
        const url = element.getAttribute("src");
        if (!url || [...value, ...found].some(item => item.url === url)) continue;
        found.push({ ...newMedia(element.tagName === "IMG" ? "image" : "video", url, sectionId), title: element.getAttribute("alt") || element.getAttribute("title") || "" });
      }
    }
    if (imageUrl && ![...value, ...found].some(item => item.url === imageUrl)) found.push(newMedia("image", imageUrl));
    if (value.length + found.length > limit) { setError(`Keep up to ${limit} media items.`); return; }
    onChange([...value, ...found]); setError(found.length ? "" : "No new attached media found.");
  }
  return <Box borderWidth="1px" borderRadius="lg" p={4}><Stack gap={4}>
    <Text fontWeight="semibold">Media for learning and chat</Text>
    <Text fontSize="sm">Describe what each image or video teaches, including essential visual actions and vehicle applicability. Only reviewed descriptions and transcripts are searchable. Keep emergency instructions complete in the written steps.</Text>
    <Flex gap={2} wrap="wrap">
      {(content !== undefined || imageUrl) && <Button type="button" size="sm" variant="outline" onClick={discover}>Add existing images and videos</Button>}
      {["image", "video"].map(kind => <Button key={kind} type="button" size="sm" variant="outline" disabled={value.length >= limit} onClick={() => onChange([...value, newMedia(kind)])}>Add {kind} link</Button>)}
    </Flex>
    {uploadImage && <Field.Root><Field.Label>Upload an image</Field.Label><Input type="file" accept="image/png,image/jpeg,image/webp,image/gif" disabled={uploading || value.length >= limit} onChange={async event => {
      const file = event.target.files?.[0]; event.target.value = ""; if (!file) return;
      setUploading(true); setError("");
      try { const url = await uploadImage(file); onChange([...value, { ...newMedia("image", url), title: file.name }]); }
      catch (error) { setError(error.message); } finally { setUploading(false); }
    }} /></Field.Root>}
    {error && <Text role="alert" color="red.600">{error}</Text>}
    {value.map((item, index) => <Box key={item.id} borderWidth="1px" borderRadius="md" p={4}><Stack gap={3}>
      <Flex justify="space-between"><Text fontWeight="semibold">{index + 1}. {item.kind === "image" ? "Image" : "Video"}</Text><Button type="button" size="xs" variant="outline" onClick={() => onChange(value.filter(media => media.id !== item.id))}>Remove media</Button></Flex>
      {[["title", "Title / caption", 200], ["url", "Media URL", 2048]].map(([key, label, max]) => <Field.Root required key={key}><Field.Label>{label}</Field.Label><Input type={key === "url" ? "url" : "text"} maxLength={max} value={item[key]} onChange={event => update(item.id, { [key]: event.target.value })} /></Field.Root>)}
      {content !== undefined && <Field.Root><Field.Label>Related guide section</Field.Label><AdminSelect value={item.section_id || ""} onChange={event => update(item.id, { section_id: event.target.value || null })}>
        <option value="">Whole guide</option>
        {item.section_id && !sections.some(section => section.id === item.section_id) && <option value={item.section_id}>Removed section — select another</option>}
        {sections.map(section => <option key={section.id} value={section.id}>{section.title}</option>)}
      </AdminSelect></Field.Root>}
      <Field.Root><Field.Label>Description and purpose</Field.Label><Textarea rows={3} maxLength={4000} placeholder="Explain what is visible and what the learner should understand." value={item.description} onChange={event => update(item.id, { description: event.target.value })} /></Field.Root>
      {[["vehicle_context", "Vehicle applicability (optional)", 500], ["source_reference", "Source / attribution (optional)", 2000]].map(([key, label, max]) => <Field.Root key={key}><Field.Label>{label}</Field.Label><Input maxLength={max} value={item[key]} onChange={event => update(item.id, { [key]: event.target.value })} /></Field.Root>)}
      {item.kind === "video" && <Stack gap={3}>
        <Field.Root><Field.Label>Start time (seconds)</Field.Label><Input type="number" min={0} max={86400} step={1} value={item.start_seconds} onChange={event => update(item.id, { start_seconds: Number(event.target.value) })} /></Field.Root>
        <Text fontSize="sm">Optional transcript segments: use increasing timestamps and include visual actions missing from the narration.</Text>
        {item.transcript.map((segment, segmentIndex) => <Box key={segmentIndex} borderLeftWidth="2px" pl={3}><Stack gap={2}>
          <Field.Root><Field.Label>Segment {segmentIndex + 1} start (seconds)</Field.Label><Input type="number" min={0} max={86400} step={1} value={segment.start_seconds} onChange={event => update(item.id, { transcript: item.transcript.map((part, i) => i === segmentIndex ? { ...part, start_seconds: Number(event.target.value) } : part) })} /></Field.Root>
          <Field.Root><Field.Label>Transcript / visual actions</Field.Label><Textarea maxLength={4000} value={segment.text} onChange={event => update(item.id, { transcript: item.transcript.map((part, i) => i === segmentIndex ? { ...part, text: event.target.value } : part) })} /></Field.Root>
          <Button type="button" size="xs" variant="outline" alignSelf="start" onClick={() => update(item.id, { transcript: item.transcript.filter((_, i) => i !== segmentIndex) })}>Remove segment</Button>
        </Stack></Box>)}
        <Button type="button" size="sm" variant="outline" alignSelf="start" disabled={item.transcript.length >= 100} onClick={() => update(item.id, { transcript: [...item.transcript, { start_seconds: item.transcript.length ? Math.min(86400, item.transcript.at(-1).start_seconds + 30) : item.start_seconds, text: "" }] })}>Add transcript segment</Button>
      </Stack>}
      <Checkbox checked={item.reviewed} disabled={!item.description.trim() || !item.title.trim() || !item.url.trim()} onCheckedChange={event => onChange(value.map(media => media.id === item.id ? { ...media, reviewed: event.checked === true } : media))}>I reviewed this description and transcript for chatbot use</Checkbox>
      <Text fontSize="xs" color="muted">Editing clears the review. Save and publish the parent guide or emergency playbook to make reviewed media available.</Text>
    </Stack></Box>)}
  </Stack></Box>;
}
