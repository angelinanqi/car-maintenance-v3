"use client";

import { useEffect, useState } from "react";
import NextLink from "next/link";
import {
  Box,
  Button,
  Flex,
  Heading,
  Input,
  Stack,
  Table,
  Text,
  Textarea,
} from "@chakra-ui/react";
import AdminLayout from "@/components/layouts/AdminLayout";
import FormField from "@/components/admin/FormField";
import { loadItems, saveItem, type MaintenanceItem } from "@/api/admin";
import { listAll } from "@/api/client.mjs";

type Guide = { id: string; title: string; maintenance_item_ids: string[] };
const empty = {
  title: "",
  category: "",
  description: "",
  action: "replace" as MaintenanceItem["action"],
  active: true,
};

export default function MaintenanceItemsPage() {
  const [items, setItems] = useState<MaintenanceItem[]>([]);
  const [guides, setGuides] = useState<Guide[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [id, setId] = useState("");
  const [draft, setDraft] = useState(empty);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function reload() {
    const result = await Promise.all([
      loadItems(),
      listAll("/guides", { include_drafts: "true" }),
    ]);
    setItems(result[0]);
    setGuides(result[1]);
    setLoaded(true);
  }
  useEffect(() => {
    let active = true;
    Promise.all([loadItems(), listAll("/guides", { include_drafts: "true" })])
      .then(([rows, cards]) => {
        if (active) {
          setItems(rows);
          setGuides(cards);
          setLoaded(true);
        }
      })
      .catch((e: Error) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, []);
  const visible = items.filter(
    (row) =>
      (!category || row.category === category) &&
      `${row.title} ${row.description}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );

  return (
    <AdminLayout
      title="Standard Maintenance Items"
      description="Manage shared operations. Personal custom items and service histories remain separate."
    >
      <Stack gap={5}>
        {error && (
          <Text role="alert" color="red.700">
            {error}
          </Text>
        )}
        <Button
          alignSelf="start"
          variant="outline"
          onClick={() =>
            reload()
              .then(() => setError(""))
              .catch((e: Error) => setError(e.message))
          }
        >
          Reload items
        </Button>
        {!loaded && !error && <Text>Loading standard items…</Text>}
        {loaded && (
          <>
            <Box p={4} borderWidth="1px" borderRadius="md">
              <Heading size="md" mb={3}>
                {id ? "Edit standard item" : "Create standard item"}
              </Heading>
              <form
                onSubmit={async (event) => {
                  event.preventDefault();
                  if (busy) return;
                  setBusy(true);
                  setError("");
                  try {
                    await saveItem(id, draft);
                    setId("");
                    setDraft(empty);
                    await reload();
                  } catch (e) {
                    setError((e as Error).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                <fieldset disabled={busy}>
                  <Stack gap={3}>
                    <FormField label="Title">
                      <Input
                        required
                        value={draft.title}
                        onChange={(e) =>
                          setDraft({ ...draft, title: e.target.value })
                        }
                      />
                    </FormField>
                    <FormField label="Category">
                      <Input
                        value={draft.category}
                        onChange={(e) =>
                          setDraft({ ...draft, category: e.target.value })
                        }
                      />
                    </FormField>
                    <FormField label="Action">
                      <select
                        disabled={Boolean(id)}
                        value={draft.action}
                        onChange={(e) =>
                          setDraft({
                            ...draft,
                            action: e.target.value as MaintenanceItem["action"],
                          })
                        }
                      >
                        <option value="inspect">Inspection</option>
                        <option value="replace">Replacement</option>
                        <option value="service">Other service</option>
                      </select>
                    </FormField>
                    <FormField label="Description">
                      <Textarea
                        value={draft.description}
                        onChange={(e) =>
                          setDraft({ ...draft, description: e.target.value })
                        }
                      />
                    </FormField>
                    <label>
                      <input
                        type="checkbox"
                        checked={draft.active}
                        onChange={(e) =>
                          setDraft({ ...draft, active: e.target.checked })
                        }
                      />{" "}
                      Active for new schedules
                    </label>
                    <Text fontSize="sm">
                      Deactivate obsolete items to preserve their IDs and
                      history. Edit a learning card to manage its maintenance
                      relationships.
                    </Text>
                    <Flex gap={3}>
                      <Button type="submit">Save item</Button>
                      {id && (
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => {
                            setId("");
                            setDraft(empty);
                          }}
                        >
                          Cancel edit
                        </Button>
                      )}
                    </Flex>
                  </Stack>
                </fieldset>
              </form>
            </Box>
            <Flex gap={3} wrap="wrap">
              <Input
                maxW="400px"
                aria-label="Search items"
                placeholder="Search standard items"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <FormField label="Category filter">
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                >
                  <option value="">All categories</option>
                  {[...new Set(items.map((r) => r.category))]
                    .filter(Boolean)
                    .map((value) => (
                      <option key={value}>{value}</option>
                    ))}
                </select>
              </FormField>
            </Flex>
            <Table.ScrollArea>
              <Table.Root minW="640px">
                <Table.Header>
                  <Table.Row>
                    {[
                      "Item",
                      "Action",
                      "Status",
                      "Related learning",
                      "Edit",
                    ].map((label) => (
                      <Table.ColumnHeader key={label}>
                        {label}
                      </Table.ColumnHeader>
                    ))}
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {visible.map((row) => (
                    <Table.Row key={row.id}>
                      <Table.Cell>
                        {row.title}
                        <Text fontSize="xs">{row.category}</Text>
                      </Table.Cell>
                      <Table.Cell>{row.action}</Table.Cell>
                      <Table.Cell>
                        {row.active ? "Active" : "Inactive"}
                      </Table.Cell>
                      <Table.Cell>
                        <Stack gap={1}>
                          {guides
                            .filter((g) =>
                              g.maintenance_item_ids?.includes(row.id),
                            )
                            .map((guide) => (
                              <NextLink
                                key={guide.id}
                                href={`/user/learn-cards/create?edit=${guide.id}`}
                                style={{ textDecoration: "underline" }}
                              >
                                {guide.title}
                              </NextLink>
                            ))}
                        </Stack>
                      </Table.Cell>
                      <Table.Cell>
                        <Button
                          disabled={busy}
                          size="sm"
                          onClick={() => {
                            setId(row.id);
                            setDraft({
                              title: row.title,
                              category: row.category,
                              description: row.description,
                              action: row.action,
                              active: row.active,
                            });
                          }}
                        >
                          Edit
                        </Button>
                      </Table.Cell>
                    </Table.Row>
                  ))}
                </Table.Body>
              </Table.Root>
            </Table.ScrollArea>
            {!visible.length && (
              <Text>No matching standard maintenance items.</Text>
            )}
          </>
        )}
      </Stack>
    </AdminLayout>
  );
}
