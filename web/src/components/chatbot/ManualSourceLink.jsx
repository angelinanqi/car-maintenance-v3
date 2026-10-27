"use client";

import { useState } from "react";
import { Button, Text } from "@chakra-ui/react";
import { request } from "@/api/client.mjs";

export default function ManualSourceLink({ endpoint }) {
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState("");
  const [fallback, setFallback] = useState("");
  if (typeof endpoint !== "string" ||
      !/^\/chat\/sessions\/[0-9a-f-]+\/sources\/[0-9a-f-]+\/[0-9a-f-]+\/original$/.test(endpoint)) return null;

  async function openManual() {
    // Open synchronously from the click so browsers can allow the new tab.
    const tab = window.open("about:blank", "_blank");
    if (tab) tab.opener = null;
    setOpening(true);
    setError("");
    setFallback("");
    try {
      const result = await request(endpoint);
      const url = new URL(result.url);
      if (!["https:", "http:"].includes(url.protocol)) throw new Error("The manual link is unavailable.");
      if (tab && !tab.closed) tab.location.replace(url.href);
      else setFallback(url.href);
    } catch (failure) {
      if (tab) tab.close();
      setError(failure.message || "Could not open the manual. Please try again.");
    } finally {
      setOpening(false);
    }
  }

  return <>
    <Button size="xs" variant="outline" alignSelf="start" loading={opening} onClick={openManual}>
      Open manual
    </Button>
    {fallback && <a href={fallback} target="_blank" rel="noopener noreferrer">Open manual in a new tab</a>}
    {error && <Text fontSize="sm" role="alert">{error}</Text>}
  </>;
}
