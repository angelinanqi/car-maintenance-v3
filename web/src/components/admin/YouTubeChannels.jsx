"use client";
import Pagination, { usePagination } from "@/components/admin/Pagination";

import { useCallback, useEffect, useState } from "react";
import { Box, Button, Flex, Heading, Input, Stack, Text } from "@chakra-ui/react";
import { listAll, request } from "@/api/client.mjs";

const statusLabels = {
  queued: "Waiting to sync",
  syncing: "Syncing videos",
  ready: "Ready",
  failed: "Sync needs attention",
};

export default function YouTubeChannels() {
  const [channels, setChannels] = useState([]);
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [notice, setNotice] = useState("");

  const pagination = usePagination(channels);

  const load = useCallback(async (signal) => {
    try {
      const rows = await listAll("/admin/youtube-channels");
      if (signal.aborted) return;
      setChannels(rows);
      setLoadError("");
    } catch (cause) {
      if (!signal.aborted) setLoadError(cause.message);
    } finally {
      if (!signal.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (busy) return;
    const controller = new AbortController();
    // Schedule after completion so slow requests never build up overlapping polls.
    let timer;
    async function poll() {
      await load(controller.signal);
      if (!controller.signal.aborted) timer = setTimeout(poll, 10000);
    }
    poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [load, busy]);

  async function save(path, body, message) {
    if (busy) return;
    setBusy(path);
    setError("");
    setNotice("");
    try {
      const row = await request(path, { method: "POST", body });
      setChannels((current) => {
        const exists = current.some((channel) => channel.id === row.id);
        return exists ? current.map((channel) => channel.id === row.id ? row : channel) : [...current, row];
      });
      if (body) setUrl("");
      if (row.status === "failed") setError(row.error || "Sync could not start. Please retry.");
      else setNotice(message);
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy("");
    }
  }

  return (
    <Box bg="white" p={{ base: 5, md: 7 }} borderRadius="12px">
      <Heading size="lg" mb={3}>YouTube Channels</Heading>
      <Text color="muted" mb={5}>
        Add a channel to prepare all its available videos for chatbot recommendations.
        The chatbot automatically searches synced videos for relevant recommendations.
      </Text>
      <form onSubmit={(event) => {
        event.preventDefault();
        save("/admin/youtube-channels", { url: url.trim() }, "Channel added. Its videos are queued for syncing.");
      }}>
        <Stack gap={3}>
          <Box as="label" htmlFor="youtube-channel-url">Channel URL</Box>
          <Flex gap={3} wrap="wrap">
            <Input
              id="youtube-channel-url"
              type="url"
              required
              maxLength={500}
              placeholder="https://www.youtube.com/@channel"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              disabled={Boolean(busy)}
              flex="1"
              minW="220px"
            />
            <Button type="submit" disabled={loading || Boolean(busy) || !url.trim()} loading={busy === "/admin/youtube-channels"}>
              Add channel
            </Button>
          </Flex>
          <Text fontSize="sm" color="muted">Use a channel handle, /channel/ link, or /user/ link.</Text>
        </Stack>
      </form>
      {error && <Text role="alert" mt={4}>{error}</Text>}
      {loadError && <Text role="alert" mt={4}>{loadError} Retrying automatically.</Text>}
      {notice && <Text role="status" mt={4}>{notice}</Text>}
      {loading ? <Text role="status" mt={5}>Loading channels…</Text> : (
        <Stack mt={5} gap={5}>
          {!channels.length && !loadError && <Text color="muted">No YouTube channels added yet.</Text>}
          {pagination.items.map((channel) => {
            const pending = ["queued", "syncing"].includes(channel.status);
            const summary = channel.summary || {};
            return (
              <Flex key={channel.id} gap={4} justify="space-between" align="start" wrap="wrap" borderTopWidth="1px" pt={4}>
                <Stack gap={1} flex="1" minW="200px">
                  <Text fontWeight="600">{channel.channel_title || channel.url}</Text>
                  <Text as="a" href={channel.url} target="_blank" rel="noreferrer" fontSize="sm" color="muted" overflowWrap="anywhere">
                    {channel.url}
                  </Text>
                  <Text fontSize="sm">{statusLabels[channel.status] || channel.status}</Text>
                  {pending && <Text fontSize="sm" color="muted">Processing continues in the background. This list updates automatically.</Text>}
                  {summary.videos_discovered !== undefined && (
                    <Text fontSize="sm" color="muted">
                      {summary.videos_discovered} videos found · {summary.videos_failed || 0} failed · {summary.metadata_only_videos || 0} using title and description
                    </Text>
                  )}
                  {channel.last_synced_at && <Text fontSize="sm" color="muted">Last successful sync: {new Date(channel.last_synced_at).toLocaleString()}</Text>}
                  {channel.error && <Text role="alert" fontSize="sm">{channel.error}</Text>}
                </Stack>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={pending || Boolean(busy)}
                  loading={busy === `/admin/youtube-channels/${channel.id}/sync`}
                  onClick={() => save(`/admin/youtube-channels/${channel.id}/sync`, undefined, "Channel queued. Existing work will be reused while new videos are prepared.")}
                >
                  {channel.status === "failed" ? "Retry sync" : "Sync videos"}
                </Button>
              </Flex>
            );
          })}
          <Pagination {...pagination} label="YouTube Channels" />
        </Stack>
      )}
    </Box>
  );
}
