"use client";

import { useState } from "react";
import {
  HStack,
  Button,
  Group,
  Separator,
  Dialog,
  Input,
  Field,
  Stack,
  Text,
  FileUpload,
} from "@chakra-ui/react";

export default function EditorToolbar({ editor }) {
  const [isYoutubeOpen, setIsYoutubeOpen] = useState(false);
  const [isImageOpen, setIsImageOpen] = useState(false);

  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [selectedImageFile, setSelectedImageFile] = useState(null);

  if (!editor) {
    return null;
  }

  const handleYoutubeSubmit = (e) => {
    e.preventDefault();

    const url = youtubeUrl.trim();

    if (!url) {
      return;
    }

    const success = editor
      .chain()
      .focus()
      .setYoutube({
        src: url,
        width: 640,
        height: 360,
      })
      .run();

    if (success) {
      setYoutubeUrl("");
      setIsYoutubeOpen(false);
    }
  };

  const handleImageSubmit = (e) => {
    e.preventDefault();

    if (!selectedImageFile) {
      return;
    }

    const reader = new FileReader();

    reader.onload = () => {
      const src = reader.result;

      if (typeof src !== "string") {
        return;
      }

      const success = editor
        .chain()
        .focus()
        .setImage({
          src,
        })
        .run();

      if (success) {
        setSelectedImageFile(null);
        setIsImageOpen(false);
      }
    };

    reader.readAsDataURL(selectedImageFile);
  };

  const closeYoutubeDialog = () => {
    setYoutubeUrl("");
    setIsYoutubeOpen(false);
  };

  const closeImageDialog = () => {
    setSelectedImageFile(null);
    setIsImageOpen(false);
  };

  return (
    <>
      <HStack
        gap={2}
        p={3}
        bg="gray.50"
        borderBottom="1px solid"
        borderColor="gray.200"
        wrap="wrap"
        position="sticky"
        top={0}
        zIndex={10}
      >
        {/* ========================= */}
        {/* 1. Basic Text Formatting  */}
        {/* ========================= */}

        <Group gap={1}>
          <Button
            type="button"
            size="xs"
            variant={editor.isActive("bold") ? "solid" : "ghost"}
            colorPalette={editor.isActive("bold") ? "blue" : "gray"}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => {
              editor.chain().focus().toggleBold().run();
            }}
          >
            <strong>B</strong>
          </Button>

          <Button
            type="button"
            size="xs"
            variant={editor.isActive("italic") ? "solid" : "ghost"}
            colorPalette={editor.isActive("italic") ? "blue" : "gray"}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => {
              editor.chain().focus().toggleItalic().run();
            }}
          >
            <em>I</em>
          </Button>

          <Button
            type="button"
            size="xs"
            variant={editor.isActive("strike") ? "solid" : "ghost"}
            colorPalette={editor.isActive("strike") ? "blue" : "gray"}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => {
              editor.chain().focus().toggleStrike().run();
            }}
          >
            <s>S</s>
          </Button>
        </Group>

        <Separator orientation="vertical" h="20px" />

        {/* ========================= */}
        {/* 2. Headings               */}
        {/* ========================= */}

        <Group gap={1}>
          {[1, 2, 3].map((level) => {
            const active = editor.isActive("heading", { level });

            return (
              <Button
                key={level}
                type="button"
                size="xs"
                variant={active ? "solid" : "ghost"}
                colorPalette={active ? "blue" : "gray"}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  editor.chain().focus().toggleHeading({ level }).run();
                }}
              >
                H{level}
              </Button>
            );
          })}
        </Group>

        <Separator orientation="vertical" h="20px" />

        {/* ========================= */}
        {/* 3. Lists                  */}
        {/* ========================= */}

        <Group gap={1}>
          <Button
            type="button"
            size="xs"
            variant={editor.isActive("bulletList") ? "solid" : "ghost"}
            colorPalette={editor.isActive("bulletList") ? "blue" : "gray"}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => {
              editor.chain().focus().toggleBulletList().run();
            }}
          >
            • Bullet List
          </Button>

          <Button
            type="button"
            size="xs"
            variant={editor.isActive("orderedList") ? "solid" : "ghost"}
            colorPalette={editor.isActive("orderedList") ? "blue" : "gray"}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => {
              editor.chain().focus().toggleOrderedList().run();
            }}
          >
            1. Numbered List
          </Button>
        </Group>

        {/* ========================= */}
        {/* 4. Media                  */}
        {/* ========================= */}

        <Group gap={1} ml="auto">
          <Button
            type="button"
            size="xs"
            variant="outline"
            colorPalette="teal"
            onClick={() => setIsImageOpen(true)}
          >
            📷 Upload Image
          </Button>

          <Button
            type="button"
            size="xs"
            variant="outline"
            colorPalette="red"
            onClick={() => setIsYoutubeOpen(true)}
          >
            ▶ Add YouTube
          </Button>
        </Group>
      </HStack>

      {/* ================================= */}
      {/* YouTube Dialog                    */}
      {/* ================================= */}

      <Dialog.Root
        open={isYoutubeOpen}
        onOpenChange={(e) => {
          setIsYoutubeOpen(e.open);

          if (!e.open) {
            setYoutubeUrl("");
          }
        }}
      >
        <Dialog.Backdrop />

        <Dialog.Positioner>
          <Dialog.Content>
            <form onSubmit={handleYoutubeSubmit}>
              <Dialog.Header
                display="flex"
                justifyContent="space-between"
                alignItems="center"
              >
                <Dialog.Title>Embed YouTube Video</Dialog.Title>

                <Button
                  type="button"
                  size="xs"
                  variant="ghost"
                  onClick={closeYoutubeDialog}
                >
                  ✕
                </Button>
              </Dialog.Header>

              <Dialog.Body>
                <Field.Root required>
                  <Field.Label>YouTube Link</Field.Label>

                  <Input
                    placeholder="https://www.youtube.com/watch?v=..."
                    value={youtubeUrl}
                    onChange={(e) => setYoutubeUrl(e.target.value)}
                  />
                </Field.Root>
              </Dialog.Body>

              <Dialog.Footer>
                <Button
                  type="button"
                  variant="outline"
                  onClick={closeYoutubeDialog}
                >
                  Cancel
                </Button>

                <Button
                  type="submit"
                  colorPalette="red"
                  disabled={!youtubeUrl.trim()}
                >
                  Insert Video
                </Button>
              </Dialog.Footer>
            </form>
          </Dialog.Content>
        </Dialog.Positioner>
      </Dialog.Root>

      {/* ================================= */}
      {/* Image Dialog (Pure Chakra)        */}
      {/* ================================= */}

      <Dialog.Root
        open={isImageOpen}
        onOpenChange={(e) => {
          setIsImageOpen(e.open);

          if (!e.open) {
            setSelectedImageFile(null);
          }
        }}
      >
        <Dialog.Backdrop />

        <Dialog.Positioner>
          <Dialog.Content>
            <form onSubmit={handleImageSubmit}>
              <Dialog.Header
                display="flex"
                justifyContent="space-between"
                alignItems="center"
              >
                <Dialog.Title>Upload Photo</Dialog.Title>

                <Button
                  type="button"
                  size="xs"
                  variant="ghost"
                  onClick={closeImageDialog}
                >
                  ✕
                </Button>
              </Dialog.Header>

              <Dialog.Body>
                <Stack gap={4}>
                  <FileUpload.Root
                    accept={["image/*"]}
                    maxFiles={1}
                    onFileChange={(details) => {
                      setSelectedImageFile(details.acceptedFiles[0] || null);
                    }}
                  >
                    <FileUpload.HiddenInput />
                    <FileUpload.Dropzone width="full" p={6}>
                      <FileUpload.DropzoneContent>
                        <Text fontSize="sm">
                          Drag and drop an image here, or click to choose a file
                        </Text>
                      </FileUpload.DropzoneContent>
                    </FileUpload.Dropzone>

                    <FileUpload.ItemGroup mt={2}>
                      {selectedImageFile && (
                        <FileUpload.Item file={selectedImageFile}>
                          <FileUpload.ItemName />
                          <FileUpload.ItemSizeText />
                          <FileUpload.ItemDeleteTrigger
                            onClick={() => setSelectedImageFile(null)}
                          />
                        </FileUpload.Item>
                      )}
                    </FileUpload.ItemGroup>
                  </FileUpload.Root>

                  <Text fontSize="xs" color="gray.500">
                    Tip: You can also copy any image to your clipboard and paste
                    it directly into the editor body with Ctrl+V / Cmd+V!
                  </Text>
                </Stack>
              </Dialog.Body>

              <Dialog.Footer>
                <Button
                  type="button"
                  variant="outline"
                  onClick={closeImageDialog}
                >
                  Cancel
                </Button>

                <Button
                  type="submit"
                  colorPalette="teal"
                  disabled={!selectedImageFile}
                >
                  Upload & Insert
                </Button>
              </Dialog.Footer>
            </form>
          </Dialog.Content>
        </Dialog.Positioner>
      </Dialog.Root>
    </>
  );
}
