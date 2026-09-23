"use client";

import { useState } from "react";
import { validateDocumentFile } from "@/lib/prototypeDocuments.mjs";
import { chatOption as chatScopes } from "@/components/chatbot/chatScopes";
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

export default function FileModal({
  isOpen,
  onClose,
  onSave,
  editData = null,
  tags = [],
}) {
  const [fileName, setFileName] = useState(editData?.name || "");
  const [tagInput, setTagInput] = useState("");
  const [files, setFiles] = useState(editData?.file ? [editData.file] : []);
  const [carModel, setCarModel] = useState(editData?.carModel || "general");
  const [error, setError] = useState("");

  // Preset tags available to click and choose from
  const [availableTags, setAvailableTags] = useState([
    ...new Set(["Manuals", "Other", ...tags, ...(editData?.tags || [])]),
  ]);
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
      const newTag =
        availableTags.find(
          (tag) => tag.toLowerCase() === tagInput.trim().toLowerCase(),
        ) || tagInput.trim();

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

    if (
      ((isEditMode || files.length === 1) && !fileName.trim()) ||
      (!isEditMode && files.length === 0)
    ) {
      setError("Enter a name and choose a file before adding the document.");
      return;
    }
    const fileError = files.map(validateDocumentFile).find(Boolean);
    if (fileError) {
      setError(fileError);
      return;
    }
    onSave({ name: fileName.trim(), tags: selectedTags, carModel, files });
    onClose();
  };

  return (
    <Dialog.Root open={isOpen} onOpenChange={(e) => !e.open && onClose()}>
      <Dialog.Backdrop />
      <Dialog.Positioner>
        <Dialog.Content maxH="85vh" overflowY="auto">
          <form onSubmit={handleSubmit}>
            {/* HEADER */}
            <Dialog.Header
              display="flex"
              justifyContent="space-between"
              alignItems="center"
            >
              <Dialog.Title>
                {isEditMode ? "Edit Document" : "Add Local Documents"}
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
                <Text fontSize="sm" color="gray.600">
                  PDF and Markdown files stay in this tab. Processing is a demo
                  and does not add knowledge to the real chatbot.
                </Text>
                {error && (
                  <Text role="alert" color="red.600">
                    {error}
                  </Text>
                )}
                {/* Local attachments; edit supports replacement. */}
                <Field.Root>
                  <Field.Label>
                    {isEditMode
                      ? "Attachment (replace to reprocess)"
                      : "Attachments"}
                  </Field.Label>
                  <FileUpload.Root
                    accept={[".pdf", ".md"]}
                    maxFiles={isEditMode ? 1 : 20}
                    acceptedFiles={files}
                    onFileReject={() =>
                      setError(
                        "Choose PDF or Markdown files (up to 20; one attachment when editing). Remove the current attachment before replacing it.",
                      )
                    }
                    onFileChange={(details) => {
                      const selected = details.acceptedFiles[0] || null;
                      setFiles(details.acceptedFiles);
                      setError("");
                      if (selected && !fileName.trim())
                        setFileName(selected.name);
                    }}
                  >
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
                    <FileUpload.ItemGroup>
                      {files.map((file, index) => (
                        <FileUpload.Item
                          key={`${file.name}-${index}`}
                          file={file}
                        >
                          <FileUpload.ItemName />
                          <FileUpload.ItemSizeText />
                          <FileUpload.ItemDeleteTrigger />
                        </FileUpload.Item>
                      ))}
                    </FileUpload.ItemGroup>
                  </FileUpload.Root>
                </Field.Root>

                {/* 2. File Name Input */}
                {(isEditMode || files.length <= 1) && (
                  <Field.Root required>
                    <Field.Label>File Name</Field.Label>
                    <Input
                      placeholder="e.g. Mercedes Car Manual"
                      value={fileName}
                      onChange={(e) => setFileName(e.target.value)}
                    />
                  </Field.Root>
                )}
                {files.length > 1 && (
                  <Text fontSize="sm">
                    Each file keeps its filename. Tags and vehicle apply to all
                    selected files.
                  </Text>
                )}
                <Field.Root>
                  <Field.Label>Vehicle / document scope</Field.Label>
                  <select
                    aria-label="Document vehicle"
                    value={carModel}
                    onChange={(event) => setCarModel(event.target.value)}
                    style={{
                      padding: 8,
                      border: "1px solid #E2E8F0",
                      width: "100%",
                    }}
                  >
                    {chatScopes.map((scope) => (
                      <option key={scope.value} value={scope.value}>
                        {scope.value === "bezza"
                          ? "Perodua Bezza"
                          : scope.label}
                      </option>
                    ))}
                  </select>
                  <Text fontSize="xs" color="gray.600">
                    Local organization only; this does not change the backend’s
                    available manuals.
                  </Text>
                </Field.Root>

                {/* 3. Clickable Tag Selection Section */}
                <Field.Root>
                  <Field.Label>Select Tags</Field.Label>

                  {/* Clickable Tag Badges */}
                  <HStack gap={2} mb={2} wrap="wrap">
                    {availableTags.map((tag) => {
                      const isSelected = selectedTags.includes(tag);
                      return (
                        <Button
                          type="button"
                          aria-pressed={isSelected}
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
                {isEditMode ? "Save Changes" : "Add Documents"}
              </Button>
            </Dialog.Footer>
          </form>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
}
