"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import {
  Flex,
  Text,
  Button,
  Input,
  Stack,
  Field,
} from "@chakra-ui/react";

import AdminLayout from "../../../../components/layouts/AdminLayout";
import TiptapEditor from "../../../../components/editor/TipTapEditor";

import { usePrototype, guideCategories } from "@/components/PrototypeProvider";
import { toaster } from "@/components/ui/toaster";

export default function CreateArticlePage() {
  return <Suspense fallback={<AdminLayout title="Learn Cards"><Text>Loading editor...</Text></AdminLayout>}><GuideEditorRoute /></Suspense>;
}

function GuideEditorRoute() {
  const searchParams = useSearchParams();
  const { cards } = usePrototype();
  const editId = searchParams.get("edit");
  const guide = cards.find((card) => card.id === editId);
  if (editId && !guide) {
    return <MissingGuide />;
  }
  return <GuideForm key={editId || "new"} guide={guide} />;
}

function MissingGuide() {
  const router = useRouter();
  return <AdminLayout title="Guide unavailable"><Text mb={4}>This local guide is no longer available. Reloading resets prototype data.</Text><Button onClick={() => router.push("/user/learn-cards")}>Back to Learn Cards</Button></AdminLayout>;
}

function GuideForm({ guide }) {
  const router = useRouter();

  const { setCards } = usePrototype();
  const [title, setTitle] = useState(guide?.title || "");
  const [category, setCategory] = useState(guide?.category || guideCategories[0]);
  const [editorHTML, setEditorHTML] = useState(guide?.content || "<p></p>");
  const [error, setError] = useState("");

  const handleSave = (status) => {
    if (!title.trim()) {
      setError("Enter a guide title before saving.");
      return;
    }
    const saved = {
      id: guide?.id || crypto.randomUUID(),
      title: title.trim(), category, content: editorHTML, status,
      updatedAt: new Date().toLocaleDateString("en-GB"),
    };
    setCards((previous) => guide
      ? previous.map((card) => card.id === guide.id ? saved : card)
      : [...previous, saved]);
    toaster.create({ title: status === "Draft" ? "Draft saved locally" : "Guide marked published locally", type: "success" });
    router.push("/user/learn-cards");
  };

  return (
    <AdminLayout
      title={guide ? "Edit Guide" : "Create Guide"}
      description="Write a maintenance guide. Drafts and publish status are saved only for this session."
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
              {guideCategories.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </Field.Root>

          <Flex gap={2} align="flex-end" wrap="wrap">
            <Button
              type="button"
              variant="outline"
              onClick={() => router.push("/user/learn-cards")}
            >
              Cancel
            </Button>

            <Button
              type="button"
              variant="outline"
              colorPalette="gray"
              onClick={() => handleSave("Draft")}
            >
              Save Draft
            </Button>

            <Button
              type="button"
              colorPalette="blue"
              onClick={() => handleSave("Published")}
            >
              Publish
            </Button>
          </Flex>
        </Flex>

        {/* ========================= */}
        {/* Article Title              */}
        {/* ========================= */}

        {error && <Text role="alert" color="red.600">{error}</Text>}
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

        {/* ========================= */}
        {/* Content Editor             */}
        {/* ========================= */}

        <Field.Root flex={1} display="flex" flexDirection="column">
          <Field.Label fontWeight="semibold">Content</Field.Label>

          <TiptapEditor
            content={editorHTML}
            onChange={(html) => setEditorHTML(html)}
          />
        </Field.Root>
      </Stack>
    </AdminLayout>
  );
}
