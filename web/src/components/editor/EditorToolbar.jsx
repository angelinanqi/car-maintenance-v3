"use client";

import { IMAGE_MAX_BYTES, IMAGE_CONTENT_TYPES } from "@/lib/config.mjs";
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

export default function EditorToolbar({ editor, uploadImage }) {
  const [isYoutubeOpen, setIsYoutubeOpen] = useState(false);
  const [isImageOpen, setIsImageOpen] = useState(false);

  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [mediaError, setMediaError] = useState("");
  const [uploading, setUploading] = useState(false);
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
      .setYoutubeVideo({
        src: url,
        width: 640,
        height: 360,
      })
      .run();

    if (!success) setMediaError("Enter a valid YouTube video URL.");
    if (success) {
      setMediaError("");
      setYoutubeUrl("");
      setIsYoutubeOpen(false);
    }
  };

  const handleImageSubmit = async (e) => {
    e.preventDefault();
    if (!selectedImageFile || uploading) return;
    setUploading(true);
    setMediaError("");
    try {
      if (selectedImageFile.size > IMAGE_MAX_BYTES) throw new Error("Image exceeds the upload size limit.");
      const src = await uploadImage(selectedImageFile);
      if (!editor.chain().focus().setImage({ src }).run()) throw new Error("Could not insert this image.");
      setSelectedImageFile(null);
      setIsImageOpen(false);
    } catch (error) { setMediaError(error.message); }
    finally { setUploading(false); }
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
            variant={editor.isActive("bold") ? "solid" : "outline"}
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
            variant={editor.isActive("italic") ? "solid" : "outline"}
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
            variant={editor.isActive("strike") ? "solid" : "outline"}
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
                variant={active ? "solid" : "outline"}
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
            variant={editor.isActive("bulletList") ? "solid" : "outline"}
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
            variant={editor.isActive("orderedList") ? "solid" : "outline"}
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
            onClick={() => { setMediaError(""); setIsImageOpen(true); }}
          >
            Insert image
          </Button>

          <Button
            type="button"
            size="xs"
            variant="outline"
            colorPalette="red"
            onClick={() => { setMediaError(""); setIsYoutubeOpen(true); }}
          >
            ▶ Add YouTube
          </Button>
        </Group>
      </HStack>

      {/* ================================= */}
      {/* YouTube Dialog                    */}
      {/* ================================= */}

      <Dialog.Root lazyMount unmountOnExit
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
                  variant="outline"
                  onClick={closeYoutubeDialog}
                >
                  Close
                </Button>
              </Dialog.Header>

              <Dialog.Body>
                {mediaError && <Text role="alert" color="red.600" mb={3}>{mediaError}</Text>}
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

      <Dialog.Root lazyMount unmountOnExit
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
                <Dialog.Title>Upload Image</Dialog.Title>

                <Button
                  type="button"
                  size="xs"
                  variant="outline"
                  onClick={closeImageDialog}
                >
                  Close
                </Button>
              </Dialog.Header>

              <Dialog.Body>
                {mediaError && <Text role="alert" color="red.600" mb={3}>{mediaError}</Text>}
                <Stack gap={4}>
                  <FileUpload.Root
                    accept={IMAGE_CONTENT_TYPES}
                    maxFileSize={IMAGE_MAX_BYTES}
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

                  <Text fontSize="sm" color="muted">
                    Images are stored persistently. Save the guide after inserting an image.
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
                  disabled={!selectedImageFile || uploading}
                  loading={uploading}
                >
                  Insert Image
                </Button>
              </Dialog.Footer>
            </form>
          </Dialog.Content>
        </Dialog.Positioner>
      </Dialog.Root>
    </>
  );
}
