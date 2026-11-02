import { Box, Button, Heading, Stack, Text } from '@chakra-ui/react';
import ManualSourceLink from './ManualSourceLink';

export default function ChatSourcePanel({ messages, selectedId, onSelect, onFind }) {
  const answers = messages.filter(message => message.role === 'assistant');
  const selected = answers.find(message => message.id === selectedId) || answers[answers.length - 1];
  const sources = (Array.isArray(selected?.sources) ? selected.sources : []).filter(Boolean);
  return <Stack gap={4}>
    <Box>
      <Heading size="md">Answer Sources</Heading>
      <Text fontSize="sm" color="muted" mt={1}>References returned with the selected answer. Original documents open through the existing secure viewer.</Text>
    </Box>
    {answers.length > 1 && <label>
      <Text as="span" fontSize="sm" fontWeight="600">Inspect an Answer</Text>
      <select value={selected?.id || ''} onChange={event => onSelect(event.target.value)}>
        {answers.map((answer, index) => <option key={answer.id} value={answer.id}>
          Answer {index + 1}: {(answer.answer || '').slice(0, 70)}
        </option>)}
      </select>
    </label>}
    {!selected && <Text fontSize="sm" color="muted">Ask a question to see the sources used in its answer. Page references and related videos also remain with each reply.</Text>}
    {selected && !sources.length && <Text fontSize="sm" color="muted">No supporting sources were returned with this answer. Check any limitations stated in the reply.</Text>}
    {sources.map((source, index) => <Box key={`${source.label || 'source'}-${index}`} borderWidth="1px" borderRadius="14px" p={4} bg="white">
      <Stack gap={2}>
        <Text fontSize="xs" fontWeight="700" color="muted">Reference {source.label || index + 1}</Text>
        <Text fontSize="sm" fontWeight="600">{source.title || source.document_title || 'Reference Document'}</Text>
        {source.page != null && <Text fontSize="sm">PDF Page {source.page}</Text>}
        {source.source_reference && <Text fontSize="sm" color="muted">{source.source_reference}</Text>}
        {source.section_path?.length > 0 && <Text fontSize="sm" color="muted">{source.section_path.join(' / ')}</Text>}
        {source.source_kind === 'website' && /^https?:\/\//.test(source.original_url || '') && <Text as="a" href={source.original_url} target="_blank" rel="noopener noreferrer" fontSize="sm" color="blue.700">Original website article</Text>}
        {source.retrieved_at && <Text fontSize="xs" color="muted">Snapshot retrieved {new Date(source.retrieved_at).toLocaleString()}</Text>}
        {source.as_of && <Text fontSize="xs" color="muted">As of {source.as_of}</Text>}
        {source.reviewed_at && <Text fontSize="xs" color="muted">Reviewed {source.reviewed_at}</Text>}
        {source.source_type === 'manual' && <ManualSourceLink endpoint={source.source_endpoint} />}
      </Stack>
    </Box>)}
    {selected && <Button variant="outline" size="sm" onClick={() => onFind(selected.id)}>Find This Answer in Conversation</Button>}
  </Stack>;
}
