"use client";

import { useState } from "react";
import { Box, Button, Image, Stack, Text } from "@chakra-ui/react";

function mediaUrl(item) {
  try {
    const url = new URL(item.url);
    if (!["https:", "http:"].includes(url.protocol) || url.username || url.password) return null;
    if (item.kind === "video" && item.start_seconds) {
      if (["youtu.be", "youtube.com", "www.youtube.com", "m.youtube.com", "youtube-nocookie.com", "www.youtube-nocookie.com"].includes(url.hostname)) {
        url.searchParams.delete("start"); url.searchParams.delete("t");
        url.searchParams.set(url.pathname.startsWith("/embed/") ? "start" : "t", url.pathname.startsWith("/embed/") ? String(item.start_seconds) : `${item.start_seconds}s`);
      } else url.hash = `t=${item.start_seconds}`;
    }
    return url.href;
  } catch { return null; }
}

function MediaItem({ item }) {
  const [failed, setFailed] = useState(false);
  const url = mediaUrl(item);
  if (!url) return null;
  return <Box borderWidth="1px" borderRadius="md" p={3}><Stack gap={2}>
    <Text fontWeight="semibold" fontSize="sm">{item.title}{item.source_label ? ` [${item.source_label}]` : ""}</Text>
    {item.step_title && <Text fontSize="xs" color="muted">Step: {item.step_title}</Text>}
    {item.kind === "image" && (failed ? <Text fontSize="sm">Image unavailable. {item.description}</Text> : <Image src={url} alt={item.description || item.title} loading="lazy" maxH="360px" objectFit="contain" onError={() => setFailed(true)} />)}
    {!failed && item.description && <Text fontSize="sm" whiteSpace="pre-wrap">{item.description}</Text>}
    {item.vehicle_context && <Text fontSize="xs">Applies to: {item.vehicle_context}</Text>}
    {item.source_reference && <Text fontSize="xs" overflowWrap="anywhere">Source: {item.source_reference}</Text>}
    {item.kind === "video" && item.asset_id && (failed ? <Text fontSize="sm">Video unavailable. Use the written instructions.</Text> : <video src={url} controls preload="metadata" onError={() => setFailed(true)} style={{ width: "100%", maxHeight: 360 }} />)}
    {item.kind === "video" && !item.asset_id && <Button asChild variant="outline" size="sm" alignSelf="start"><a href={url} target="_blank" rel="noopener noreferrer">Watch from {Math.floor((item.start_seconds || 0) / 60)}:{String((item.start_seconds || 0) % 60).padStart(2, "0")}</a></Button>}
  </Stack></Box>;
}

export default function ContentMedia({ items = [] }) {
  if (!items.length) return null;
  return <Box as="section" aria-label="Related images and videos"><Stack gap={3}>
    <Text fontSize="sm" fontWeight="semibold">Related images and videos</Text>
    {items.map(item => <MediaItem key={`${item.media_id || item.id}-${item.start_seconds || 0}`} item={item} />)}
  </Stack></Box>;
}
