"use client";

import NextLink from "next/link";
import { Grid, Card, Text, Heading, Stack, Button } from "@chakra-ui/react";
import AdminLayout from "@/components/layouts/AdminLayout";
import { usePrototype } from "@/components/PrototypeProvider";

export default function Home() {
  const { documents, cards, sops } = usePrototype();
  const sections = [
    { label: "Documents", count: documents.length, href: "/user/kb", description: "Add and edit local document records. Processing is not connected." },
    { label: "Learning Guides", count: cards.length, href: "/user/learn-cards", description: "Write guides and try draft and published states locally." },
    { label: "Emergency Steps", count: sops.reduce((count, sop) => count + sop.steps.length, 0), href: "/user/emergency", description: "Edit sample playbooks and preview their checklists." },
  ];

  return (
    <AdminLayout title="Home" description="Your local documents, guides, and sample playbooks.">
      <Grid templateColumns={{ base: "1fr", lg: "repeat(3, minmax(0, 1fr))" }} gap={4}>
        {sections.map((section) => (
          <Card.Root key={section.href} variant="outline" bg="white">
            <Card.Body>
              <Stack gap={3} h="100%">
                <Heading size="sm">{section.label}</Heading>
                <Text fontSize="3xl" fontWeight="bold">{section.count}</Text>
                <Text fontSize="sm" color="gray.600" flex={1}>{section.description}</Text>
                <Button asChild variant="outline" alignSelf="start"><NextLink href={section.href}>Open {section.label}</NextLink></Button>
              </Stack>
            </Card.Body>
          </Card.Root>
        ))}
      </Grid>
    </AdminLayout>
  );
}
