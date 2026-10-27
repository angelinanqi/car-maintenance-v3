import { Box } from "@chakra-ui/react";
import Markdown from "react-markdown";

// Source images are rendered separately from backend-authorised attachments.
// Model-written HTML and image URLs must not become executable page content.
export default function ChatAnswer({ children }) {
  return (
    <Box fontSize="md" overflowWrap="anywhere" lineHeight="1.7" css={{
      "& p": { marginBlock: "0 0.8em" },
      "& p:last-child": { marginBottom: 0 },
      "& h1, & h2, & h3, & h4, & h5, & h6": {
        fontSize: "1em", fontWeight: 600, marginBlock: "1em 0.4em", lineHeight: 1.4,
      },
      "& :first-child": { marginTop: 0 },
      "& ul": { paddingInlineStart: "1.5em", listStyleType: "disc", marginBlock: "0.4em 1em" },
      "& ol": { paddingInlineStart: "1.5em", listStyleType: "decimal", marginBlock: "0.4em 1em" },
      "& li": { paddingInlineStart: "0.2em", marginBlock: "0.35em" },
      "& li > p": { marginBottom: "0.35em" },
      "& a": { textDecoration: "underline" },
      "& blockquote": { borderInlineStartWidth: "3px", paddingInlineStart: "1em", marginBlock: "1em" },
      "& pre": { overflowX: "auto", padding: "0.75em", background: "bg.muted", borderRadius: "md" },
    }}>
      <Markdown skipHtml disallowedElements={["img"]} components={{
        a: ({ href, children }) => href && /^https?:\/\//i.test(href)
          ? <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
          : <span>{children}</span>,
      }}>{children}</Markdown>
    </Box>
  );
}
