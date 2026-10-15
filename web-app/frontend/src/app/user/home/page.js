"use client";

import NextLink from "next/link";
import { Grid, Card, Text, Heading, Stack, Button } from "@chakra-ui/react";
import AdminLayout from "@/components/layouts/AdminLayout";
import { useContent } from "@/components/ContentProvider";

export default function Home() {
  const { dashboard } = useContent();
  const documents = dashboard?.documents || {};
  const guides = dashboard?.guides || {};
  const sections = [
    { label: "Documents", count: documents.total ?? "-", href: "/user/kb", description: `${documents.processed || 0} processed, ${documents.awaiting_index || 0} awaiting indexing, ${documents.processing || 0} processing, ${documents.failed || 0} failed, ${documents.uploaded || 0} awaiting processing.` },
    { label: "Learning Guides", count: guides.total ?? "-", href: "/user/learn-cards", description: `${guides.published || 0} published and ${guides.draft || 0} drafts.` },
    { label: "Emergency Steps", count: dashboard?.steps ?? "-", href: "/user/emergency", description: `${dashboard?.playbooks || 0} playbooks and ${dashboard?.contacts || 0} contacts.` },
  ];

  return (
    <AdminLayout
      title="Home"
      description="Saved documents, guides, and emergency playbooks."
    >
      <Grid
        templateColumns={{ base: "1fr", lg: "repeat(3, minmax(0, 1fr))" }}
        gap={4}
      >
        {sections.map((section) => (
          <Card.Root key={section.href} variant="outline" bg="white">
            <Card.Body>
              <Stack gap={3} h="100%">
                <Heading size="sm">{section.label}</Heading>
                <Text fontSize="3xl" fontWeight="bold">
                  {section.count}
                </Text>
                <Text fontSize="sm" color="gray.600" flex={1}>
                  {section.description}
                </Text>
                <Button asChild variant="outline" alignSelf="start">
                  <NextLink href={section.href}>Open {section.label}</NextLink>
                </Button>
              </Stack>
            </Card.Body>
          </Card.Root>
        ))}
      </Grid>
      <Button asChild mt={6} variant="outline">
        <NextLink href="/user/chatbot">Open real Chat Preview</NextLink>
      </Button>
    </AdminLayout>
  );
}
