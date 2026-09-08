"use client";

import { useState, useEffect } from "react";
import {
  Dialog,
  Button,
  Stack,
  Input,
  Field,
  HStack,
  Tag,
  FileUpload,
  Text,
} from "@chakra-ui/react";

export default function FileModal({ isOpen, onClose, editData = null }) {
  const [fileName, setFileName] = useState("");
  const [tagInput, setTagInput] = useState("");

  // Preset tags available to click and choose from
  const [availableTags, setAvailableTags] = useState([
    "Manuals",
    "Others",
  ]);
  // Active selected tags
  const [selectedTags, setSelectedTags] = useState(["Manuals"]);

  const isEditMode = Boolean(editData);

  // Populate data when editing, or reset when opening fresh
  useEffect(() => {
    if (editData) {
      setFileName(editData.name || "");
      setSelectedTags(editData.category ? [editData.category] : [""]);
    } else {
      setFileName("");
      setSelectedTags([""]);
    }
  }, [editData, isOpen]);

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
    if (e.key === "Enter" && tagInput.trim()) {
      e.preventDefault();
      const newTag = tagInput.trim();

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

    const payload = {
      fileName,
      tags: selectedTags,
    };

    if (isEditMode) {
      // BACKEND UPDATE API CALL HERE
      console.log("Saving Edits for ID:", editData.id, payload);
    } else {
      // BACKEND UPLOAD API CALL HERE
      console.log("Uploading New File:", payload);
    }

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
                {isEditMode ? "Edit Document" : "Upload New File"}
              </Dialog.Title>
              <Button
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
                {/* 1. File Upload Component (Upload Mode Only) */}
                {!isEditMode && (
                  <Field.Root required>
                    <Field.Label>Attachment</Field.Label>
                    <FileUpload.Root maxFiles={1}>
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
                        <Tag.Root
                          key={tag}
                          size="lg"
                          variant={isSelected ? "solid" : "outline"}
                          colorPalette={isSelected ? "blue" : "gray"}
                          cursor="pointer"
                          onClick={() => handleToggleTag(tag)}
                          userSelect="none"
                        >
                          <Tag.Label>{tag}</Tag.Label>
                        </Tag.Root>
                      );
                    })}
                  </HStack>

                  {/* Input to create a custom tag */}
                  <Input
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
              <Button variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" colorPalette="blue">
                {isEditMode ? "Save Changes" : "Upload File"}
              </Button>
            </Dialog.Footer>
          </form>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
}
