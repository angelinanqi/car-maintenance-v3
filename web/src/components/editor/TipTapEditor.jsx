"use client";

import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Image from "@tiptap/extension-image";
import Youtube from "@tiptap/extension-youtube";
import { Box } from "@chakra-ui/react";

import EditorToolbar from "./EditorToolbar";

export default function TiptapEditor({ content, onChange, readOnly = false, uploadImage }) {
  const editor = useEditor({
    editable: !readOnly,
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [1, 2, 3],
        },
      }),

      Image.configure({
        inline: false,
        allowBase64: false,
        HTMLAttributes: {
          class: "editor-image",
        },
      }),

      Youtube.configure({
        controls: true,
        nocookie: true,
        HTMLAttributes: {
          class: "editor-youtube",
        },
      }),
    ],

    content: content || "<p></p>",

    immediatelyRender: false,

    onUpdate: ({ editor }) => {
      onChange?.(editor.getHTML());
    },
  });

  return (
    <Box
      border="1px solid"
      borderColor="gray.200"
      borderRadius="lg"
      overflow="hidden"
      bg="white"
      w="100%"
      minH={readOnly ? "auto" : "400px"}
      display="flex"
      flexDirection="column"
    >
      {!readOnly && <EditorToolbar editor={editor} uploadImage={uploadImage} />}

      <Box
        p={6}
        flex="1"
        cursor="text"
        onClick={() => editor?.chain().focus().run()}
      >
        <EditorContent editor={editor} />
      </Box>

      {/* Editor-specific CSS */}
      <style jsx global>{`
        .ProseMirror {
          outline: none;
          min-height: ${readOnly ? "0" : "300px"};
          font-size: 16px;
          line-height: 1.7;
          color: #1a202c;
        }

        .ProseMirror:focus {
          outline: none;
        }

        /* =========================
           HEADINGS
           ========================= */

        .ProseMirror h1 {
          display: block;
          font-size: 32px;
          font-weight: 800;
          line-height: 1.2;
          margin: 24px 0 12px;
        }

        .ProseMirror h2 {
          display: block;
          font-size: 24px;
          font-weight: 700;
          line-height: 1.3;
          margin: 20px 0 10px;
        }

        .ProseMirror h3 {
          display: block;
          font-size: 19px;
          font-weight: 600;
          line-height: 1.4;
          margin: 16px 0 8px;
        }

        /* =========================
           PARAGRAPHS
           ========================= */

        .ProseMirror p {
          margin: 8px 0;
        }

        /* =========================
           BULLET LIST
           ========================= */

        .ProseMirror ul {
          display: block;
          list-style: disc;
          margin: 1em 0;
          padding-left: 40px;
        }

        /* =========================
           NUMBERED LIST
           ========================= */

        .ProseMirror ol {
          display: block;
          list-style: decimal;
          margin: 1em 0;
          padding-left: 40px;
        }

        /* =========================
           LIST ITEMS
           ========================= */

        .ProseMirror li {
          display: list-item;
          margin: 4px 0;
        }

        .ProseMirror li > p {
          margin: 0;
        }

        /* Nested bullet lists */

        .ProseMirror ul ul {
          list-style: circle;
        }

        .ProseMirror ul ul ul {
          list-style: square;
        }

        /* Nested numbered lists */

        .ProseMirror ol ol {
          list-style: lower-alpha;
        }

        .ProseMirror ol ol ol {
          list-style: lower-roman;
        }

        /* =========================
           MEDIA
           ========================= */

        .ProseMirror .editor-image {
          display: block;
          max-width: 100%;
          height: auto;
          border-radius: 10px;
          margin: 16px 0;
        }

        .ProseMirror .editor-youtube {
          display: block;
          width: 100%;
          max-width: 100%;
          aspect-ratio: 16 / 9;
          border: none;
          border-radius: 10px;
          margin: 16px 0;
        }

        /* =========================
           SELECTION
           ========================= */

        .ProseMirror ::selection {
          background: #ffe08a;
        }
      `}</style>
    </Box>
  );
}
