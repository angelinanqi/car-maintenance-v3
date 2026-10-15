"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { Flex, Text, Button, Input, Stack, Field, Textarea } from "@chakra-ui/react";

import AdminLayout from "../../../../components/layouts/AdminLayout";
import TiptapEditor from "../../../../components/editor/TipTapEditor";

import { useContent } from "@/components/ContentProvider";
import { toaster } from "@/components/ui/toaster";
import { uploadGuideImage } from "@/api/guides.mjs";
import { hasGuideContent } from "@/lib/guideContent.mjs";
import { listAll } from "@/api/client.mjs";

export default function CreateArticlePage() {
  return (
    <Suspense
      fallback={
        <AdminLayout title="Learn Cards">
          <Text>Loading editor...</Text>
        </AdminLayout>
      }
    >
      <GuideEditorRoute />
    </Suspense>
  );
}

function GuideEditorRoute() {
  const searchParams = useSearchParams();
  const { cards, loading, error } = useContent();
  const editId = searchParams.get("edit");
  if (loading) return <AdminLayout title="Learn Cards" />;
  const guide = cards.find((card) => card.id === editId);
  if (editId && !guide) {
    return error ? <AdminLayout title="Learn Cards" /> : <MissingGuide />;
  }
  return <GuideForm key={editId || "new"} guide={guide} />;
}

function MissingGuide() {
  const router = useRouter();
  return (
    <AdminLayout title="Guide unavailable">
      <Text mb={4}>
        This guide is no longer available.
      </Text>
      <Button onClick={() => router.push("/user/learn-cards")}>
        Back to Learn Cards
      </Button>
    </AdminLayout>
  );
}

function GuideForm({ guide }) {
  const router = useRouter();

  const { saveGuide, categories, cards } = useContent();
  const [guideId, setGuideId] = useState(guide?.id || null);
  const [saving, setSaving] = useState(false);
  const busy = useRef(false);
  const [title, setTitle] = useState(guide?.title || "");
  const [category, setCategory] = useState(
    guide?.category_id || "",
  );
  const [editorHTML, setEditorHTML] = useState(guide?.content || "<p></p>");
  const [error, setError] = useState("");
  const [description, setDescription] = useState(guide?.description || "");
  const [readingMinutes, setReadingMinutes] = useState(guide?.reading_minutes || "");
  const [relatedLessons, setRelatedLessons] = useState(guide?.related_lesson_ids || []);
  const [relatedItems, setRelatedItems] = useState(guide?.maintenance_item_ids || []);
  const [items, setItems] = useState([]);
  useEffect(() => {
    let active = true;
    listAll("/admin/maintenance-items").then((rows) => { if (active) setItems(rows); }).catch((e) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, []);

  async function persist(status) {
    if (!title.trim()) throw new Error("Enter a guide title before saving or uploading an image.");
    if (status === "published" && !hasGuideContent(editorHTML)) {
      throw new Error("Add content before publishing. You can save an empty draft.");
    }
    if (readingMinutes && (!Number.isInteger(Number(readingMinutes)) || Number(readingMinutes) <= 0)) throw new Error("Reading time must be a positive whole number of minutes.");
    const saved = await saveGuide(guideId, { title: title.trim(), category_id: category || null, content: editorHTML, status,
      description, reading_minutes: readingMinutes ? Number(readingMinutes) : null,
      related_lesson_ids: relatedLessons, maintenance_item_ids: relatedItems });
    setGuideId(saved.id);
    return saved.id;
  }

  async function handleSave(status) {
    if (busy.current) return;
    busy.current = true;
    setSaving(true);
    setError("");
    try {
      await persist(status);
      toaster.create({ title: status === "draft" ? "Draft saved" : "Guide published", type: "success" });
      router.push("/user/learn-cards");
    } catch (error) { setError(error.message); }
    finally { busy.current = false; setSaving(false); }
  }

  async function uploadImage(file) {
    if (busy.current) throw new Error("Wait for the current save or upload to finish.");
    busy.current = true;
    setSaving(true);
    try {
      const id = guideId || await persist("draft");
      return (await uploadGuideImage(id, file)).url;
    } finally { busy.current = false; setSaving(false); }
  }

  return (
    <AdminLayout
      title={guide ? "Edit Guide" : "Create Guide"}
      description="Write a maintenance guide. Images are uploaded to persistent storage; the first image upload creates a draft."
    >
      <Stack gap={6} w="100%" h="100%">
        {/* ========================= */}
        {/* Top Action Bar             */}
        {/* ========================= */}

        <Flex justify="space-between" align="center" wrap="wrap" gap={4}>
          <Field.Root maxW="220px">
            <Field.Label fontStyle="normal">Category</Field.Label>

            <select
              aria-label="Category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: "6px",
                border: "1px solid #E2E8F0",
                backgroundColor: "#fff",
              }}
            >
              <option value="">Uncategorized</option>
              {categories.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </Field.Root>

          <Flex gap={2} align="flex-end" wrap="wrap">
            <Button
              type="button"
              variant="outline"
              disabled={saving}
              onClick={() => {
                const changed =
                  title !== (guide?.title || "") ||
                  category !== (guide?.category_id || "") ||
                  editorHTML !== (guide?.content || "<p></p>") || description !== (guide?.description || "") ||
                  String(readingMinutes) !== String(guide?.reading_minutes || "") ||
                  JSON.stringify(relatedLessons) !== JSON.stringify(guide?.related_lesson_ids || []) ||
                  JSON.stringify(relatedItems) !== JSON.stringify(guide?.maintenance_item_ids || []);
                if (
                  !changed ||
                  window.confirm("Discard unsaved guide changes?")
                )
                  router.push("/user/learn-cards");
              }}
            >
              Cancel
            </Button>

            <Button
              type="button"
              variant="outline"
              colorPalette="gray"
              onClick={() => handleSave("draft")}
              loading={saving}
            >
              Save Draft
            </Button>

            <Button
              type="button"
              colorPalette="blue"
              onClick={() => handleSave("published")}
              loading={saving}
            >
              Publish
            </Button>
          </Flex>
        </Flex>

        {/* ========================= */}
        {/* Article Title              */}
        {/* ========================= */}

        {error && (
          <Text role="alert" color="red.600">
            {error}
          </Text>
        )}
        <Field.Root required invalid={Boolean(error)}>
          <Field.Label fontWeight="semibold">Guide Title</Field.Label>

          <Input
            placeholder="e.g. 5 Quick Tips for Long Trips"
            size="lg"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            bg="white"
          />
        </Field.Root>

        <label>Introduction / description<Textarea value={description} onChange={(e) => setDescription(e.target.value)} /></label>
        <label>Optional reading time (minutes)<Input type="number" min={1} maxW="180px" value={readingMinutes} onChange={(e) => setReadingMinutes(e.target.value)} /></label>
        <fieldset disabled={saving}><Stack gap={2}>
          <Text fontWeight="semibold">Related learning cards</Text>
          {cards.filter((card) => card.id !== guideId).map((card) => <label key={card.id}><input type="checkbox" checked={relatedLessons.includes(card.id)} onChange={(e) => setRelatedLessons(e.target.checked ? [...relatedLessons, card.id] : relatedLessons.filter((id) => id !== card.id))} /> {card.title} ({card.status})</label>)}
          <Text fontWeight="semibold" mt={2}>Related standard maintenance items</Text>
          {items.map((item) => <label key={item.id}><input type="checkbox" checked={relatedItems.includes(item.id)} onChange={(e) => setRelatedItems(e.target.checked ? [...relatedItems, item.id] : relatedItems.filter((id) => id !== item.id))} /> {item.title} ({item.action}){!item.active ? " · inactive" : ""}</label>)}
          {!items.length && <Text fontSize="sm">Create standard maintenance items to add relationships. Existing relationship IDs are retained.</Text>}
        </Stack></fieldset>

        {/* ========================= */}
        {/* Content Editor             */}
        {/* ========================= */}

        <Field.Root flex={1} display="flex" flexDirection="column">
          <Field.Label fontWeight="semibold">Content</Field.Label>

          <TiptapEditor
            uploadImage={uploadImage}
            content={editorHTML}
            onChange={(html) => setEditorHTML(html)}
          />
        </Field.Root>
      </Stack>
    </AdminLayout>
  );
}
