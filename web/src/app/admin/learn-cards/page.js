"use client";
import Pagination, { usePagination } from "@/components/admin/Pagination";

import { AdminSelect } from "@/components/admin/NativeControls";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useContent } from "@/components/ContentProvider";
import { toaster } from "@/components/ui/toaster";
import dynamic from "next/dynamic";
import DeleteConfirmModal from "@/components/modals/DeleteConfirmModal";
import { hasGuideContent } from "@/lib/guideContent.mjs";
import {
  Flex,
  Box,
  Heading,
  Text,
  Button,
  Card,
  Tabs,
  Badge,
  Tag,
  HStack,
  Stack,
  Dialog,
  Input,
} from "@chakra-ui/react";

// Adjust path based on your folder structure
import AdminLayout from "../../../components/layouts/AdminLayout";

const TiptapEditor = dynamic(() => import("@/components/editor/TipTapEditor"), {
  loading: () => <Text role="status">Opening guide preview…</Text>,
});

export default function ContentPage() {
  const router = useRouter();
  const [selectedTab, setSelectedTab] = useState("all");
  const [preview, setPreview] = useState(null);
  const [deleteCard, setDeleteCard] = useState(null);
  const [publishingId, setPublishingId] = useState(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");

  const {
    cards,
    categories: guideCategories,
    saveGuide,
    publishGuide,
    deleteGuide,
  } = useContent();
  const categories = [
    { id: "all", name: "All" },
    { id: "uncategorized", name: "Uncategorized" },
    ...guideCategories,
  ];

  // Toggle Published / Unpublished status
  const handleTogglePublish = async (id) => {
    if (publishingId) return;
    const card = cards.find((item) => item.id === id);
    setPublishingId(id);
    try {
      if (card.status === "published") {
        await saveGuide(id, { status: "draft" });
      } else {
        await publishGuide(id);
      }
      toaster.create({ title: "Guide status saved", type: "success" });
    } catch (error) {
      toaster.create({ title: error.message, type: "error" });
    } finally {
      setPublishingId(null);
    }
  };

  const handleEdit = (card) => {
    router.push("/admin/learn-cards/create?edit=" + card.id);
  };

  // Filter cards based on active tab selection
  const filteredCards = cards.filter(
    (card) =>
      (selectedTab === "all" ||
        (card.category_id || "uncategorized") === selectedTab) &&
      (!status || card.status === status) &&
      `${card.title} ${card.description || ""}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );

  const pagination = usePagination(filteredCards, JSON.stringify([query, status, selectedTab]));

  return (
    <AdminLayout
      title="Learning Guides"
      description="Write, preview, and manage maintenance guides."
    >
      <Stack gap={6}>
        {/* HEADER ROW */}
        <Flex justify="space-between" align="center" wrap="wrap" gap={4}>
          <Box>
            <Heading size="md">All Guides</Heading>
            <Text fontSize="sm" color="muted">
              Continue an unfinished guide or update advice that drivers already
              use.
            </Text>
          </Box>

          <HStack gap={2} wrap="wrap">
            <Button
              variant="outline"
              onClick={() => router.push("/admin/learn-cards/manage-cat")}
            >
              Manage learning topics
            </Button>
            {/* Create Button */}
            <Button
              colorPalette="brand"
              onClick={() => router.push("/admin/learn-cards/create")}
            >
              Create Guide
            </Button>
          </HStack>
        </Flex>

        <Flex gap={4} wrap="wrap" align="end">
          <Box as="label" flex={1} minW="180px">
            Search guides
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search title or introduction"
            />
          </Box>
          <Box as="label" minW="180px">
            Publication
            <AdminSelect
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="">All statuses</option>
              <option value="draft">Draft</option>
              <option value="published">Published</option>
            </AdminSelect>
          </Box>
        </Flex>
        <Text fontSize="sm" color="muted">
          Drivers can read published guides when their learning topic is
          available. The chatbot can also use these guides when the topic is
          enabled in Topics &amp; videos.
        </Text>
        {/* CHAKRA UI V3 TABS */}
        <Tabs.Root
          defaultValue="all"
          value={selectedTab}
          onValueChange={(e) => setSelectedTab(e.value)}
          variant="line"
          minW={0}
        >
          <Tabs.List overflowX="auto" overflowY="hidden">
            {categories.map((cat) => (
              <Tabs.Trigger
                key={cat.id}
                value={cat.id}
                textTransform="capitalize"
                flexShrink={0}
                whiteSpace="nowrap"
              >
                {cat.name}
              </Tabs.Trigger>
            ))}
          </Tabs.List>

          {/* HORIZONTAL CARDS LIST VIEW */}
          <Tabs.Content value={selectedTab} pt={4}>
            <Stack gap={3} w="100%">
              {pagination.items.map((card) => {
                const isPublished = card.status === "published";
                return (
                  <Card.Root key={card.id} variant="outline" w="100%">
                    <Card.Body p={4}>
                      <Flex
                        direction={{ base: "column", md: "row" }}
                        justify="space-between"
                        align={{ base: "start", md: "center" }}
                        gap={4}
                      >
                        {/* Left Info Section */}
                        <Stack gap={2} flex={1}>
                          {/* Status & Category */}
                          <HStack gap={2}>
                            <Badge
                              colorPalette={isPublished ? "green" : "gray"}
                              variant="subtle"
                              userSelect="none"
                            >
                              {card.status}
                            </Badge>

                            <Tag.Root
                              size="sm"
                              variant="outline"
                              userSelect="none"
                            >
                              <Tag.Label>{card.category}</Tag.Label>
                            </Tag.Root>
                          </HStack>

                          {/* Card Title */}
                          <Heading size="sm">{card.title}</Heading>

                          {/* Updated Date */}
                          <Text fontSize="sm" color="muted">
                            Updated {card.updatedAt}
                          </Text>
                        </Stack>

                        {/* Right Actions Section */}
                        <HStack
                          gap={2}
                          shrink={0}
                          wrap="wrap"
                          w={{ base: "100%", md: "auto" }}
                          justify="flex-end"
                        >
                          <Button
                            size="sm"
                            variant={isPublished ? "outline" : "solid"}
                            colorPalette={isPublished ? "orange" : "green"}
                            onClick={() => handleTogglePublish(card.id)}
                            disabled={Boolean(publishingId)}
                            loading={publishingId === card.id}
                          >
                            {isPublished ? "Unpublish guide" : "Publish guide"}
                          </Button>

                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleEdit(card)}
                          >
                            Edit
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setPreview(card)}
                          >
                            Preview
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            colorPalette="red"
                            onClick={() => setDeleteCard(card)}
                          >
                            Remove
                          </Button>
                        </HStack>
                      </Flex>
                    </Card.Body>
                  </Card.Root>
                );
              })}
            </Stack>

            <Pagination {...pagination} label="Learning Guides" />
            {/* Empty state */}
            {filteredCards.length === 0 && (
              <Box py={10} textAlign="center">
                <Text color="muted">
                  {cards.length
                    ? "No guides match these filters."
                    : "No learning guides yet. Create a guide, save a draft, then publish when it is ready."}
                </Text>
                {cards.length > 0 && (
                  <Button
                    mt={3}
                    variant="outline"
                    onClick={() => {
                      setQuery("");
                      setStatus("");
                      setSelectedTab("all");
                    }}
                  >
                    Clear filters
                  </Button>
                )}
              </Box>
            )}
          </Tabs.Content>
        </Tabs.Root>
      </Stack>
      <DeleteConfirmModal
        isOpen={Boolean(deleteCard)}
        itemName={deleteCard?.title}
        onClose={() => setDeleteCard(null)}
        onConfirm={async () => {
          try {
            await deleteGuide(deleteCard.id);
            setDeleteCard(null);
            toaster.create({ title: "Guide removed", type: "success" });
          } catch (error) {
            toaster.create({ title: error.message, type: "error" });
          }
        }}
      />
      <Dialog.Root
        open={Boolean(preview)}
        onOpenChange={({ open }) => !open && setPreview(null)}
        size="xl"
        scrollBehavior="inside"
      >
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content>
            <Dialog.Header>
              <Dialog.Title>{preview?.title}</Dialog.Title>
            </Dialog.Header>
            <Dialog.Body>
              <Text mb={3} fontSize="sm">
                {preview?.status} · {preview?.category} · Admin preview; not
                delivered to mobile users.
              </Text>
              {preview &&
                (hasGuideContent(preview.content) ? (
                  <TiptapEditor
                    key={preview.id}
                    content={preview.content}
                    readOnly
                  />
                ) : (
                  <Text>This draft has no content yet.</Text>
                ))}
            </Dialog.Body>
            <Dialog.Footer>
              <Button onClick={() => setPreview(null)}>Close preview</Button>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Dialog.Root>
    </AdminLayout>
  );
}
