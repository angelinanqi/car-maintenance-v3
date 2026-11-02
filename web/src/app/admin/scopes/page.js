"use client";

import AdminLayout from "@/components/layouts/AdminLayout";
import KnowledgeScopes from "@/components/KnowledgeScopes";
import YouTubeChannels from "@/components/admin/YouTubeChannels";
import { Stack } from "@chakra-ui/react";

export default function ScopesPage() {
  return (
    <AdminLayout
      title="Topics and Related Videos"
      description="Manage learning topics and sync YouTube channels for chatbot recommendations."
    >
      <Stack gap={6}>
        <YouTubeChannels />
        <KnowledgeScopes />
      </Stack>
    </AdminLayout>
  );
}
