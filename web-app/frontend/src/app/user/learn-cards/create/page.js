"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import {
  Flex,
  Box,
  Heading,
  Button,
  Input,
  Stack,
  Field,
} from "@chakra-ui/react";

import AdminLayout from "../../../../components/layouts/AdminLayout";
import TiptapEditor from "../../../../components/editor/TipTapEditor";

export default function CreateArticlePage() {
  const router = useRouter();

  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("Tutorials");
  const [editorHTML, setEditorHTML] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const handleSave = async (status = "Published") => {
    if (!title.trim()) {
      alert("Please enter an article title.");
      return;
    }

    setIsSaving(true);

    console.log("Saved Article:", {
      title,
      category,
      content: editorHTML,
      status,
    });

    setIsSaving(false);

    router.push("/admin/content");
  };

  return (
    <AdminLayout
      title="Create Article"
      description="Write and format a short article for your readers."
    >
      <Stack gap={6} w="100%" h="100%">
        {/* ========================= */}
        {/* Top Action Bar             */}
        {/* ========================= */}

        <Flex justify="space-between" align="center" wrap="wrap" gap={4}>
          <Field.Root maxW="220px">
            <Field.Label fontStyle="normal">Category</Field.Label>

            <select
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
              <option value="Tutorials">Tutorials</option>

              <option value="Documentation">Documentation</option>

              <option value="Updates">Updates</option>
            </select>
          </Field.Root>

          <Flex gap={2} align="flex-end">
            <Button
              type="button"
              variant="outline"
              disabled={isSaving}
              onClick={() => router.back()}
            >
              Cancel
            </Button>

            <Button
              type="button"
              variant="outline"
              colorPalette="gray"
              loading={isSaving}
              onClick={() => handleSave("Draft")}
            >
              Save Draft
            </Button>

            <Button
              type="button"
              colorPalette="blue"
              loading={isSaving}
              onClick={() => handleSave("Published")}
            >
              Publish
            </Button>
          </Flex>
        </Flex>

        {/* ========================= */}
        {/* Article Title              */}
        {/* ========================= */}

        <Field.Root required>
          <Field.Label fontWeight="semibold">Article Title</Field.Label>

          <Input
            placeholder="e.g. 5 Quick Tips for Next.js 15"
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
