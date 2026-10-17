"use client";

import { Checkbox } from "@/components/ui/checkbox";

import { AdminSelect } from "@/components/admin/NativeControls";

import { useCallback, useEffect, useState } from "react";
import NextLink from "next/link";
import {
  Fieldset,
  Field,
  Box,
  Button,
  Heading,
  Input,
  Stack,
  Text,
  Textarea,
} from "@chakra-ui/react";
import { request } from "@/api/client.mjs";

export default function KnowledgeScopes({ documents, onChanged }) {
  const [data, setData] = useState(null);
  const [documentId, setDocumentId] = useState("");
  const [associations, setAssociations] = useState({
    vehicle_ids: [],
    category_ids: [],
  });
  const [metadata, setMetadata] = useState({
    year: "",
    engine: "",
    variant: "",
    vehicle_independent: false,
    source_fidelity_verified: false,
  });
  const [query, setQuery] = useState("");
  const [videoScope, setVideoScope] = useState("");
  const [videoIds, setVideoIds] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const load = useCallback(async () => {
    setData(await request("/knowledge/manage"));
  }, []);
  useEffect(() => {
    let active = true;
    request("/knowledge/manage")
      .then((result) => {
        if (active) setData(result);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, []);
  async function save(action) {
    if (pending) return;
    setPending(true);
    setError("");
    setNotice("");
    try {
      await action();
      await load();
      await onChanged();
      setNotice("Knowledge scope settings saved.");
    } catch (failure) {
      setError(failure.message);
      await Promise.allSettled([load(), onChanged()]);
    } finally {
      setPending(false);
    }
  }
  function chooseDocument(id) {
    setDocumentId(id);
    const row = documents.find((item) => item.id === id) || {};
    setMetadata({
      year: row.year || "",
      engine: row.engine || "",
      variant: row.variant || "",
      vehicle_independent: row.vehicle_independent || false,
      source_fidelity_verified: row.source_fidelity_verified || false,
    });
    setAssociations({
      vehicle_ids: data.document_vehicles
        .filter((r) => r.document_id === id)
        .map((r) => r.vehicle_id),
      category_ids: data.document_categories
        .filter((r) => r.document_id === id)
        .map((r) => r.category_id),
    });
  }
  function toggle(kind, id) {
    setAssociations((old) => ({
      ...old,
      [kind]: old[kind].includes(id)
        ? old[kind].filter((value) => value !== id)
        : [...old[kind], id],
    }));
  }
  const selected = documents.find((item) => item.id === documentId);
  return (
    <Box bg="white" borderRadius="12px" p={{ base: 5, md: 7 }}>
      <Heading size="md" mb={3}>
        Document applicability and content scopes
      </Heading>
      <Text mb={3}>
        Assign sources to compatible vehicles or categories. Publish the indexed
        document and its scope separately to enable chat.
      </Text>
      <Text mb={3}>
        <NextLink href="/user/vehicles" style={{ textDecoration: "underline" }}>
          Manage vehicles
        </NextLink>
        {" · "}
        <NextLink
          href="/user/learn-cards/manage-cat"
          style={{ textDecoration: "underline" }}
        >
          Manage learning categories
        </NextLink>
      </Text>
      {error && (
        <Text role="alert" color="red.700">
          {error}
        </Text>
      )}
      {notice && (
        <Text role="status" mb={4}>
          {notice}
        </Text>
      )}
      <Button
        mb={3}
        variant="outline"
        disabled={pending}
        onClick={() => load().catch((e) => setError(e.message))}
      >
        Reload associations
      </Button>
      {!data && !error && <Text>Loading knowledge scopes…</Text>}
      {data && (
        <Fieldset.Root disabled={pending}>
          <Stack gap={4}>
            <Field.Root>
              <Field.Label>Document </Field.Label>
              <AdminSelect
                value={documentId}
                onChange={(e) => chooseDocument(e.target.value)}
              >
                <option value="">Select document to assign</option>
                {documents.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.status})
                  </option>
                ))}
              </AdminSelect>
            </Field.Root>
            {selected && (
              <Fieldset.Root disabled={selected.status === "processing"}>
                <Stack gap={3}>
                  <Input
                    aria-label="Search scope assignments"
                    placeholder="Filter vehicles and categories"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                  {data.vehicles
                    .filter((v) =>
                      `${v.name} ${v.year} ${v.variant}`
                        .toLowerCase()
                        .includes(query.toLowerCase()),
                    )
                    .map((v) => (
                      <Checkbox
                        key={v.id}
                        checked={associations.vehicle_ids.includes(v.id)}
                        onCheckedChange={() => toggle("vehicle_ids", v.id)}
                      >
                        {v.name} · {v.year} · {v.variant}
                      </Checkbox>
                    ))}
                  {data.categories
                    .filter((c) =>
                      c.name.toLowerCase().includes(query.toLowerCase()),
                    )
                    .map((c) => (
                      <Checkbox
                        key={c.id}
                        checked={associations.category_ids.includes(c.id)}
                        onCheckedChange={() => toggle("category_ids", c.id)}
                      >
                        Category: {c.name}
                      </Checkbox>
                    ))}
                  {["year", "engine", "variant"].map((key) => (
                    <Field.Root key={key}>
                      <Field.Label>Source {key}</Field.Label>
                      <Input
                        value={metadata[key]}
                        onChange={(e) =>
                          setMetadata({ ...metadata, [key]: e.target.value })
                        }
                      />
                    </Field.Root>
                  ))}
                  <Checkbox
                    checked={metadata.vehicle_independent}
                    onCheckedChange={(e) =>
                      setMetadata({
                        ...metadata,
                        vehicle_independent: e.checked === true,
                      })
                    }
                  >
                    Vehicle-independent guidance
                  </Checkbox>
                  <Checkbox
                    disabled={!selected.extraction_storage_path}
                    checked={metadata.source_fidelity_verified}
                    onCheckedChange={(e) =>
                      setMetadata({
                        ...metadata,
                        source_fidelity_verified: e.checked === true,
                      })
                    }
                  >
                    I checked extracted specifications, units and table
                    relationships against the original source.
                  </Checkbox>
                  <Button
                    onClick={() =>
                      save(async () => {
                        await request(`/documents/${documentId}`, {
                          method: "PATCH",
                          body: metadata,
                        });
                        await request(
                          `/knowledge/documents/${documentId}/associations`,
                          { method: "PUT", body: associations },
                        );
                      })
                    }
                  >
                    Save document applicability and associations
                  </Button>
                </Stack>
              </Fieldset.Root>
            )}
            <Heading as="h2" size="lg" mt={5}>
              Category chat publication
            </Heading>
            {data.categories.map((category) => (
              <Checkbox
                key={category.id}
                checked={category.knowledge_published || false}
                onCheckedChange={(e) =>
                  save(() =>
                    request(
                      `/knowledge/categories/${category.id}/publication`,
                      {
                        method: "PATCH",
                        body: { published: e.checked === true },
                      },
                    ),
                  )
                }
              >
                Publish {category.name} as an AI scope
              </Checkbox>
            ))}
            <Text fontSize="sm">
              Configure AI scope publication separately. The learning category
              must also be published for its chat scope to be visible.
            </Text>
            <Field.Root>
              <Field.Label>Supplementary videos — choose a scope </Field.Label>
              <AdminSelect
                value={videoScope}
                onChange={(e) => {
                  const value = e.target.value;
                  setVideoScope(value);
                  const [kind, id] = value.split(":");
                  setVideoIds(
                    data.videos
                      .filter((v) => v[`${kind}_id`] === id)
                      .map((v) => v.video_id)
                      .join("\n"),
                  );
                }}
              >
                <option value="">Select scope</option>
                {data.vehicles.map((v) => (
                  <option key={v.id} value={`vehicle:${v.id}`}>
                    {v.name}
                  </option>
                ))}
                {data.categories.map((c) => (
                  <option key={c.id} value={`category:${c.id}`}>
                    {c.name}
                  </option>
                ))}
              </AdminSelect>
            </Field.Root>
            {videoScope && (
              <>
                <Field.Root>
                  <Field.Label>
                    Indexed YouTube video IDs, one per line
                  </Field.Label>
                  <Textarea
                    value={videoIds}
                    onChange={(e) => setVideoIds(e.target.value)}
                  />
                  <Field.HelperText>
                    Add or remove eligible indexed videos for this scope. The
                    chatbot ranks matching recommendations by relevance.
                  </Field.HelperText>
                </Field.Root>
                <Button
                  onClick={() =>
                    save(() =>
                      request(
                        `/knowledge/${videoScope.replace(":", "/")}/videos`,
                        {
                          method: "PUT",
                          body: {
                            video_ids: videoIds.split(/\s+/).filter(Boolean),
                          },
                        },
                      ),
                    )
                  }
                >
                  Save supplementary video associations
                </Button>
              </>
            )}
          </Stack>
        </Fieldset.Root>
      )}
    </Box>
  );
}
