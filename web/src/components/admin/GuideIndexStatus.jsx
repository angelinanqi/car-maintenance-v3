"use client";

import { useEffect, useState } from "react";
import { Box, Button, Stack, Text } from "@chakra-ui/react";
import { guideIndexStatus, retryGuideIndexing } from "@/api/guides.mjs";

export default function GuideIndexStatus({ guideId }) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [retrying, setRetrying] = useState(false);
  useEffect(() => {
    let active = true;
    let timer;
    async function refresh() {
      try {
        const result = await guideIndexStatus(guideId);
        if (active) { setStatus(result); setError(""); }
      } catch (error) { if (active) setError(error.message); }
      if (active) timer = setTimeout(refresh, 10000);
    }
    refresh();
    return () => { active = false; clearTimeout(timer); };
  }, [guideId]);

  async function retry() {
    setRetrying(true);
    try {
      await retryGuideIndexing(guideId);
      setStatus({ status: "awaiting_index", warnings: [] });
      setError("");
    } catch (error) { setError(error.message); }
    finally { setRetrying(false); }
  }

  const labels = { processed: "Available in chat", awaiting_index: "Preparing for chat…",
    failed: "Could not prepare this guide for chat", draft: "Publish this guide to make it available in chat",
    category_hidden: "Publish this guide’s category to make it available in chat" };
  return <Box borderWidth="1px" borderRadius="lg" p={4}><Stack gap={2}>
    <Text role="status">{labels[status?.status] || "Checking chat availability…"}</Text>
    {status?.error && <Text fontSize="sm">{status.error}</Text>}
    {status?.warnings?.map((warning, index) => <Text fontSize="sm" key={index}>{warning}</Text>)}
    {error && <Text role="alert" color="red.600">{error}</Text>}
    {(status?.status === "failed" || status?.warnings?.length > 0) &&
      <Button size="sm" variant="outline" alignSelf="start" loading={retrying} onClick={retry}>Retry preparation</Button>}
  </Stack></Box>;
}
