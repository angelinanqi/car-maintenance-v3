import { Badge, Box, Flex, Stack, Text } from "@chakra-ui/react";

export default function PublicationChecklist({ steps }) {
  const complete = steps.filter((step) => step.complete).length;
  return <Box borderWidth="1px" borderRadius="10px" overflow="hidden">
    <Flex px={4} py={3} bg="canvas" justify="space-between" gap={3} align="center">
      <Text fontWeight="600">Before publishing</Text>
      <Text fontSize="sm" color="muted">{complete} of {steps.length} ready</Text>
    </Flex>
    <Stack gap={0}>
      {steps.map((step) => <Flex key={step.label} px={4} py={3} gap={3} align="start" borderTopWidth="1px">
        <Badge colorPalette={step.complete ? "green" : "orange"} flexShrink={0}>
          {step.complete ? "Ready" : "To do"}
        </Badge>
        <Box minW={0}>
          <Text fontSize="sm" fontWeight="600">
            {step.href && !step.complete
              ? <a href={step.href} style={{ textDecoration: "underline" }}>{step.label}</a>
              : step.label}
          </Text>
          {step.description && <Text fontSize="sm" color="muted">{step.description}</Text>}
        </Box>
      </Flex>)}
    </Stack>
  </Box>;
}
