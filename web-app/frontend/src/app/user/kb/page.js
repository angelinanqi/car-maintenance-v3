'use client';

import { useState } from 'react';
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

    // Sample Dataset
    const [items, setItems] = useState([
        { id: 1, name: 'Myvi Car Manual', category: 'Manuals', status: 'Active', date: '2026-08-15' },
        { id: 2, name: 'Perodua Bezza Warranty Booklet', category: 'Manuals', status: 'Pending', date: '2026-08-20' },
        { id: 3, name: 'Emergency SOPs Proton Saga', category: 'Other', status: 'Active', date: '2026-08-28' },
    ]);

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
            // BACKEND DELETE CALL HERE
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
                        Upload File
                    </Button>
                </Flex>

                {/* TABLE VIEW */}
                <Table.ScrollArea border="1px solid" borderColor="gray.200" borderRadius="md">
                    <Table.Root size="sm" variant="outline">
                        <Table.Header>
                            <Table.Row bg="gray.50">
                                <Table.ColumnHeader>Name</Table.ColumnHeader>
                                <Table.ColumnHeader>Category</Table.ColumnHeader>
                                <Table.ColumnHeader>Status</Table.ColumnHeader>
                                <Table.ColumnHeader>Date Added</Table.ColumnHeader>
                                <Table.ColumnHeader textAlign="right">Actions</Table.ColumnHeader>
                            </Table.Row>
                        </Table.Header>
                        <Table.Body>
                            {items.map((item) => (
                                <Table.Row key={item.id}>
                                    <Table.Cell fontWeight="medium">{item.name}</Table.Cell>
                                    <Table.Cell>{item.category}</Table.Cell>
                                    <Table.Cell>
                                        <Badge colorPalette={item.status === 'Active' ? 'green' : 'orange'}>
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

                {/* MODALS */}
                
                {/* 1. Upload Modal */}
                <FileModal 
                    isOpen={isUploadOpen} 
                    onClose={() => setIsUploadOpen(false)} 
                />

                {/* 2. Edit Modal (Reuses FileModal in edit mode) */}
                <FileModal 
                    isOpen={Boolean(editItem)} 
                    editData={editItem} 
                    onClose={() => setEditItem(null)} 
                />

                {/* 3. Delete Confirmation Modal */}
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