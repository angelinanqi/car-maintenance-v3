"use client";

import { AdminSelect } from "@/components/admin/NativeControls";
import NextLink from "next/link";

import { useState } from "react";
import { useContent } from "@/components/ContentProvider";
import { toaster } from "@/components/ui/toaster";
import { downloadDocumentUrl, downloadExtractionUrl, originalDocumentUrl, publishDocument, unpublishDocument, stageReplacement } from "@/api/documents.mjs";
import {
  Flex,
  Heading,
  Text,
  Button,
  Table,
  Badge,
  Group,
  Stack,
  Box,
  Checkbox,
  Input,
  Menu,
  Portal,
} from "@chakra-ui/react";

// Relative Imports
import AdminLayout from "../../../components/layouts/AdminLayout";
import FileModal from "../../../components/modals/FileModal";
import DeleteConfirmModal from "../../../components/modals/DeleteConfirmModal";

export default function ProjectsPage() {
  // Modal States
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [editItem, setEditItem] = useState(null); // Controls Edit Modal
  const [deleteItem, setDeleteItem] = useState(null); // Controls Delete Modal
  const [replacementItem, setReplacementItem] = useState(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [publishingId, setPublishingId] = useState(null);

  const {
    documents: items,
    saveDocument, deleteDocument, refresh,
    processDocuments,
  } = useContent();
  const [selectedIds, setSelectedIds] = useState([]);
  const [processingRequest, setProcessingRequest] = useState(false);
  const visible = items.filter((item) => `${item.name} ${item.tags.join(" ")}`.toLowerCase().includes(query.toLowerCase()) && (!statusFilter || item.status === statusFilter));
  const selectable = visible.filter((item) => item.status !== "processing" && !item.published);
  const selected = selectable.filter((item) => selectedIds.includes(item.id));

  async function handleProcess(ids, force = false) {
    if (processingRequest) return;
    setProcessingRequest(true);
    try {
      const results = await processDocuments(ids, force);
      const failed = results.filter((item) => item.error);
      toaster.create({ title: failed.length ? failed.map((item) => item.error).join("; ") : "Processing requested. Status updates automatically.", type: failed.length ? "error" : "success" });
    } catch (error) { toaster.create({ title: error.message, type: "error" }); }
    finally { setProcessingRequest(false); }
  }

  function downloadFile(item) {
    window.open(downloadDocumentUrl(item.id), "_blank", "noopener,noreferrer");
  }

  async function handleSave(data) {
    await saveDocument(editItem, data);
    toaster.create({ title: editItem ? "Document updated" : "Documents uploaded", type: "success" });
  }
  async function changePublication(item) {
    if (publishingId) return;
    if (!window.confirm(item.published ? "Unpublish this document? It will no longer be retrieved or publicly downloadable." : "Confirm that the original and processed document have been reviewed and are ready to publish? Publishing a replacement retires the previous document.")) return;
    setPublishingId(item.id);
    try {
      await (item.published ? unpublishDocument(item.id) : publishDocument(item.id));
      await refresh();
      toaster.create({ title: item.published ? "Document unpublished" : "Document published", type: "success" });
    } catch (error) { toaster.create({ title: error.message, type: "error" }); }
    finally { setPublishingId(null); }
  }

  // Open Edit Modal with selected row data
  const handleOpenEdit = (item) => {
    setEditItem(item);
  };

  // Open Delete Confirmation Modal
  const handleOpenDelete = (item) => {
    setDeleteItem(item);
  };

  // Execute Delete
  const handleConfirmDelete = async () => {
    if (!deleteItem) return;
    try {
      await deleteDocument(deleteItem.id);
      setSelectedIds((previous) => previous.filter((id) => id !== deleteItem.id));
      setDeleteItem(null);
      toaster.create({ title: "Document and stored files removed; excluded from chat", type: "success" });
    } catch (error) { toaster.create({ title: error.message, type: "error" }); }
  };

  return (
    <AdminLayout
      title="Document library"
      description="Upload, associate, process, review and publish reference documents."
    >
      <Stack gap={6}>
        <Flex bg="brand.100" p={5} borderRadius="12px" gap={4} align="center" justify="space-between" wrap="wrap">
          <Box><Heading as="h2" size="md">Make a source available to chat</Heading><Text fontSize="sm" mt={1}>Upload → assign a scope → process → review → publish.</Text></Box>
          <Button asChild variant="outline"><NextLink href="/user/scopes">Manage scopes & applicability</NextLink></Button>
        </Flex>
        {/* HEADER ROW */}
        <Flex justify="space-between" align="center" wrap="wrap" gap={4}>
          <Box>
            <Heading size="md">All Documents</Heading>
            <Text fontSize="sm" color="muted">
              Showing {items.length} records
            </Text>
          </Box>

          {/* Upload Trigger */}
          <Button variant="outline" onClick={refresh}>Refresh</Button>
          <Button colorPalette="brand" onClick={() => setIsUploadOpen(true)}>
            Add Documents
          </Button>
        </Flex>

        <Text fontSize="sm" color="gray.600">
          Upload and associate sources, then process them. Review extraction and wait for confirmed indexing before publishing. Only indexed, published documents in published scopes are searchable.
        </Text>
        <Flex gap={4} wrap="wrap" align="end"><Box as="label" flex="1" minW="180px">Search documents<Input mt={2} value={query} placeholder="Search title or tags" onChange={(e) => setQuery(e.target.value)} /></Box><Box as="label" minW="180px">Processing status <AdminSelect value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}><option value="">All statuses</option>{["uploaded", "processing", "awaiting_index", "processed", "failed"].map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</AdminSelect></Box></Flex>
        <Flex gap={3} align="center" wrap="wrap">
          <Text fontSize="sm">
            {selected.length} selected ·{" "}
            {items.filter((item) => item.status === "processed").length}{" "}
            indexed · {items.filter((item) => item.status === "awaiting_index").length} awaiting indexing
          </Text>
          <Button
            disabled={!selected.length || processingRequest}
            onClick={() => handleProcess(selected.map((item) => item.id))}
          >
            Process selected
          </Button>
          <Button
            variant="outline"
            disabled={!selectedIds.length}
            onClick={() => setSelectedIds([])}
          >
            Clear selection
          </Button>
        </Flex>
        {/* TABLE VIEW */}
        <Table.ScrollArea
          border="1px solid"
          borderColor="gray.200"
          borderRadius="md"
        >
          <Table.Root size="sm" variant="outline" minW="650px">
            <Table.Header>
              <Table.Row bg="gray.50">
                <Table.ColumnHeader>
                  <Checkbox.Root
                    disabled={!selectable.length}
                    checked={
                      selected.length === selectable.length &&
                      selectable.length > 0
                        ? true
                        : selected.length
                          ? "indeterminate"
                          : false
                    }
                    onCheckedChange={({ checked }) =>
                      setSelectedIds(
                        checked ? selectable.map((item) => item.id) : [],
                      )
                    }
                  >
                    <Checkbox.HiddenInput aria-label="Select all documents" />
                    <Checkbox.Control><Checkbox.Indicator /></Checkbox.Control>
                  </Checkbox.Root>
                </Table.ColumnHeader>
                <Table.ColumnHeader>Name</Table.ColumnHeader>
                <Table.ColumnHeader>Tags</Table.ColumnHeader>
                <Table.ColumnHeader>Status</Table.ColumnHeader>
                <Table.ColumnHeader>Publication</Table.ColumnHeader>
                <Table.ColumnHeader>Date Added</Table.ColumnHeader>
                <Table.ColumnHeader textAlign="right">
                  Actions
                </Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {visible.map((item) => (
                <Table.Row key={item.id}>
                  <Table.Cell>
                    <Checkbox.Root
                      disabled={item.status === "processing" || item.published}
                      checked={selectedIds.includes(item.id)}
                      onCheckedChange={({ checked }) =>
                        setSelectedIds((previous) =>
                          checked
                            ? [...previous, item.id]
                            : previous.filter((id) => id !== item.id),
                        )
                      }
                    >
                      <Checkbox.HiddenInput
                        aria-label={`Select ${item.name}`}
                      />
                      <Checkbox.Control><Checkbox.Indicator /></Checkbox.Control>
                    </Checkbox.Root>
                  </Table.Cell>
                  <Table.Cell fontWeight="medium">
                    {item.name}
                    <Text fontSize="sm" color="gray.600">
                      {item.vehicle_independent ? "Vehicle-independent reference" : "Vehicle applicability managed in Knowledge scopes"}
                    </Text>
                    <Text fontSize="sm">{item.document_type?.replaceAll("_", " ") || "Other reference"}</Text>
                    {item.replacement_for_id && <Text fontSize="sm">Replacement for {item.replacement_for_id}</Text>}
                  </Table.Cell>
                  <Table.Cell>
                    {item.tags.length ? item.tags.join(", ") : "No tags"}
                  </Table.Cell>
                  <Table.Cell>
                    <Badge
                      colorPalette={
                        item.status === "failed"
                          ? "red"
                          : item.status === "processed"
                            ? "green"
                            : item.status === "processing"
                              ? "blue"
                              : "gray"
                      }
                    >
                      {item.status === "awaiting_index" ? "Awaiting indexing" : item.status === "processed" ? (item.indexed_revision ? "Indexed" : "Reprocessing required") : item.status}
                    </Badge>
                    {item.error && (
                      <Text role="alert" fontSize="sm" color="red.600">
                        {item.error}
                      </Text>
                    )}
                  </Table.Cell>
                  <Table.Cell><Badge colorPalette={item.published ? "green" : "gray"}>{item.superseded_by_id ? "Superseded" : item.published ? "Published" : "Draft"}</Badge></Table.Cell>
                  <Table.Cell>{item.date}</Table.Cell>

                  {/* Action Buttons */}
                  <Table.Cell textAlign="right">
                    <Group attached={false} gap={2} justify="flex-end" flexWrap="wrap" maxW="360px" minW="230px" ml="auto">
                      <Button
                        size="xs"
                        loading={item.status === "processing"}
                        disabled={item.status === "processing" || processingRequest || item.published}
                        onClick={() => handleProcess([item.id], ["processed", "awaiting_index"].includes(item.status))}
                      >
                        {item.status === "failed"
                          ? "Retry"
                          : ["processed", "awaiting_index"].includes(item.status) ? "Reprocess" : "Process"}
                      </Button>
                      <Button size="xs" variant="outline" disabled={Boolean(publishingId) || Boolean(item.superseded_by_id) || (!item.published && (item.status !== "processed" || !item.indexed_revision || item.indexed_revision !== item.source_revision))} onClick={() => changePublication(item)}>{item.published ? "Unpublish" : "Publish"}</Button>
                      <Menu.Root positioning={{ strategy: "fixed", hideWhenDetached: true }}>
                        <Menu.Trigger asChild><Button size="xs" variant="outline" aria-label={`More actions for ${item.name}`}>More actions</Button></Menu.Trigger>
                        <Portal><Menu.Positioner><Menu.Content>
                          <Menu.Item value="replace" disabled={item.status === "processing" || Boolean(item.superseded_by_id)} onSelect={() => setReplacementItem(item)}>Stage replacement</Menu.Item>
                          {item.source_type === "pdf" && <Menu.Item value="original" onSelect={() => window.open(originalDocumentUrl(item.id), "_blank", "noopener,noreferrer")}>Open original PDF</Menu.Item>}
                          {item.extraction_storage_path && ["awaiting_index", "processed"].includes(item.status) && <Menu.Item value="extraction" onSelect={() => window.open(downloadExtractionUrl(item.id), "_blank", "noopener,noreferrer")}>Review extraction</Menu.Item>}
                          <Menu.Item value="download" disabled={item.status === "processing"} onSelect={() => downloadFile(item)}>Download</Menu.Item>
                          <Menu.Item value="edit" disabled={item.status === "processing"} onSelect={() => handleOpenEdit(item)}>Edit</Menu.Item>
                          <Menu.Item value="remove" color="red.600" disabled={item.status === "processing"} onSelect={() => handleOpenDelete(item)}>Remove</Menu.Item>
                        </Menu.Content></Menu.Positioner></Portal>
                      </Menu.Root>
                    </Group>
                  </Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>
        </Table.ScrollArea>

        {items.length === 0 && (
          <Text color="gray.600">
            No documents yet. Upload a PDF or Markdown document to get started.
          </Text>
        )}
        {items.length > 0 && visible.length === 0 && <Box bg="white" p={6} borderRadius="12px"><Text>No documents match these filters.</Text><Button mt={3} variant="outline" onClick={() => { setQuery(""); setStatusFilter(""); }}>Clear filters</Button></Box>}
        {/* MODALS */}

        {(isUploadOpen || editItem) && (
          <FileModal
            key={editItem?.id || "new"}
            isOpen
            editData={editItem}
            tags={items.flatMap((item) => item.tags)}
            onSave={handleSave}
            onClose={() => {
              setIsUploadOpen(false);
              setEditItem(null);
            }}
          />
        )}
        {replacementItem && <FileModal key={`replacement-${replacementItem.id}`} isOpen editData={replacementItem} replacementFor={replacementItem.id} onClose={() => setReplacementItem(null)} onSave={async ({ files }) => {
          try { await stageReplacement(replacementItem.id, files[0]); }
          finally { await refresh(); }
          toaster.create({ title: "Replacement draft uploaded. Process and review it before publishing.", type: "success" });
        }} />}

        {/* Delete Confirmation Modal */}
        <DeleteConfirmModal
          isOpen={Boolean(deleteItem)}
          itemName={deleteItem?.name}
          onClose={() => setDeleteItem(null)}
          onConfirm={handleConfirmDelete}
        />
      </Stack>
    </AdminLayout>
  );
}
