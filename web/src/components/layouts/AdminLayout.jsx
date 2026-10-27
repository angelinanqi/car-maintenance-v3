"use client";

import NextLink from "next/link";
import { useContent } from "@/components/ContentProvider";
import { Box, Heading, Text, Stack, Button, Flex } from "@chakra-ui/react";

export default function AdminLayout({ title, description, children }) {
  const { loading, error, refresh } = useContent();
  return (
    <Box w="100%" maxW="1440px" mx="auto" px={{ base: 4, md: 7, xl: 10 }} py={{ base: 6, md: 8 }}>
      <Flex align="center" justify="space-between" gap={4} mb={7} color="muted" fontSize="sm">
        <NextLink href="/admin/home">Roadie workspace</NextLink>
        <Text>Administration</Text>
      </Flex>
      <Stack align="start" gap={3} mb={8}>
        <Heading as="h1" fontSize={{ base: "28px", md: "34px" }} lineHeight="1.2">{title}</Heading>
        {description && <Text color="muted" maxW="760px">{description}</Text>}
      </Stack>
      {loading && <Text role="status" mb={4}>Loading your workspace…</Text>}
      {error && <Box role="alert" mb={5}><Text>{error}</Text><Button mt={2} variant="outline" onClick={() => refresh()}>Retry loading</Button></Box>}
      {children}
    </Box>
  );
}
