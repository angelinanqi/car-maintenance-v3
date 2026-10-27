import { Box, Flex, Text } from "@chakra-ui/react";

export default function Brand({ inverse = false }) {
  return (
    <Flex align="center" gap={3} color={inverse ? "white" : "ink"}>
      <Box bg="brand.400" color="ink" w="36px" h="36px" borderRadius="8px" display="grid" placeItems="center" aria-hidden="true">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M6 20 9 4h6l3 16M12 6v3m0 3v3m0 3v2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
      </Box>
      <Text fontWeight="700" fontSize="xl" letterSpacing="-0.04em">Roadie <Box as="span" fontWeight="400" color={inverse ? "#c5cdd6" : "muted"}>Admin</Box></Text>
    </Flex>
  );
}
