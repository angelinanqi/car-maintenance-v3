"use client";
import { useContent } from "@/components/ContentProvider";
﻿import { Flex, Box, Heading, Text, Stack } from "@chakra-ui/react";
import NavBar from "../NavBar";

export default function AdminLayout({ title, description, children }) {
  const { loading, error, refresh } = useContent();
  return (
    <Flex minH="100vh" direction={{ base: "column", md: "row" }} bg="gray.50" color="gray.900">
      <Box flexShrink={0}><NavBar /></Box>
      <Box as="main" flex={1} minW={0} w="100%" maxW="1200px" p={{ base: 4, md: 8 }}>
        <Stack align="start" gap={2} mb={6}>
          {loading && <Text>Loading saved content...</Text>}
          {error && <Text role="alert" color="red.600">{error} <button onClick={refresh}>Retry loading</button></Text>}
          <Heading as="h1" size="xl">{title}</Heading>
          {description && <Text color="gray.600" fontSize="sm">{description}</Text>}
        </Stack>
        {children}
      </Box>
    </Flex>
  );
}
