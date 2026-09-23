"use client";

import { useState } from "react";
import { usePrototype } from "@/components/PrototypeProvider";
import { toaster } from "@/components/ui/toaster";
import { createLocalDocuments } from "@/lib/prototypeDocuments.mjs";
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

  const {
    documents: items,
    setDocuments: setItems,
    processDocuments,
  } = usePrototype();
  const [selectedIds, setSelectedIds] = useState([]);
  const selectable = items.filter((item) => item.status !== "Processing");
  const selected = selectable.filter((item) => selectedIds.includes(item.id));

  async function handleProcess(ids) {
    const result = await processDocuments(ids);
    toaster.create({
      title: `${result.succeeded} processed in demo; ${result.failed} failed`,
      type: result.failed ? "error" : "success",
    });
  }

  function downloadFile(item) {
    const url = URL.createObjectURL(item.file);
    const link = document.createElement("a");
    link.href = url;
    link.download = item.file.name;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const handleSave = (data) => {
    const { files, ...metadata } = data;
    if (editItem) {
      const file = files[0] || null;
      const changed =
        file !== editItem.file ||
        metadata.carModel !== (editItem.carModel || "general");
      setItems((previous) =>
        previous.map((item) =>
          item.id === editItem.id
            ? {
                ...item,
                ...metadata,
                file,
                ...(changed
                  ? { status: file ? "Ready" : "Needs file", error: "" }
                  : {}),
              }
            : item,
        ),
      );
    } else {
      setItems((previous) => [
        ...previous,
        ...createLocalDocuments(files, metadata),
      ]);
    }
    toaster.create({
      title: editItem ? "Document updated locally" : "Document added locally",
      type: "success",
    });
  };

  // Open Edit Modal with selected row data
  const handleOpenEdit = (item) => {
    setEditItem(item);
  };

  // Open Delete Confirmation Modal
  const handleOpenDelete = (item) => {
    setDeleteItem(item);
  };

  // Execute Delete
  const handleConfirmDelete = () => {
    if (deleteItem) {
      toaster.create({ title: "Document removed locally", type: "success" });
      setItems((prev) => prev.filter((i) => i.id !== deleteItem.id));
      setSelectedIds((previous) =>
        previous.filter((id) => id !== deleteItem.id),
      );
      setDeleteItem(null);
    }
  };

  return (
    <AdminLayout
      title="Knowledge Base"
      description="Manage your project documents and records."
    >
      <Stack gap={6}>
        {/* HEADER ROW */}
        <Flex justify="space-between" align="center" wrap="wrap" gap={4}>
          <Box>
            <Heading size="md">All Documents</Heading>
            <Text fontSize="sm" color="gray.500">
              Showing {items.length} records
            </Text>
          </Box>

          {/* Upload Trigger */}
          <Button colorPalette="blue" onClick={() => setIsUploadOpen(true)}>
            Add Documents
          </Button>
        </Flex>

        <Text fontSize="sm" color="gray.600">
          Processing is simulated. “Processed (demo)” means available to AI in
          this prototype only; Chat Preview continues to use the backend’s
          existing index.
        </Text>
        <Flex gap={3} align="center" wrap="wrap">
          <Text fontSize="sm">
            {selected.length} selected ·{" "}
            {items.filter((item) => item.status === "Processed (demo)").length}{" "}
            processed in demo
          </Text>
          <Button
            disabled={!selected.length}
            onClick={() => handleProcess(selected.map((item) => item.id))}
          >
            Process selected (demo)
          </Button>
          <Button
            variant="ghost"
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
                    <Checkbox.Control />
                  </Checkbox.Root>
                </Table.ColumnHeader>
                <Table.ColumnHeader>Name</Table.ColumnHeader>
                <Table.ColumnHeader>Tags</Table.ColumnHeader>
                <Table.ColumnHeader>Status</Table.ColumnHeader>
                <Table.ColumnHeader>Date Added</Table.ColumnHeader>
                <Table.ColumnHeader textAlign="right">
                  Actions
                </Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {items.map((item) => (
                <Table.Row key={item.id}>
                  <Table.Cell>
                    <Checkbox.Root
                      disabled={item.status === "Processing"}
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
                      <Checkbox.Control />
                    </Checkbox.Root>
                  </Table.Cell>
                  <Table.Cell fontWeight="medium">
                    {item.name}
                    <Text fontSize="xs" color="gray.600">
                      Scope: {item.carModel || "general"}
                    </Text>
                    {!item.file && (
                      <Text fontSize="xs">Edit to attach a file.</Text>
                    )}
                  </Table.Cell>
                  <Table.Cell>
                    {item.tags.length ? item.tags.join(", ") : "No tags"}
                  </Table.Cell>
                  <Table.Cell>
                    <Badge
                      colorPalette={
                        item.status === "Failed"
                          ? "red"
                          : item.status === "Processed (demo)"
                            ? "green"
                            : item.status === "Processing"
                              ? "blue"
                              : "gray"
                      }
                    >
                      {item.status}
                    </Badge>
                    {item.error && (
                      <Text role="alert" fontSize="xs" color="red.600">
                        {item.error}
                      </Text>
                    )}
                  </Table.Cell>
                  <Table.Cell>{item.date}</Table.Cell>

                  {/* Action Buttons */}
                  <Table.Cell textAlign="right">
                    <Group attached={false} gap={2} justify="flex-end">
                      <Button
                        size="xs"
                        loading={item.status === "Processing"}
                        disabled={item.status === "Processing"}
                        onClick={() => handleProcess([item.id])}
                      >
                        {item.status === "Failed"
                          ? "Retry (demo)"
                          : "Process (demo)"}
                      </Button>
                      <Button
                        size="xs"
                        variant="outline"
                        disabled={!item.file}
                        onClick={() => downloadFile(item)}
                      >
                        Download
                      </Button>
                      <Button
                        variant="outline"
                        size="xs"
                        onClick={() => handleOpenEdit(item)}
                        disabled={item.status === "Processing"}
                      >
                        Edit
                      </Button>
                      <Button
                        variant="outline"
                        colorPalette="red"
                        size="xs"
                        onClick={() => handleOpenDelete(item)}
                        disabled={item.status === "Processing"}
                      >
                        Remove
                      </Button>
                    </Group>
                  </Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>
        </Table.ScrollArea>

        {items.length === 0 && (
          <Text color="gray.600">
            No documents yet. Add a document to try the local library.
          </Text>
        )}
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
