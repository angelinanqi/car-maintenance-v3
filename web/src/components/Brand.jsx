import { Box, Flex, Text } from "@chakra-ui/react";

export default function Brand({ inverse = false }) {
  if (!inverse) return <Flex align="center" gap={3}>
    <Box asChild w="140px" maxW="100%">
      <img src="/branding/roadie_full_logo.png" alt="MyRoadie" />
    </Box>
    <Text color="muted" fontWeight="600">Admin</Text>
  </Flex>;
  return (
    <Flex align="center" gap={3} color={inverse ? "white" : "ink"}>
      <Box asChild w="40px" h="40px" flexShrink={0}>
        <img src="/branding/roadie_logo.png" alt="" width="40" height="40" />
      </Box>
      <Text fontWeight="700" fontSize="xl" letterSpacing="-0.04em">MyRoadie <Box as="span" fontWeight="400" color={inverse ? "brand.200" : "muted"}>Admin</Box></Text>
    </Flex>
  );
}
