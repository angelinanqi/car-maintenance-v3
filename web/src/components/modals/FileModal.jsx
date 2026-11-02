"use client";

import { AdminSelect } from "@/components/admin/NativeControls";

import {
  DOCUMENT_EXTENSIONS,
  DOCUMENT_MAX_FILES,
  DOCUMENT_MAX_BYTES,
} from "@/lib/config.mjs";
import { useState } from "react";
import { validateDocumentFile } from "@/lib/documentFiles.mjs";
import useUnsavedChanges from "@/components/admin/useUnsavedChanges";
import {
  Dialog,
  Button,
  Stack,
  Input,
  Field,
  HStack,
  FileUpload,
  Text,
  Box,
  Fieldset,
} from "@chakra-ui/react";

export default function FileModal({
  isOpen,
  onClose,
  onSave,
  editData = null,
  tags = [],
  replacementFor = null,
}) {
  const [fileName, setFileName] = useState(editData?.name || "");
  const [tagInput, setTagInput] = useState("");
  const [files, setFiles] = useState(editData?.file ? [editData.file] : []);
  const [documentType, setDocumentType] = useState(
    editData?.document_type || "other_reference",
  );
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  // Preset tags available to click and choose from
  const [availableTags, setAvailableTags] = useState([
    ...new Set(["Manuals", "Other", ...tags, ...(editData?.tags || [])]),
  ]);
  const [selectedTags, setSelectedTags] = useState(editData?.tags || []);
  const isEditMode = Boolean(editData);
  const maxFiles = isEditMode || replacementFor ? 1 : DOCUMENT_MAX_FILES;
  const uploadLimits = `Accepted: ${DOCUMENT_EXTENSIONS.join(", ")}. Maximum ${DOCUMENT_MAX_BYTES / 1024 / 1024} MB per file; ${maxFiles} file(s) per upload.`;
  const dirty =
    files.length > 0 ||
    fileName !== (editData?.name || "") ||
    documentType !== (editData?.document_type || "other_reference") ||
    JSON.stringify(selectedTags) !== JSON.stringify(editData?.tags || []);
  useUnsavedChanges(dirty);
  function close() {
    if (
      !saving &&
      (!dirty ||
        window.confirm("Close and discard these unsaved document details?"))
    )
      onClose();
  }

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
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (saving) return;
    if (files.length > maxFiles) {
      setError(`Too many files. ${uploadLimits}`);
      return;
    }

    if (
      ((isEditMode || files.length === 1) && !fileName.trim()) ||
      ((!isEditMode || replacementFor) && files.length === 0)
    ) {
      setError("Enter a name and choose a file before adding the document.");
      return;
    }
    const fileError = files.map(validateDocumentFile).find(Boolean);
    if (fileError) {
      setError(fileError);
      return;
    }
    setSaving(true);
    try {
      await onSave({
        name: fileName.trim(),
        tags: selectedTags,
        documentType,
        files,
      });
      onClose();
    } catch (error) {
      if (error.uploadedFiles?.length)
        setFiles((previous) =>
          previous.filter((file) => !error.uploadedFiles.includes(file)),
        );
      setError(
        error.uploadedFiles?.length
          ? `${error.uploadedFiles.length} file(s) uploaded. Remaining files: ${error.message}`
          : error.message,
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog.Root
      open={isOpen}
      closeOnInteractOutside={false}
      closeOnEscape={!saving}
      onOpenChange={(e) => !e.open && close()}
    >
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
                {replacementFor
                  ? "Replace Document"
                  : isEditMode
                    ? "Edit Document Details"
                    : "Add a Reference Document"}
              </Dialog.Title>
              <Button
                type="button"
                variant="outline"
                size="xs"
                onClick={close}
                disabled={saving}
                aria-label="Close"
              >
                Close
              </Button>
            </Dialog.Header>

            {/* BODY */}
            <Dialog.Body>
              <Fieldset.Root disabled={saving}>
                <Stack gap={4}>
                  <Text fontSize="sm" color="gray.600">
                    {replacementFor
                      ? "Choose the updated manual. The current version stays available until you check and approve its replacement. You will confirm the vehicles and topics it covers next."
                      : isEditMode
                        ? "Change how this document is identified. To provide a newer file, use Replace document in the document workspace."
                        : "Start with the file and a recognisable title. Next, you’ll choose the vehicles or topics it covers and prepare it for checking."}
                  </Text>
                  <Text fontSize="sm" color="muted">
                    {uploadLimits}
                  </Text>
                  {error && (
                    <Text role="alert" color="red.600">
                      {error}
                    </Text>
                  )}
                  {/* Local attachments; edit supports replacement. */}
                  {(!isEditMode || replacementFor) && (
                    <Field.Root>
                      <Field.Label>
                        {isEditMode ? "Updated document" : "Document file"}
                      </Field.Label>
                      <FileUpload.Root
                        disabled={Boolean(
                          editData?.published && !replacementFor,
                        )}
                        accept={DOCUMENT_EXTENSIONS}
                        minFileSize={1}
                        maxFileSize={DOCUMENT_MAX_BYTES}
                        maxFiles={maxFiles}
                        acceptedFiles={files}
                        onFileReject={() => setError(`File selection rejected. ${uploadLimits} Empty files are not allowed. Remove an existing attachment before replacing it.`)}
                        onFileChange={(details) => {
                          const selected = details.acceptedFiles[0] || null;
                          setFiles(details.acceptedFiles);
                          if (!details.rejectedFiles.length) setError("");
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
                  )}

                  {/* 2. File Name Input */}
                  {!replacementFor && (isEditMode || files.length <= 1) && (
                    <Field.Root required>
                      <Field.Label>Document title</Field.Label>
                      <Input
                        placeholder="e.g. Myvi 2022 owner’s manual"
                        value={fileName}
                        onChange={(e) => setFileName(e.target.value)}
                      />
                    </Field.Root>
                  )}
                  {files.length > 1 && (
                    <Text fontSize="sm">
                      Each file keeps its filename. Tags and document type apply
                      to all selected files.
                    </Text>
                  )}

                  {!replacementFor && (
                    <Field.Root>
                      <Field.Label>Document type</Field.Label>
                      <AdminSelect
                        aria-label="Document type"
                        value={documentType}
                        onChange={(event) =>
                          setDocumentType(event.target.value)
                        }
                      >
                        <option value="owners_manual">
                          Owner&apos;s manual
                        </option>
                        <option value="maintenance_booklet">
                          Maintenance booklet
                        </option>
                        <option value="service_manual">Service manual</option>
                        <option value="other_reference">Other reference</option>
                      </AdminSelect>
                    </Field.Root>
                  )}

                  {/* 3. Clickable Tag Selection Section */}
                  {!replacementFor && (
                    <Box as="details">
                      <Box as="summary">Search Labels (Optional)</Box>
                      <Field.Root mt={3}>
                        <Field.Label>
                          Labels to help find this document
                        </Field.Label>

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
                                colorPalette={isSelected ? "brand" : "gray"}
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
                        <Text fontSize="sm" color="muted" mt={1}>
                          Selected:{" "}
                          {selectedTags.length > 0
                            ? selectedTags.join(", ")
                            : "None"}
                        </Text>
                      </Field.Root>
                    </Box>
                  )}
                </Stack>
              </Fieldset.Root>
            </Dialog.Body>

            {/* FOOTER */}
            <Dialog.Footer>
              <Button
                type="button"
                variant="outline"
                onClick={close}
                disabled={saving}
              >
                Cancel
              </Button>
              <Button type="submit" colorPalette="brand" loading={saving}>
                {replacementFor
                  ? "Upload updated document"
                  : isEditMode
                    ? "Save details"
                    : "Upload and continue"}
              </Button>
            </Dialog.Footer>
          </form>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
}
