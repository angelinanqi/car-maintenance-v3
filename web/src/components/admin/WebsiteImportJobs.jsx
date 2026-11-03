"use client";
import { useEffect, useState } from 'react';
import { Box, Button, Flex, Stack, Text } from '@chakra-ui/react';
import { request } from '@/api/client.mjs';
import { ACTIVE_IMPORTS, importLabel } from '@/lib/websiteImports.mjs';

export default function WebsiteImportJobs({ onOpen, refreshKey = 0 }) {
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState('');
  const [offset, setOffset] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let timer;
    async function poll() {
      try {
        const rows = await request(`/website-imports?offset=${offset}&limit=10`, { signal: controller.signal, timeoutMs: 15000 });
        if (controller.signal.aborted) return;
        setJobs(rows); setError('');
        timer = setTimeout(poll, rows.some(job => ACTIVE_IMPORTS.has(job.status)) ? 3000 : 15000);
      } catch (cause) {
        if (!controller.signal.aborted) { setError(cause.message); timer = setTimeout(poll, 15000); }
      }
    }
    poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [offset, refreshKey]);
  if (!jobs.length && !error && offset === 0) return null;
  return <Box borderWidth="1px" borderRadius="12px" p={4}>
    <Stack gap={3}>
      <Text fontWeight="600">Website imports</Text>
      <Text fontSize="sm" color="muted">Accepted imports continue when you close this page. Open a ready PDF to preview and process it.</Text>
      {error && <Text role="alert" color="red.600">{error}</Text>}
      {jobs.map(job => <Flex key={job.id} gap={3} justify="space-between" align="center">
        <Box minW={0}>
          <Text fontWeight="500" overflowWrap="anywhere">{job.title || job.submitted_url}</Text>
          <Text fontSize="sm" color={job.status === 'failed' ? 'red.600' : 'muted'}>{importLabel(job)}</Text>
        </Box>
        <Button size="sm" variant="outline" flexShrink={0} onClick={() => onOpen(job.id)}>View import</Button>
      </Flex>)}
      <Flex gap={3}>
        {offset > 0 && <Button size="sm" variant="outline" onClick={() => setOffset(Math.max(0, offset - 10))}>Newer</Button>}
        {jobs.length === 10 && <Button size="sm" variant="outline" onClick={() => setOffset(offset + 10)}>Older</Button>}
      </Flex>
    </Stack>
  </Box>;
}
