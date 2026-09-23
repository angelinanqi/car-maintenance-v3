import { Box, Button, Stack, Text } from "@chakra-ui/react";

// Only user-facing fields are rendered. Video items use title, url, and an
// optional display timestamp; future API data can be mapped to this shape.
export default function ChatMessage({ message }) {
  const isUser = message.role === "user";

  return (
    <Box alignSelf={isUser ? "flex-end" : "flex-start"} maxW={{ base: "95%", md: "80%" }}
      minW={0} bg={isUser ? "blue.50" : "white"} borderWidth="1px"
      borderColor={isUser ? "blue.200" : "gray.200"} borderRadius="lg" p={4}>
      <Stack gap={3}>
        <Text fontSize="xs" fontWeight="semibold" color="gray.600">{isUser ? "You" : "Assistant"}</Text>
        <Text fontSize="sm" whiteSpace="pre-wrap" overflowWrap="anywhere">{message.answer}</Text>
        {!isUser && message.external_warning && (
          <Box bg="orange.50" borderLeftWidth="3px" borderColor="orange.300" p={3} borderRadius="sm">
            <Text fontSize="sm" color="orange.900">{message.external_warning}</Text>
          </Box>
        )}
        {!isUser && message.videos?.map((video, index) => (
          <Box key={`${video.url}-${index}`} borderWidth="1px" borderColor="gray.200" borderRadius="md" p={3}>
            <Stack gap={2} align="start">
              <Text fontSize="xs" color="gray.600">Recommended video</Text>
              <Text fontSize="sm" fontWeight="semibold" overflowWrap="anywhere">{video.title}</Text>
              {video.timestamp && <Text fontSize="xs" color="gray.600">Starts at {video.timestamp}</Text>}
              {/^https?:\/\//i.test(video.url) && (
                <Button asChild size="sm" variant="outline" colorPalette="blue">
                  <a href={video.url} target="_blank" rel="noopener noreferrer" aria-label={`Watch ${video.title} (opens in a new tab)`}>Watch video</a>
                </Button>
              )}
            </Stack>
          </Box>
        ))}
      </Stack>
    </Box>
  );
}
