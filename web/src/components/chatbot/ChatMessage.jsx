import { Box, Button, SimpleGrid, Stack, Text } from "@chakra-ui/react";
import ChatAttachment from "./ChatAttachment";
import ChatAnswer from "./ChatAnswer";
import ManualSourceLink from "./ManualSourceLink";
import ContentMedia from "../ContentMedia";
import { chatLayout } from "@/lib/chatLayout.mjs";

function ManualOriginals({ attachments, heading = false }) {
  if (!attachments.length) return null;
  return <Box as="section" aria-label="Manual originals">
    {heading && <Text fontSize="sm" fontWeight="semibold" mb={3}>From the manual</Text>}
    <SimpleGrid columns={{ base: 1, sm: attachments.length > 1 ? 2 : 1 }} gap={3}>
      {attachments.map(attachment => <ChatAttachment
        key={`${attachment.document_id}-${attachment.source_revision}-${attachment.element_id}`}
        attachment={attachment} sourceLabel={attachment.reference_label} />)}
    </SimpleGrid>
  </Box>;
}

const sourceTypes = {
  learning_guide: "Learning guide",
  emergency_protocol: "Reviewed emergency protocol",
  manual: "Reference document",
  personal_vehicle_profile: "Your saved vehicle details",
  personal_maintenance: "Your saved services and calculated due status",
};

function sourceDate(value) {
  if (typeof value !== "string") return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : new Intl.DateTimeFormat("en-GB", {
    day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
  }).format(date);
}

// The RAG response uses timestamps in seconds and includes timestamped URLs.
export default function ChatMessage({ message, onMaintenance, onEmergency, onGuide }) {
  const isUser = message.role === "user";
  const sources = (Array.isArray(message.sources) ? message.sources : []).filter(Boolean);
  const failed = ["generation_error", "retrieval_error"].includes(message.response_type);
  const attachments = (Array.isArray(message.attachments) ? message.attachments : []).filter(Boolean);
  const layout = chatLayout(message.answer, message.answer_sections, attachments);
  const manualLinks = (Array.isArray(message.manual_links) ? message.manual_links : []).filter(Boolean);
  const guides = (Array.isArray(message.recommended_guides) ? message.recommended_guides : []).filter(Boolean);

  return (
    <Box
      alignSelf={isUser ? "flex-end" : "flex-start"}
      as="article"
      aria-label={isUser ? "Your message" : "Assistant answer"}
      maxW={isUser ? { base: "95%", md: "80%" } : "68ch"}
      w={isUser ? undefined : "100%"}
      minW={0}
      bg={isUser ? "brand.100" : "transparent"}
      borderRadius={isUser ? "lg" : "none"}
      px={isUser ? 4 : { base: 1, md: 2 }}
      py={4}
    >
      <Stack gap={3}>
        <Text fontSize="sm" fontWeight="semibold" color="gray.600">
          {isUser ? "You" : "Car assistant"}
        </Text>
        {isUser
          ? <Text fontSize="md" whiteSpace="pre-wrap" overflowWrap="anywhere" lineHeight="1.7">{message.answer}</Text>
          : layout.sections.length
            ? <Stack gap={4}>{layout.sections.map((section, index) => <Stack key={index} gap={3}>
                <ChatAnswer>{section.text}</ChatAnswer>
                <ManualOriginals attachments={section.attachments} />
              </Stack>)}</Stack>
            : <ChatAnswer>{message.answer}</ChatAnswer>}
        {!isUser && <ManualOriginals attachments={layout.remainingAttachments} heading />}
        {!isUser && <ContentMedia items={Array.isArray(message.content_media) ? message.content_media : []} />}
        {isUser && message.failed && (
          <Text fontSize="sm" color="red.600">
            No answer received for this message.
          </Text>
        )}
        {!isUser && failed && (
          <Text role="alert" fontSize="sm" color="red.700">
            The service could not complete this answer. Please try again shortly.
          </Text>
        )}
        {!isUser && (message.route === 'emergency' || sources.some(source => source.source_type === 'emergency_protocol')) && onEmergency && <Button
          colorPalette={message.route === 'emergency' ? 'red' : 'brand'}
          variant={message.route === 'emergency' ? 'solid' : 'outline'} onClick={onEmergency}>
          {message.route === 'emergency' ? 'Open emergency help' : 'Explore emergency guidance'}
        </Button>}
        {!isUser && onGuide && guides.length > 0 && <Box as="section" aria-label="Further learning">
          <Text fontSize="sm" fontWeight="semibold" mb={2}>Further learning</Text>
          <Stack gap={2}>
            {guides.map(guide => <Button key={guide.source_id} variant="outline" whiteSpace="normal" height="auto" py={2}
              onClick={() => onGuide(guide.source_id)}>Open guide: {guide.title}</Button>)}
          </Stack>
        </Box>}
        {!isUser && sources.some(source => source.source_type === 'personal_maintenance') && onMaintenance && <Button variant="outline" onClick={onMaintenance}>View maintenance</Button>}
        {!isUser && sources.length > 0 && <Box as="section" aria-label="Supporting sources" mt={1} pt={3} borderTopWidth="1px" borderColor="gray.200">
          <Text fontSize="xs" fontWeight="semibold" color="muted" mb={3}>Supporting sources</Text>
          <Stack gap={3}>
            {sources.map((source, index) => (
              <Box key={`${source.label || "source"}-${index}`} display="flex" gap={3} minW={0}>
                <Text as="span" fontSize="xs" fontFamily="mono" fontWeight="semibold" color="brand.700" pt="1px" minW="2ch" flexShrink={0}>
                  {source.label || index + 1}
                </Text>
                <Stack gap={1} minW={0}>
                  <Text fontSize="sm" fontWeight="medium" overflowWrap="anywhere">
                    {source.title || source.document_title || "Reference document"}
                  </Text>
                  <Text fontSize="xs" color="muted">{sourceTypes[source.source_type] || "Reference document"}</Text>
                  {source.as_of && sourceDate(source.as_of) && <Text fontSize="xs" color="muted">As of {sourceDate(source.as_of)}</Text>}
                  {source.reviewed_at && sourceDate(source.reviewed_at) && <Text fontSize="xs" color="muted">Reviewed {sourceDate(source.reviewed_at)}</Text>}
                  {source.source_reference && <Text fontSize="xs" color="muted" overflowWrap="anywhere">{source.source_reference}</Text>}
                  {source.page != null && <Text fontSize="xs" color="muted">Page {source.page}</Text>}
                  {source.section_path?.length > 0 && <Text fontSize="xs" color="muted">Section: {source.section_path.join(" → ")}</Text>}
                  {source.source_type === "manual" && <ManualSourceLink endpoint={source.source_endpoint} />}
                </Stack>
              </Box>
            ))}
          </Stack>
        </Box>}
        {!isUser && message.response_type === "insufficient_information" && sources.length === 0 && (
          <Text fontSize="sm" color="muted">No supporting source was found for this question.</Text>
        )}
        {!isUser && manualLinks.length > 0 && <Box as="section" aria-label="Manuals to browse">
          <Text fontSize="sm" fontWeight="semibold" mb={2}>Manuals to browse</Text>
          <Text fontSize="sm" color="muted" mb={3}>You can inspect these manuals from your selected scope. They are not confirmed evidence for this answer.</Text>
          <Stack gap={3}>
            {manualLinks.map((manual) => <Stack key={`${manual.document_id}-${manual.source_revision}`} gap={1}>
              <Text fontSize="sm">{manual.document_title}</Text>
              <ManualSourceLink endpoint={manual.source_endpoint} />
            </Stack>)}
          </Stack>
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
              This answer includes information outside the available manuals.
            </Text>
          </Box>
        )}
        {!isUser &&
          (Array.isArray(message.videos) ? message.videos : [])
            .filter((video) => video && typeof video.url === "string")
            .map((video, index) => (
              <Box
                key={`${video.url}-${index}`}
                borderLeftWidth="2px"
                borderColor="brand.300"
                pl={4}
                py={2}
              >
                <Stack gap={2} align="start">
                  <Text fontSize="sm" color="gray.600">
                    Related video · External tutorial{video.channel_title ? ` · ${video.channel_title}` : ""}
                  </Text>
                  <Text
                    fontSize="sm"
                    fontWeight="semibold"
                    overflowWrap="anywhere"
                  >
                    {video.title}
                  </Text>
                  <Text fontSize="xs" color="gray.600">
                    {video.matched_using === "title_and_description"
                      ? "Matched using its title and description. "
                      : ""}
                    Content and vehicle compatibility have not been verified.
                  </Text>
                  {typeof video.timestamp === "number" &&
                    Number.isFinite(video.timestamp) &&
                    video.timestamp >= 0 && (
                      <Text fontSize="sm" color="gray.600">
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
                      colorPalette="brand"
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
