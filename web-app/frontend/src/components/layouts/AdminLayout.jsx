import { Flex, Box, Heading, Text, Stack } from "@chakra-ui/react";
import NavBar from "../NavBar";

export default function AdminLayout({ title, description, children }) {
  return (
    <Flex minH="100vh" direction={{ base: "column", md: "row" }} bg="gray.50" color="gray.900">
      <Box flexShrink={0}><NavBar /></Box>
      <Box as="main" flex={1} minW={0} w="100%" maxW="1200px" p={{ base: 4, md: 8 }}>
        <Stack align="start" gap={2} mb={6}>
          <Text fontSize="xs" color="gray.600">LOCAL PROTOTYPE · Changes last until you reload this tab.</Text>
          <Heading as="h1" size="xl">{title}</Heading>
          {description && <Text color="gray.600" fontSize="sm">{description}</Text>}
        </Stack>
        {children}
      </Box>
    </Flex>
  );
}
