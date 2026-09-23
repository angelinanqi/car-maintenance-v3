'use client';

import { useState } from 'react';
import { usePrototype } from '@/components/PrototypeProvider';
import { toaster } from '@/components/ui/toaster';
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
} from '@chakra-ui/react';

// Relative Imports
import AdminLayout from '../../../components/layouts/AdminLayout';
import FileModal from '../../../components/modals/FileModal';
import DeleteConfirmModal from '../../../components/modals/DeleteConfirmModal';

export default function ProjectsPage() {
    // Modal States
    const [isUploadOpen, setIsUploadOpen] = useState(false);
    const [editItem, setEditItem] = useState(null);       // Controls Edit Modal
    const [deleteItem, setDeleteItem] = useState(null);   // Controls Delete Modal

    const { documents: items, setDocuments: setItems } = usePrototype();

    const handleSave = (data) => {
        if (editItem) {
            setItems((previous) => previous.map((item) => item.id === editItem.id ? { ...item, ...data } : item));
        } else {
            setItems((previous) => [...previous, { ...data, id: crypto.randomUUID(), status: "Local only", date: new Date().toLocaleDateString("en-CA") }]);
        }
        toaster.create({ title: editItem ? "Document updated locally" : "Document added locally", type: "success" });
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
            setDeleteItem(null);
        }
    };

    return (
        <AdminLayout title="Knowledge Base" description="Manage your project documents and records.">
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
                        Add Document
                    </Button>
                </Flex>

                {/* TABLE VIEW */}
                <Table.ScrollArea border="1px solid" borderColor="gray.200" borderRadius="md">
                    <Table.Root size="sm" variant="outline" minW="650px">
                        <Table.Header>
                            <Table.Row bg="gray.50">
                                <Table.ColumnHeader>Name</Table.ColumnHeader>
                                <Table.ColumnHeader>Tags</Table.ColumnHeader>
                                <Table.ColumnHeader>Status</Table.ColumnHeader>
                                <Table.ColumnHeader>Date Added</Table.ColumnHeader>
                                <Table.ColumnHeader textAlign="right">Actions</Table.ColumnHeader>
                            </Table.Row>
                        </Table.Header>
                        <Table.Body>
                            {items.map((item) => (
                                <Table.Row key={item.id}>
                                    <Table.Cell fontWeight="medium">{item.name}</Table.Cell>
                                    <Table.Cell>{item.tags.length ? item.tags.join(", ") : "No tags"}</Table.Cell>
                                    <Table.Cell>
                                        <Badge colorPalette="gray">
                                            {item.status}
                                        </Badge>
                                    </Table.Cell>
                                    <Table.Cell>{item.date}</Table.Cell>
                                    
                                    {/* Action Buttons */}
                                    <Table.Cell textAlign="right">
                                        <Group attached={false} gap={2} justify="flex-end">
                                            <Button
                                                variant="outline"
                                                size="xs"
                                                onClick={() => handleOpenEdit(item)}
                                            >
                                                Edit
                                            </Button>
                                            <Button
                                                variant="outline"
                                                colorPalette="red"
                                                size="xs"
                                                onClick={() => handleOpenDelete(item)}
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

                {items.length === 0 && <Text color="gray.600">No documents yet. Add a document to try the local library.</Text>}
                {/* MODALS */}
                
                {(isUploadOpen || editItem) && (
                    <FileModal
                        key={editItem?.id || "new"}
                        isOpen
                        editData={editItem}
                        onSave={handleSave}
                        onClose={() => { setIsUploadOpen(false); setEditItem(null); }}
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