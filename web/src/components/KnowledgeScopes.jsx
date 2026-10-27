"use client";

import { useState } from "react";
import NextLink from "next/link";
import {
  Box,
  Button,
  Fieldset,
  Flex,
  Heading,
  Stack,
  Text,
  Textarea,
} from "@chakra-ui/react";
import { AdminSelect } from "@/components/admin/NativeControls";
import { useContent } from "@/components/ContentProvider";
import { request } from "@/api/client.mjs";
import { parseVideoLinks } from "@/lib/adminJourney.mjs";
import useUnsavedChanges from "@/components/admin/useUnsavedChanges";

export default function KnowledgeScopes() {
  const { knowledge, refresh } = useContent();
  const [destination, setDestination] = useState("");
  const [links, setLinks] = useState("");
  const [baseline, setBaseline] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useUnsavedChanges(links !== baseline);
  async function save(action, message) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      await refresh({ documentsOnly: true });
      setNotice(message);
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy(false);
    }
  }
  if (!knowledge)
    return (
      <Text>
        Vehicle and topic settings are unavailable. Retry loading the workspace
        above.
      </Text>
    );
  return (
    <Stack gap={6}>
      {error && <Text role="alert">{error}</Text>}
      {notice && <Text role="status">{notice}</Text>}
      <Box bg="white" p={{ base: 5, md: 7 }} borderRadius="12px">
        <Heading size="lg" mb={3}>
          Documents belong with their vehicles and topics
        </Heading>
        <Text color="muted">
          To change where a reference is used, open it in the reference library.
          Its coverage, document check and availability are together in one
          place.
        </Text>
        <Button asChild variant="outline" mt={4}>
          <NextLink href="/admin/kb">Open reference library</NextLink>
        </Button>
      </Box>
      <Box bg="white" p={{ base: 5, md: 7 }} borderRadius="12px">
        <Heading size="lg" mb={3}>
          Learning topics in the chatbot
        </Heading>
        <Text color="muted" mb={5}>
          Enable a topic when you want drivers to ask questions about its
          published guides and reference documents.
        </Text>
        <Stack gap={4}>
          {knowledge.categories.map((category) => (
            <Flex
              key={category.id}
              justify="space-between"
              align="center"
              gap={3}
              wrap="wrap"
            >
              <Box>
                <Text fontWeight="600">{category.name}</Text>
                <Text fontSize="sm" color="muted">
                  {!category.published
                    ? "Make the learning topic available first."
                    : category.knowledge_published
                      ? "Enabled in the chatbot; needs published content."
                      : "Not enabled in the chatbot."}
                </Text>
              </Box>
              {!category.published ? (
                <Button asChild variant="outline" size="sm">
                  <NextLink href="/admin/learn-cards/manage-cat">
                    Manage learning topic
                  </NextLink>
                </Button>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={busy}
                  onClick={() =>
                    save(
                      () =>
                        request(
                          `/knowledge/categories/${category.id}/publication`,
                          {
                            method: "PATCH",
                            body: { published: !category.knowledge_published },
                          },
                        ),
                      "Chatbot topic settings saved.",
                    )
                  }
                >
                  {category.knowledge_published
                    ? "Disable in chatbot"
                    : "Enable in chatbot"}
                </Button>
              )}
            </Flex>
          ))}
        </Stack>
        {!knowledge.categories.length && (
          <Text>Add a learning topic in Learning topics first.</Text>
        )}
      </Box>
      <Box bg="white" p={{ base: 5, md: 7 }} borderRadius="12px">
        <Heading size="lg" mb={3}>
          Related videos
        </Heading>
        <Text color="muted" mb={4}>
          Choose a vehicle or topic, then add YouTube links. Only videos already
          prepared by your Roadie video service can be recommended. Adding a
          link here does not prepare a new video.
        </Text>
        <Fieldset.Root disabled={busy}>
          <Stack gap={4}>
            <Box as="label">
              Vehicle or learning topic
              <AdminSelect
                value={destination}
                onChange={(event) => {
                  if (
                    links !== baseline &&
                    !window.confirm("Discard unsaved video links?")
                  )
                    return;
                  const value = event.target.value;
                  const [kind, id] = value.split(":");
                  const text = knowledge.videos
                    .filter((video) => video[`${kind}_id`] === id)
                    .map(
                      (video) =>
                        `https://www.youtube.com/watch?v=${video.video_id}`,
                    )
                    .join("\n");
                  setDestination(value);
                  setLinks(text);
                  setBaseline(text);
                }}
              >
                <option value="">Choose a vehicle or topic</option>
                <optgroup label="Vehicles">
                  {knowledge.vehicles.map((vehicle) => (
                    <option key={vehicle.id} value={`vehicle:${vehicle.id}`}>
                      {[
                        vehicle.name,
                        vehicle.year,
                        vehicle.engine,
                        vehicle.variant,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </option>
                  ))}
                </optgroup>
                <optgroup label="Learning topics">
                  {knowledge.categories.map((category) => (
                    <option key={category.id} value={`category:${category.id}`}>
                      {category.name}
                    </option>
                  ))}
                </optgroup>
              </AdminSelect>
            </Box>
            {destination && (
              <>
                <Box as="label">
                  YouTube links, one per line
                  <Textarea
                    mt={2}
                    rows={5}
                    value={links}
                    onChange={(event) => setLinks(event.target.value)}
                    placeholder="https://www.youtube.com/watch?v=..."
                  />
                </Box>
                <Button
                  alignSelf="start"
                  disabled={links === baseline}
                  loading={busy}
                  onClick={() => {
                    let ids;
                    try {
                      ids = parseVideoLinks(links);
                    } catch (cause) {
                      setError(cause.message);
                      return;
                    }
                    save(async () => {
                      await request(
                        `/knowledge/${destination.replace(":", "/")}/videos`,
                        { method: "PUT", body: { video_ids: ids } },
                      );
                      setBaseline(links);
                    }, "Related video links saved.");
                  }}
                >
                  Save video links
                </Button>
              </>
            )}
          </Stack>
        </Fieldset.Root>
      </Box>
    </Stack>
  );
}
