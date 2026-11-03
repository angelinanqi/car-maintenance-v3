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
import FileUploadField from "@/components/admin/FileUploadField";
import UploadCoverageStep from "@/components/admin/UploadCoverageStep";
import { cleanTag, tagKey, uniqueTags } from "@/lib/documentTags.mjs";
import {
  Dialog,
  Button,
  Stack,
  Input,
  Field,
  HStack,
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
  preferredVehicle = "",
  onUploadedDone,
}) {
  const [fileName, setFileName] = useState(editData?.name || "");
  const [tagInput, setTagInput] = useState("");
  const [files, setFiles] = useState(editData?.file ? [editData.file] : []);
  const [documentType, setDocumentType] = useState(
    editData?.document_type || "other_reference",
  );
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [uploadedDocuments, setUploadedDocuments] = useState([]);
  const [coverageStep, setCoverageStep] = useState(false);
  const [progress, setProgress] = useState(null);

  // Tags come from saved documents, so removed labels do not reappear as presets.
  const [availableTags, setAvailableTags] = useState([
    ...uniqueTags([...tags, ...(editData?.tags || [])]),
  ]);
  const originalSelectedTags = uniqueTags(editData?.tags || []).map((tag) =>
    availableTags.find((choice) => tagKey(choice) === tagKey(tag)) || tag);
  const [selectedTags, setSelectedTags] = useState(originalSelectedTags);
  const isEditMode = Boolean(editData);
  const maxFiles = isEditMode || replacementFor ? 1 : DOCUMENT_MAX_FILES;
  const uploadLimits = `Accepted: ${DOCUMENT_EXTENSIONS.join(", ")}. Maximum ${DOCUMENT_MAX_BYTES / 1024 / 1024} MB per file; ${maxFiles} file(s) per upload.`;
  const dirty =
    uploadedDocuments.length > 0 ||
    files.length > 0 ||
    fileName !== (editData?.name || "") ||
    documentType !== (editData?.document_type || "other_reference") ||
    JSON.stringify(selectedTags) !== JSON.stringify(originalSelectedTags);
  useUnsavedChanges(dirty);
  function close() {
    if (
      !saving &&
      (!dirty ||
        window.confirm(uploadedDocuments.length
          ? "Uploaded documents are saved. Close and finish any remaining coverage or uploads later?"
          : "Close and discard these unsaved document details?"))
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
        availableTags.find((tag) => tagKey(tag) === tagKey(tagInput)) || cleanTag(tagInput);

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
    if (saving || coverageStep) return;
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
      const uploaded = await onSave({
        name: fileName.trim(),
        tags: selectedTags,
        documentType,
        files,
      }, setProgress);
      if (!isEditMode && !replacementFor) {
        setUploadedDocuments((previous) => [...previous, ...uploaded]);
        setFiles([]);
        setCoverageStep(true);
      } else onClose();
    } catch (error) {
      if (error.uploadedDocuments?.length)
        setUploadedDocuments((previous) => [...previous, ...error.uploadedDocuments]);
      if (error.uploadedFiles?.length) {
        const remaining = files.filter((file) => !error.uploadedFiles.includes(file));
        setFiles(remaining);
        if (files.length > 1) setFileName(remaining[0]?.name || "");
      }
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
        <Dialog.Content maxW="720px" maxH="85vh" overflowY="auto">
          <form onSubmit={handleSubmit}>
            {/* HEADER */}
            <Dialog.Header
              display="flex"
              justifyContent="space-between"
              alignItems="center"
            >
              <Dialog.Title>
                {coverageStep ? "Set coverage for uploaded documents" : replacementFor
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
              {uploadedDocuments.length > 0 && <Box display={coverageStep ? "block" : "none"}>
                <UploadCoverageStep documents={uploadedDocuments} preferredVehicle={preferredVehicle}
                  remainingFileCount={files.length}
                  onBusy={setSaving} onBack={files.length ? () => setCoverageStep(false) : null}
                  onDone={(documents) => { onUploadedDone?.(documents); onClose(); }} />
              </Box>}
              {!coverageStep && (
              <Fieldset.Root disabled={saving}>
                <Stack gap={4}>
                  <Text fontSize="sm" color="gray.600">
                    {replacementFor
                      ? "Choose the updated manual. The current version stays available until you check and approve its replacement. You will confirm the vehicles and topics it covers next."
                      : isEditMode
                        ? "Change how this document is identified. To provide a newer file, use Replace document in the document workspace."
                        : "Choose your files and shared details. After upload, assign the same vehicles or learning topics to the whole bundle in this popup."}
                  </Text>
                  <Text fontSize="sm" color="muted">
                    {uploadLimits}
                  </Text>
                  {(!isEditMode || replacementFor) && (
                    <Text fontSize="sm" color="muted">
                      Identical files are blocked, even with a different filename.
                      Use the existing document to assign more vehicles or topics.
                    </Text>
                  )}
                  {error && (
                    <Text role="alert" color="red.600">
                      {error}
                    </Text>
                  )}
                  {uploadedDocuments.length > 0 && (
                    <Box bg="green.50" p={3} borderRadius="md">
                      <Text>{uploadedDocuments.length} document(s) already uploaded and saved.</Text>
                      <Button type="button" mt={2} size="sm" variant="outline" disabled={saving}
                        onClick={() => setCoverageStep(true)}>Set coverage for uploaded documents</Button>
                    </Box>
                  )}
                  {progress && (
                    <Box role="status" aria-live="polite">
                      <Text>{progress.results.length} of {progress.total} files checked{progress.currentFile ? ` · Uploading ${progress.currentFile}…` : ""}</Text>
                      <Box as="progress" w="100%" max={progress.total} value={progress.results.length}
                        aria-label="Document upload progress" />
                      {progress.results.map((result, index) => (
                        <Text key={index} fontSize="sm" color={result.error ? "red.600" : "muted"}>
                          {result.file.name}: {result.error || "Uploaded"}
                        </Text>
                      ))}
                    </Box>
                  )}
                  {/* Local attachments; edit supports replacement. */}
                  {(!isEditMode || replacementFor) && (
                    <Field.Root>
                      <Field.Label>
                        {isEditMode ? "Updated document" : "Document file"}
                      </Field.Label>
                      <FileUploadField
                        disabled={saving || Boolean(editData?.published && !replacementFor)}
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
                      />
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
                          maxLength={100}
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
              )}
            </Dialog.Body>

            {/* FOOTER */}
            {!coverageStep && <Dialog.Footer>
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
            </Dialog.Footer>}
          </form>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
}
