"use client";

import { useRouter } from 'next/navigation';
import { useState } from "react";
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
} from "@chakra-ui/react";

// Adjust path based on your folder structure
import AdminLayout from "../../../components/layouts/AdminLayout";

export default function ContentPage() {
  const router = useRouter();
  const [selectedTab, setSelectedTab] = useState("all");
  const [isCreateOpen, setIsCreateOpen] = useState(false); // Modal trigger for later

  // Sample Dataset
  const [cards, setCards] = useState([
    {
      id: 1,
      title: "Getting Started with Next.js App Router",
      category: "Tutorials",
      status: "Published", // 'Published' or 'Unpublished'
      updatedAt: "1 January 2026",
    },
    {
      id: 2,
      title: "Chakra UI v3 Migration Guidelines",
      category: "Documentation",
      status: "Unpublished",
      updatedAt: "14 February 2026",
    },
    {
      id: 3,
      title: "Q3 Product Roadmap & Goals",
      category: "Updates",
      status: "Published",
      updatedAt: "28 August 2026",
    },
    {
      id: 4,
      title: "Building Scalable API Endpoints",
      category: "Tutorials",
      status: "Unpublished",
      updatedAt: "1 September 2026",
    },
  ]);

  // Categories list for Tabs
  const categories = ["all", "Tutorials", "Documentation", "Updates"];

  // Toggle Published / Unpublished status
  const handleTogglePublish = (id) => {
    setCards((prev) =>
      prev.map((card) => {
        if (card.id === id) {
          const newStatus =
            card.status === "Published" ? "Unpublished" : "Published";
          console.log(`Updated ID ${id} status to ${newStatus}`);
          return { ...card, status: newStatus };
        }
        return card;
      }),
    );
  };

  const handleEdit = (card) => {
    console.log("Edit clicked for:", card);
  };

  // Filter cards based on active tab selection
  const filteredCards =
    selectedTab === "all"
      ? cards
      : cards.filter(
          (card) => card.category.toLowerCase() === selectedTab.toLowerCase(),
        );

  return (
    <AdminLayout
      title="Content Manager"
      description="Manage and publish category articles and records."
    >
      <Stack gap={6}>
        {/* HEADER ROW */}
        <Flex justify="space-between" align="center" wrap="wrap" gap={4}>
          <Box>
            <Heading size="md">All Articles</Heading>
            <Text fontSize="sm" color="gray.500">
              Manage items across categories
            </Text>
          </Box>

          <Button
            colorPalette="blue"
            onClick={() => router.push("/user/learn-cards/create")}
          >
            Create
          </Button>
        </Flex>

        {/* CHAKRA UI V3 TABS */}
        <Tabs.Root
          defaultValue="all"
          value={selectedTab}
          onValueChange={(e) => setSelectedTab(e.value)}
          variant="line"
        >
          <Tabs.List>
            {categories.map((cat) => (
              <Tabs.Trigger key={cat} value={cat} textTransform="capitalize">
                {cat}
              </Tabs.Trigger>
            ))}
          </Tabs.List>

          {/* HORIZONTAL CARDS LIST VIEW */}
          <Tabs.Content value={selectedTab} pt={4}>
            <Stack gap={3} w="100%">
              {filteredCards.map((card) => {
                const isPublished = card.status === "Published";
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
                          <Text fontSize="xs" color="gray.500">
                            Updated {card.updatedAt}
                          </Text>
                        </Stack>

                        {/* Right Actions Section */}
                        <HStack
                          gap={2}
                          shrink={0}
                          w={{ base: "100%", md: "auto" }}
                          justify="flex-end"
                        >
                          <Button
                            size="sm"
                            variant={isPublished ? "outline" : "solid"}
                            colorPalette={isPublished ? "orange" : "green"}
                            onClick={() => handleTogglePublish(card.id)}
                          >
                            {isPublished ? "Unpublish" : "Publish"}
                          </Button>

                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleEdit(card)}
                          >
                            Edit
                          </Button>
                        </HStack>
                      </Flex>
                    </Card.Body>
                  </Card.Root>
                );
              })}
            </Stack>

            {/* Empty state */}
            {filteredCards.length === 0 && (
              <Box py={10} textAlign="center">
                <Text color="gray.500">No items found in this category.</Text>
              </Box>
            )}
          </Tabs.Content>
        </Tabs.Root>
      </Stack>
    </AdminLayout>
  );
}
