"use client";

import { Checkbox } from "@/components/ui/checkbox";

import { AdminSelect } from "@/components/admin/NativeControls";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import {
  Fieldset,
  Flex,
  Text,
  Button,
  Input,
  Stack,
  Field,
  Textarea,
} from "@chakra-ui/react";

import AdminLayout from "../../../../components/layouts/AdminLayout";
import TiptapEditor from "../../../../components/editor/TipTapEditor";

import { useContent } from "@/components/ContentProvider";
import { toaster } from "@/components/ui/toaster";
import { uploadGuideImage } from "@/api/guides.mjs";
import { hasGuideContent } from "@/lib/guideContent.mjs";
import { listAll } from "@/api/client.mjs";
import useUnsavedChanges from "@/components/admin/useUnsavedChanges";

export default function CreateArticlePage() {
  return (
    <Suspense
      fallback={
        <AdminLayout title="Learning guides">
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
  if (loading) return <AdminLayout title="Learning guides" />;
  const guide = cards.find((card) => card.id === editId);
  if (editId && !guide) {
    return error ? <AdminLayout title="Learning guides" /> : <MissingGuide />;
  }
  return <GuideForm key={editId || "new"} guide={guide} />;
}

function MissingGuide() {
  const router = useRouter();
  return (
    <AdminLayout title="Guide unavailable">
      <Text mb={4}>This guide is no longer available.</Text>
      <Button onClick={() => router.push("/user/learn-cards")}>
        Back to Learning guides
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
  const [category, setCategory] = useState(guide?.category_id || "");
  const [editorHTML, setEditorHTML] = useState(guide?.content || "<p></p>");
  const [error, setError] = useState("");
  const [description, setDescription] = useState(guide?.description || "");
  const [readingMinutes, setReadingMinutes] = useState(
    guide?.reading_minutes || "",
  );
  const [displayOrder, setDisplayOrder] = useState(guide?.display_order || 0);
  const [relatedLessons, setRelatedLessons] = useState(
    guide?.related_lesson_ids || [],
  );
  const [relatedItems, setRelatedItems] = useState(
    guide?.maintenance_item_ids || [],
  );
  const [items, setItems] = useState([]);
  const changed =
    title !== (guide?.title || "") ||
    category !== (guide?.category_id || "") ||
    editorHTML !== (guide?.content || "<p></p>") ||
    description !== (guide?.description || "") ||
    String(readingMinutes) !== String(guide?.reading_minutes || "") ||
    displayOrder !== (guide?.display_order || 0) ||
    JSON.stringify(relatedLessons) !==
      JSON.stringify(guide?.related_lesson_ids || []) ||
    JSON.stringify(relatedItems) !==
      JSON.stringify(guide?.maintenance_item_ids || []);
  useUnsavedChanges(changed && !saving);
  useEffect(() => {
    let active = true;
    listAll("/admin/maintenance-items")
      .then((rows) => {
        if (active) setItems(rows);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, []);

  async function persist(status) {
    if (!title.trim())
      throw new Error(
        "Enter a guide title before saving or uploading an image.",
      );
    if (status === "published" && !hasGuideContent(editorHTML)) {
      throw new Error(
        "Add content before publishing. You can save an empty draft.",
      );
    }
    if (
      readingMinutes &&
      (!Number.isInteger(Number(readingMinutes)) || Number(readingMinutes) <= 0)
    )
      throw new Error(
        "Reading time must be a positive whole number of minutes.",
      );
    if (!Number.isInteger(displayOrder) || displayOrder < 0)
      throw new Error("Display order must be a non-negative whole number.");
    const saved = await saveGuide(guideId, {
      title: title.trim(),
      category_id: category || null,
      content: editorHTML,
      status,
      description,
      display_order: displayOrder,
      reading_minutes: readingMinutes ? Number(readingMinutes) : null,
      related_lesson_ids: relatedLessons,
      maintenance_item_ids: relatedItems,
    });
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
      toaster.create({
        title: status === "draft" ? "Draft saved" : "Guide published",
        type: "success",
      });
      router.push("/user/learn-cards");
    } catch (error) {
      setError(error.message);
    } finally {
      busy.current = false;
      setSaving(false);
    }
  }

  async function uploadImage(file) {
    if (busy.current)
      throw new Error("Wait for the current save or upload to finish.");
    busy.current = true;
    setSaving(true);
    try {
      const id = guideId || (await persist("draft"));
      return (await uploadGuideImage(id, file)).url;
    } finally {
      busy.current = false;
      setSaving(false);
    }
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

            <AdminSelect
              aria-label="Category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="">Uncategorized</option>
              {categories.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </AdminSelect>
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
                  editorHTML !== (guide?.content || "<p></p>") ||
                  description !== (guide?.description || "") ||
                  String(readingMinutes) !==
                    String(guide?.reading_minutes || "") ||
                  displayOrder !== (guide?.display_order || 0) ||
                  JSON.stringify(relatedLessons) !==
                    JSON.stringify(guide?.related_lesson_ids || []) ||
                  JSON.stringify(relatedItems) !==
                    JSON.stringify(guide?.maintenance_item_ids || []);
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
              colorPalette="brand"
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

        <Field.Root>
          <Field.Label>Introduction / description</Field.Label>
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </Field.Root>
        <Field.Root>
          <Field.Label>Optional reading time (minutes)</Field.Label>
          <Input
            type="number"
            min={1}
            maxW="180px"
            value={readingMinutes}
            onChange={(e) => setReadingMinutes(e.target.value)}
          />
        </Field.Root>
        <Field.Root>
          <Field.Label>Display order</Field.Label>
          <Input
            type="number"
            min={0}
            step={1}
            maxW="180px"
            value={displayOrder}
            onChange={(event) => setDisplayOrder(Number(event.target.value))}
          />
          <Field.HelperText>
            Lower numbers appear first within the mobile learning category.
          </Field.HelperText>
        </Field.Root>
        <Fieldset.Root disabled={saving}>
          <Stack gap={2}>
            <Text fontWeight="semibold">Related learning cards</Text>
            {cards
              .filter((card) => card.id !== guideId)
              .map((card) => (
                <Checkbox
                  key={card.id}
                  checked={relatedLessons.includes(card.id)}
                  onCheckedChange={(e) =>
                    setRelatedLessons(
                      e.checked === true
                        ? [...relatedLessons, card.id]
                        : relatedLessons.filter((id) => id !== card.id),
                    )
                  }
                >
                  {card.title} ({card.status})
                </Checkbox>
              ))}
            <Text fontWeight="semibold" mt={2}>
              Related standard maintenance items
            </Text>
            {items.map((item) => (
              <Checkbox
                key={item.id}
                checked={relatedItems.includes(item.id)}
                onCheckedChange={(e) =>
                  setRelatedItems(
                    e.checked === true
                      ? [...relatedItems, item.id]
                      : relatedItems.filter((id) => id !== item.id),
                  )
                }
              >
                {item.title} ({item.action}){!item.active ? " · inactive" : ""}
              </Checkbox>
            ))}
            {!items.length && (
              <Text fontSize="sm">
                Create standard maintenance items to add relationships. Existing
                relationship IDs are retained.
              </Text>
            )}
          </Stack>
        </Fieldset.Root>

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
