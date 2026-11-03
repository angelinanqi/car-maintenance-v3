"use client";

import { useState } from "react";
import { Box, Button, Stack, Text } from "@chakra-ui/react";
import { request } from "@/api/client.mjs";
import { API_URL } from "@/lib/config.mjs";

function sourceEndpoint(value, kind) {
  return typeof value === "string" &&
    /^\/chat\/sessions\/[0-9a-f-]+\/sources\/[0-9a-f-]+\/[0-9a-f-]+\/(image|table)-\d{5,}\/(?:pages\/[1-9]\d*\/)?(image|original)$/.test(value) &&
    value.endsWith(`/${kind}`);
}

function OriginalPage({ page }) {
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const available = page.asset_available !== false && sourceEndpoint(page.asset_endpoint, "image");
  const url = available ? `${API_URL}${page.asset_endpoint}${attempt ? `?retry=${attempt}` : ""}` : "";
  return <Box w="100%">
    <Text fontSize="sm" fontWeight="medium">Original PDF page {page.page}{page.role === "section_context" ? " · Related table context" : ""}</Text>
    {url && !failed ? <a href={url} target="_blank" rel="noopener noreferrer" aria-label={`Enlarge original PDF page ${page.page}`}>
      <img src={url} crossOrigin="use-credentials" loading="lazy" alt={`Original PDF page ${page.page}, including table headers and notes`}
        onError={() => setFailed(true)} style={{ display: "block", width: "100%", maxHeight: 440, objectFit: "contain", background: "white" }} />
      <Text as="span" fontSize="sm">Enlarge page {page.page}</Text>
    </a> : <Text fontSize="sm" role="alert">Page preview unavailable. Open the original source to check this page.</Text>}
    {available && failed && <Button size="xs" variant="outline" onClick={() => { setAttempt(attempt + 1); setFailed(false); }}>Retry page</Button>}
  </Box>;
}

export default function ChatAttachment({ attachment, sourceLabel }) {
  const [loadedImage, setLoadedImage] = useState("");
  const [failedImage, setFailedImage] = useState("");
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [original, setOriginal] = useState("");
  const [loadingOriginal, setLoadingOriginal] = useState(false);
  const endpoint = attachment.asset_endpoint;
  const available = sourceEndpoint(endpoint, "image") && attachment.asset_available !== false;
  const image = available ? `${API_URL}${endpoint}${attempt ? `?retry=${attempt}` : ""}` : "";
  const imageFailed = image && failedImage === image;
  const table = attachment.kind === "table" && attachment.structure_valid === true &&
    typeof attachment.html === "string" && attachment.html.length <= 1000000;
  const title = attachment.identity_review?.title || attachment.generated_identity?.title || attachment.caption || attachment.section_path?.at(-1) || "Manual illustration";
  const pages = (Array.isArray(attachment.pages) ? attachment.pages : []).join(", ");
  const previews = attachment.kind === "table" && Array.isArray(attachment.page_previews) ? attachment.page_previews : [];

  async function loadOriginal() {
    if (!sourceEndpoint(attachment.source_endpoint, "original")) return;
    setLoadingOriginal(true);
    try {
      const result = await request(attachment.source_endpoint);
      if (!/^https?:\/\//i.test(result.url)) throw new Error("The original source link is unavailable.");
      const url = new URL(result.url);
      if (attachment.pages?.length) url.hash = `page=${attachment.pages[0]}`;
      setOriginal(url.href);
    } catch (failure) {
      setError(failure.message);
    } finally {
      setLoadingOriginal(false);
    }
  }

  return (
    <Box as="figure" borderWidth="1px" borderRadius="md" p={3} m={0}>
      <Stack gap={2} align="start">
        <Text fontSize="sm" fontWeight="medium">{title}</Text>
        {previews.map((page) => <OriginalPage key={page.page} page={page} />)}
        {previews.length > 0 && available && <Text fontSize="sm">Enlarged table detail</Text>}
        {image && !imageFailed && <Box bg="white" borderRadius="sm" p={3} w="100%" minH="100px" display="flex" justifyContent="center" alignItems="center">
          <a href={image} target="_blank" rel="noopener noreferrer" aria-label="Enlarge source image (opens in a new tab)">
            <img key={image} src={image} crossOrigin="use-credentials"
              alt={attachment.caption || `Original manual illustration${pages ? `, page ${pages}` : ""}`}
              onLoad={() => setLoadedImage(image)} onError={() => setFailedImage(image)}
              style={{ display: "block", minWidth: 96, maxWidth: "100%", maxHeight: 360, objectFit: "contain" }} />
          </a>
        </Box>}
        {image && loadedImage !== image && !imageFailed && <Text fontSize="sm" role="status">Loading manual image…</Text>}
        {image && loadedImage === image && !imageFailed && <a href={image} target="_blank" rel="noopener noreferrer">Enlarge image</a>}
        {(!available || imageFailed) && !table && <Text fontSize="sm" role="alert">The original preview is unavailable. Open the original source to view this reference.</Text>}
        {table && <details open={!available || imageFailed}>
          <summary>View extracted table</summary>
          <Text fontSize="xs" color="muted">Extracted layout; check values and notes against the original.</Text>
          {/* HTML comes only from the backend's sanitised source-element archive. */}
          <Box overflowX="auto" maxH="360px" overflowY="auto" maxW="100%"
            css={{ "& table": { borderCollapse: "collapse" },
              "& td, & th": { border: "1px solid", borderColor: "gray.300", padding: "0.5em" } }}
            dangerouslySetInnerHTML={{ __html: attachment.html }} />
        </details>}
        {(attachment.notes || []).map((note, index) => <Text key={index} fontSize="sm">{note}</Text>)}
        {attachment.notes?.length > 0 && !attachment.association_verified &&
          <Text fontSize="xs" color="muted">Nearby notes are included as context; their association is unverified.</Text>}
        {error && <Text fontSize="sm" role="alert">{error}</Text>}
        {imageFailed && <Button size="xs" variant="outline" onClick={() => setAttempt(attempt + 1)}>Retry image</Button>}
        <Text as="figcaption" fontSize="xs" color="muted" overflowWrap="anywhere">{sourceLabel ? `[${sourceLabel}]` : attachment.document_title}{pages && ` · Page ${pages}`}</Text>
        {!attachment.source_fidelity_verified && <Text fontSize="xs" color="muted">Check symbols, values and notes against the original source.</Text>}
        {original ? <a href={original} target="_blank" rel="noopener noreferrer">Open original source</a>
          : sourceEndpoint(attachment.source_endpoint, "original") && <Button size="xs" variant="outline" loading={loadingOriginal} onClick={loadOriginal}>Get original source</Button>}
      </Stack>
    </Box>
  );
}
