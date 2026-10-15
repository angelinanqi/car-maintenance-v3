"use client";
import { useState } from "react";
import {
  Button,
  Stack,
  Input,
  Flex,
  Text,
  Heading,
  Textarea,
} from "@chakra-ui/react";
import AdminLayout from "@/components/layouts/AdminLayout";
import { useContent } from "@/components/ContentProvider";
import DeleteConfirmModal from "@/components/modals/DeleteConfirmModal";

const empty = { name: "", description: "", display_order: 0, published: false };
export default function CategoriesPage() {
  const { categories, saveCategory, deleteCategory } = useContent();
  const [draft, setDraft] = useState(empty);
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function save(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await saveCategory(editing, draft);
      setEditing(null);
      setDraft(empty);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <AdminLayout
      title="Learning Categories"
      description="Manage descriptions, display order and publication. Unpublished categories hide their lessons from public readers."
    >
      <Stack gap={5}>
        <Heading size="md">
          {editing ? "Edit category" : "Add category"}
        </Heading>
        <form onSubmit={save}>
          <fieldset disabled={busy}>
            <Stack gap={3}>
              <label>
                Name
                <Input
                  value={draft.name}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                  required
                />
              </label>
              <label>
                Description
                <Textarea
                  value={draft.description}
                  onChange={(e) =>
                    setDraft({ ...draft, description: e.target.value })
                  }
                />
              </label>
              <label>
                Display order
                <Input
                  type="number"
                  min={0}
                  value={draft.display_order}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      display_order: Number(e.target.value),
                    })
                  }
                />
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={draft.published}
                  onChange={(e) =>
                    setDraft({ ...draft, published: e.target.checked })
                  }
                />{" "}
                Publish learning category
              </label>
              <Flex gap={3}>
                <Button type="submit" loading={busy}>
                  Save category
                </Button>
                {editing && (
                  <Button
                    type="button"
                    onClick={() => {
                      setEditing(null);
                      setDraft(empty);
                    }}
                  >
                    Cancel
                  </Button>
                )}
              </Flex>
            </Stack>
          </fieldset>
        </form>
        {error && (
          <Text role="alert" color="red.600">
            {error}
          </Text>
        )}
        {[...categories]
          .sort((a, b) => a.display_order - b.display_order)
          .map((category) => (
            <Flex key={category.id} gap={3} align="center" wrap="wrap">
              <Text flex={1}>
                {category.display_order} · {category.name} ·{" "}
                {category.published ? "Published" : "Draft"}
              </Text>
              <Button
                disabled={busy}
                variant="outline"
                onClick={() => {
                  setEditing(category.id);
                  setDraft({
                    name: category.name,
                    description: category.description,
                    display_order: category.display_order,
                    published: category.published,
                  });
                }}
              >
                Edit
              </Button>
              <Button
                disabled={busy}
                variant="outline"
                colorPalette="red"
                onClick={() => setDeleting(category)}
              >
                Remove
              </Button>
            </Flex>
          ))}
        {!categories.length && <Text>No categories yet.</Text>}
      </Stack>
      <DeleteConfirmModal
        isOpen={Boolean(deleting)}
        itemName={deleting?.name}
        onClose={() => setDeleting(null)}
        onConfirm={async () => {
          try {
            await deleteCategory(deleting.id);
            setDeleting(null);
            setError("");
          } catch (e) {
            setError(e.message);
            setDeleting(null);
          }
        }}
      />
    </AdminLayout>
  );
}
