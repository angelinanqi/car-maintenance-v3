import { Box, Button, Stack, Text } from "@chakra-ui/react";

const sourceTypes = {
  learning_guide: "Learning guide",
  emergency_protocol: "Reviewed emergency protocol",
  manual: "Reference document",
};

// The RAG response uses timestamps in seconds and includes timestamped URLs.
export default function ChatMessage({ message }) {
  const isUser = message.role === "user";

  return (
    <Box
      alignSelf={isUser ? "flex-end" : "flex-start"}
      maxW={{ base: "95%", md: "80%" }}
      minW={0}
      bg={isUser ? "blue.50" : "white"}
      borderWidth="1px"
      borderColor={isUser ? "blue.200" : "gray.200"}
      borderRadius="lg"
      p={4}
    >
      <Stack gap={3}>
        <Text fontSize="xs" fontWeight="semibold" color="gray.600">
          {isUser ? "You" : "Assistant"}
        </Text>
        <Text fontSize="sm" whiteSpace="pre-wrap" overflowWrap="anywhere">
          {message.answer}
        </Text>
        {isUser && message.failed && (
          <Text fontSize="xs" color="red.600">
            No answer received for this message.
          </Text>
        )}
        {!isUser && message.response_type && (
          <Text role={["generation_error", "retrieval_error"].includes(message.response_type) ? "alert" : undefined} fontSize="xs" color={["generation_error", "retrieval_error"].includes(message.response_type) ? "red.700" : "gray.600"}>
            Response: {message.response_type.replaceAll("_", " ")}
          </Text>
        )}
        {!isUser && message.route && <Text fontSize="xs" color="gray.600">Route: {message.route}</Text>}
        {!isUser && <Box as="section" aria-label="Source references">
          <Text fontSize="sm" fontWeight="semibold">Source references</Text>
          {(Array.isArray(message.sources) ? message.sources : []).filter(Boolean).map((source, index) => (
            <Box key={`${source.chunk_id || source.document_id || "source"}-${index}`} mt={2} pl={3} borderLeftWidth="2px">
              <Text fontSize="sm" overflowWrap="anywhere">{source.label || `Source ${index + 1}`}: {sourceTypes[source.source_type] || "Reference document"} — {source.title || source.document_title || source.document_id || "Reference unavailable"}</Text>
              {source.reviewed_at && <Text fontSize="xs">Reviewed: {source.reviewed_at}</Text>}
              {source.source_reference && <Text fontSize="xs" overflowWrap="anywhere">Source reference: {source.source_reference}</Text>}
              {source.page != null && <Text fontSize="xs">Page: {source.page}</Text>}
              {source.chunk_id && <Text fontSize="xs" overflowWrap="anywhere">Chunk: {source.chunk_id}</Text>}
            </Box>
          ))}
          {!message.sources?.length && <Text fontSize="xs" color="gray.600">No source references returned for this answer.</Text>}
        </Box>}
        {!isUser && message.external_warning && (
          <Box
            bg="orange.50"
            borderLeftWidth="3px"
            borderColor="orange.300"
            p={3}
            borderRadius="sm"
          >
            <Text fontSize="sm" color="orange.900">
              Verify current legal requirements with the relevant authority.
            </Text>
          </Box>
        )}
        {!isUser &&
          (Array.isArray(message.videos) ? message.videos : [])
            .filter((video) => video && typeof video.url === "string")
            .map((video, index) => (
              <Box
                key={`${video.url}-${index}`}
                borderWidth="1px"
                borderColor="gray.200"
                borderRadius="md"
                p={3}
              >
                <Stack gap={2} align="start">
                  <Text fontSize="xs" color="gray.600">
                    Recommended video
                  </Text>
                  <Text
                    fontSize="sm"
                    fontWeight="semibold"
                    overflowWrap="anywhere"
                  >
                    {video.title}
                  </Text>
                  {typeof video.timestamp === "number" &&
                    Number.isFinite(video.timestamp) &&
                    video.timestamp >= 0 && (
                      <Text fontSize="xs" color="gray.600">
                        Starts at {Math.floor(video.timestamp / 60)}:
                        {String(Math.floor(video.timestamp % 60)).padStart(
                          2,
                          "0",
                        )}
                      </Text>
                    )}
                  {/^https?:\/\//i.test(video.url) && (
                    <Button
                      asChild
                      size="sm"
                      variant="outline"
                      colorPalette="blue"
                    >
                      <a
                        href={video.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label={`Watch ${video.title} (opens in a new tab)`}
                      >
                        Watch video
                      </a>
                    </Button>
                  )}
                </Stack>
              </Box>
            ))}
      </Stack>
    </Box>
  );
}
