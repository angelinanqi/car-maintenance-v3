"use client";

import NextLink from "next/link";
import { Box, Flex, Grid, Text, Heading, Stack, Button } from "@chakra-ui/react";
import AdminLayout from "@/components/layouts/AdminLayout";
import { useContent } from "@/components/ContentProvider";

export default function Home() {
  const { dashboard, loading } = useContent();
  const documents = dashboard?.documents;
  const guides = dashboard?.guides;
  const stats = [
    ["Reference documents", documents?.total, "/user/kb"],
    ["Published guides", guides ? guides.published || 0 : undefined, "/user/learn-cards"],
    ["Emergency playbooks", dashboard?.playbooks, "/user/emergency"],
    ["Shared contacts", dashboard?.contacts, "/user/emergency"],
  ];
  const workflows = [
    ["Vehicle catalogue", "Add manufacturers, models and vehicle variants.", "/user/vehicles"],
    ["Maintenance items", "Define the inspections and service operations drivers track.", "/user/maintenance-items"],
    ["Service schedules", "Review manufacturer intervals against the original source.", "/user/schedules"],
    ["Learning guides", "Turn useful car knowledge into clear lessons.", "/user/learn-cards"],
    ["Emergency & contacts", "Keep reviewed protocols and assistance contacts ready.", "/user/emergency"],
    ["Chat preview", "Check responses, source citations and scope availability.", "/user/chatbot"],
  ];
  return <AdminLayout title="Your Roadie workspace" description="Keep the knowledge behind every journey accurate, reviewed and ready to use.">
    <Grid templateColumns={{ base: "1fr 1fr", xl: "repeat(4, 1fr)" }} gap={3} mb={8}>
      {stats.map(([label, count, href]) => <Box key={label} bg="white" p={{ base: 4, md: 6 }} borderRadius="12px">
        <Text color="muted" fontSize="sm">{label}</Text>
        <Text fontSize="36px" fontWeight="650" lineHeight="1.3" mt={3} mb={3} fontVariantNumeric="tabular-nums">{count ?? "—"}</Text>
        <NextLink href={href} style={{ fontSize: 14, fontWeight: 600, color: "#795000" }}>Manage →</NextLink>
      </Box>)}
    </Grid>
    <Grid templateColumns={{ base: "1fr", xl: "1.3fr 1fr" }} gap={6} mb={8}>
      <Box bg="white" p={{ base: 5, md: 7 }} borderRadius="12px">
        <Heading as="h2" size="xl" mb={2}>Ready for the next step</Heading>
        <Text color="muted" mb={5}>Work waiting in your content library.</Text>
        {!dashboard ? <Text>{loading ? "Loading current counts…" : "Counts are unavailable. Retry loading the workspace above."}</Text> : <Stack gap={3}>
          {[["Documents to process", documents.uploaded || 0], ["Processing or awaiting indexing", (documents.processing || 0) + (documents.awaiting_index || 0)], ["Documents needing a retry", documents.failed || 0], ["Learning drafts", guides.draft || 0]].map(([label, count]) => <Flex key={label} justify="space-between" gap={4} bg="canvas" p={3} borderRadius="6px"><Text>{label}</Text><Text fontWeight="650" fontVariantNumeric="tabular-nums">{count}</Text></Flex>)}
        </Stack>}
        <Button asChild mt={5}><NextLink href="/user/kb">Open document library</NextLink></Button>
      </Box>
      <Box bg="brand.100" p={{ base: 5, md: 7 }} borderRadius="12px">
        <Heading as="h2" size="xl" mb={4}>From source to answer</Heading>
        <Stack as="ol" gap={4} pl={5} listStyleType="decimal">
          <li><Text fontWeight="600">Add a trusted source</Text><Text fontSize="sm">Upload a document and assign its vehicle or topic.</Text></li>
          <li><Text fontWeight="600">Process and review</Text><Text fontSize="sm">Wait for indexing, then check the extraction against the original.</Text></li>
          <li><Text fontWeight="600">Publish and check</Text><Text fontSize="sm">Publish the document and scope, then try the chat preview.</Text></li>
        </Stack>
        <Button asChild variant="outline" mt={6} borderColor="brand.600"><NextLink href="/user/scopes">Manage knowledge scopes</NextLink></Button>
      </Box>
    </Grid>
    <Heading as="h2" size="xl" mb={4}>Manage Roadie</Heading>
    <Grid templateColumns={{ base: "1fr", md: "1fr 1fr" }} gap={3}>
      {workflows.map(([label, description, href]) => <Box key={href} asChild bg="white" p={5} borderRadius="8px" _hover={{ bg: "brand.50" }}>
        <NextLink href={href}><Flex justify="space-between" align="start" gap={4}><Box><Text fontWeight="600">{label}</Text><Text color="muted" fontSize="sm" mt={1}>{description}</Text></Box><Text aria-hidden="true">→</Text></Flex></NextLink>
      </Box>)}
    </Grid>
  </AdminLayout>;
}
