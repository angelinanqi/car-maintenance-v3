"use client";
import Pagination, { usePagination } from "@/components/admin/Pagination";

import { Checkbox } from "@/components/ui/checkbox";
import { useState } from "react";
import {
  Fieldset,
  Field,
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
import CategoryRemovalDialog from "@/components/admin/CategoryRemovalDialog";

const empty = { name: "", description: "", display_order: 0, published: false };
export default function CategoriesPage() {
  const { categories, saveCategory, deleteCategory, archiveCategory, restoreCategory } = useContent();
  const [draft, setDraft] = useState(empty);
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const pagination = usePagination(categories.filter((category) => showArchived || !category.archived)
    .sort((a, b) => a.display_order - b.display_order), String(showArchived));
  async function save(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await saveCategory(editing, draft);
      setEditing(null);
      setDraft(empty);
      setNotice("Learning category saved.");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <AdminLayout
      title="Learning Topics"
      description="Group related guides so drivers can find them. Making a topic available also lets drivers see its published guides."
    >
      <Stack gap={5}>
        {notice && <Text role="status">{notice}</Text>}
        <Heading size="md">
          {editing ? "Edit Learning Topic" : "Add Learning Topic"}
        </Heading>
        <form onSubmit={save}>
          <Fieldset.Root disabled={busy}>
            <Stack gap={3}>
              <Field.Root>
                <Field.Label>Name</Field.Label>
                <Input
                  value={draft.name}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                  required
                />
              </Field.Root>
              <Field.Root>
                <Field.Label>Description</Field.Label>
                <Textarea
                  value={draft.description}
                  onChange={(e) =>
                    setDraft({ ...draft, description: e.target.value })
                  }
                />
              </Field.Root>
              <Field.Root>
                <Field.Label>Display order</Field.Label>
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
              </Field.Root>
              <Checkbox
                checked={draft.published}
                onCheckedChange={(e) =>
                  setDraft({ ...draft, published: e.checked === true })
                }
              >
                Make this topic available to drivers
              </Checkbox>
              <Flex gap={3}>
                <Button type="submit" loading={busy}>
                  Save topic
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
          </Fieldset.Root>
        </form>
        {error && (
          <Text role="alert" color="red.600">
            {error}
          </Text>
        )}
        <Checkbox checked={showArchived} onCheckedChange={(event) => setShowArchived(event.checked === true)}>Show archived topics</Checkbox>
        {pagination.items.map((category) => (
            <Flex key={category.id} gap={3} align="center" wrap="wrap">
              <Text flex={1}>
                {category.display_order} · {category.name} ·{" "}
                {category.archived ? "Archived" : category.published ? "Published" : "Draft"}
              </Text>
              {category.archived ? <Button disabled={busy} variant="outline" onClick={async () => {
                setBusy(true);
                setError("");
                setNotice("");
                try {
                  await restoreCategory(category.id);
                  setNotice("Topic restored as a draft. Publish it and enable it in the chatbot when ready.");
                } catch (cause) { setError(cause.message); }
                finally { setBusy(false); }
              }}>Restore</Button> : <Button
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
              </Button>}
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
        <Pagination {...pagination} label="Learning Topics" />
        {!categories.length && <Text>No categories yet.</Text>}
      </Stack>
      {deleting && <CategoryRemovalDialog
        key={deleting.id}
        category={deleting}
        categories={categories}
        archiveCategory={archiveCategory}
        deleteCategory={deleteCategory}
        onClose={() => setDeleting(null)}
        onComplete={(message) => {
          if (editing === deleting.id) { setEditing(null); setDraft(empty); }
          setDeleting(null);
          setError("");
          setNotice(message);
        }}
      />}
    </AdminLayout>
  );
}
