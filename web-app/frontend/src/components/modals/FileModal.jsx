"use client";

import { useState } from "react";
import {
  Dialog,
  Button,
  Stack,
  Input,
  Field,
  HStack,
  FileUpload,
  Text,
} from "@chakra-ui/react";

export default function FileModal({ isOpen, onClose, onSave, editData = null }) {
  const [fileName, setFileName] = useState(editData?.name || "");
  const [tagInput, setTagInput] = useState("");
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");

  // Preset tags available to click and choose from
  const [availableTags, setAvailableTags] = useState([...new Set(["Manuals", "Other", ...(editData?.tags || [])])]);
  const [selectedTags, setSelectedTags] = useState(editData?.tags || []);
  const isEditMode = Boolean(editData);

  // Click handler to toggle tag selection ON/OFF
  const handleToggleTag = (tag) => {
    if (selectedTags.includes(tag)) {
      setSelectedTags(selectedTags.filter((t) => t !== tag));
    } else {
      setSelectedTags([...selectedTags, tag]);
    }
  };

  // Add a brand new tag on pressing 'Enter' inside input
  const handleAddCustomTag = (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      if (!tagInput.trim()) return;
      const newTag = availableTags.find((tag) => tag.toLowerCase() === tagInput.trim().toLowerCase()) || tagInput.trim();

      // Add to available tags if not present
      if (!availableTags.includes(newTag)) {
        setAvailableTags([...availableTags, newTag]);
      }
      // Auto-select the newly added tag
      if (!selectedTags.includes(newTag)) {
        setSelectedTags([...selectedTags, newTag]);
      }
      setTagInput("");
    }
  };

  // Submit handler
  const handleSubmit = (e) => {
    e.preventDefault();

    if (!fileName.trim() || (!isEditMode && !file)) {
      setError("Enter a name and choose a file before adding the document.");
      return;
    }
    onSave({ name: fileName.trim(), tags: selectedTags, file: isEditMode ? editData.file : file });
    onClose();
  };

  return (
    <Dialog.Root open={isOpen} onOpenChange={(e) => !e.open && onClose()}>
      <Dialog.Backdrop />
      <Dialog.Positioner>
        <Dialog.Content>
          <form onSubmit={handleSubmit}>
            {/* HEADER */}
            <Dialog.Header
              display="flex"
              justifyContent="space-between"
              alignItems="center"
            >
              <Dialog.Title>
                {isEditMode ? "Edit Document" : "Add Local Document"}
              </Dialog.Title>
              <Button
                type="button"
                variant="ghost"
                size="xs"
                onClick={onClose}
                aria-label="Close"
              >
                ✕
              </Button>
            </Dialog.Header>

            {/* BODY */}
            <Dialog.Body>
              <Stack gap={4}>
                <Text fontSize="sm" color="gray.600">Files stay in memory for this prototype session. Nothing is uploaded or processed.</Text>
                {error && <Text role="alert" color="red.600">{error}</Text>}
                {/* 1. File Upload Component (Upload Mode Only) */}
                {!isEditMode && (
                  <Field.Root required>
                    <Field.Label>Attachment</Field.Label>
                    <FileUpload.Root maxFiles={1} onFileReject={() => setError("Choose one file at a time.")} onFileChange={(details) => {
                      const selected = details.acceptedFiles[0] || null;
                      setFile(selected);
                      if (selected && !fileName.trim()) setFileName(selected.name);
                    }}>
                      <FileUpload.Dropzone
                        w="100%"
                        p={6}
                        border="2px dashed"
                        borderColor="gray.200"
                        borderRadius="md"
                        textAlign="center"
                        cursor="pointer"
                      >
                        <FileUpload.DropzoneContent>
                          <FileUpload.Label>
                            Drag and drop files here, or click to browse
                          </FileUpload.Label>
                        </FileUpload.DropzoneContent>
                      </FileUpload.Dropzone>
                      <FileUpload.HiddenInput />
                      {file && (
                        <FileUpload.ItemGroup>
                          <FileUpload.Item file={file}>
                            <FileUpload.ItemName />
                            <FileUpload.ItemSizeText />
                            <FileUpload.ItemDeleteTrigger />
                          </FileUpload.Item>
                        </FileUpload.ItemGroup>
                      )}
                    </FileUpload.Root>
                  </Field.Root>
                )}

                {/* 2. File Name Input */}
                <Field.Root required>
                  <Field.Label>File Name</Field.Label>
                  <Input
                    placeholder="e.g. Mercedes Car Manual"
                    value={fileName}
                    onChange={(e) => setFileName(e.target.value)}
                  />
                </Field.Root>

                {/* 3. Clickable Tag Selection Section */}
                <Field.Root>
                  <Field.Label>Select Tags</Field.Label>

                  {/* Clickable Tag Badges */}
                  <HStack gap={2} mb={2} wrap="wrap">
                    {availableTags.map((tag) => {
                      const isSelected = selectedTags.includes(tag);
                      return (
                        <Button type="button" aria-pressed={isSelected}
                          key={tag}
                          size="sm"
                          variant={isSelected ? "solid" : "outline"}
                          colorPalette={isSelected ? "blue" : "gray"}
                          cursor="pointer"
                          onClick={() => handleToggleTag(tag)}
                          userSelect="none"
                        >
                          {tag}
                        </Button>
                      );
                    })}
                  </HStack>

                  {/* Input to create a custom tag */}
                  <Input
                    aria-label="New tag"
                    placeholder="Type custom tag & press Enter to add"
                    value={tagInput}
                    onChange={(e) => setTagInput(e.target.value)}
                    onKeyDown={handleAddCustomTag}
                    size="sm"
                  />
                  <Text fontSize="xs" color="gray.500" mt={1}>
                    Selected:{" "}
                    {selectedTags.length > 0 ? selectedTags.join(", ") : "None"}
                  </Text>
                </Field.Root>
              </Stack>
            </Dialog.Body>

            {/* FOOTER */}
            <Dialog.Footer>
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" colorPalette="blue">
                {isEditMode ? "Save Changes" : "Add Document"}
              </Button>
            </Dialog.Footer>
          </form>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
}
