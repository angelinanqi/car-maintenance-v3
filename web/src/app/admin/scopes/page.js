"use client";

import AdminLayout from "@/components/layouts/AdminLayout";
import KnowledgeScopes from "@/components/KnowledgeScopes";
import YouTubeChannels from "@/components/admin/YouTubeChannels";
import { Stack } from "@chakra-ui/react";

export default function ScopesPage() {
  return (
    <AdminLayout
      title="Topics and related videos"
      description="Choose the learning topics drivers can ask about and the videos that support them."
    >
      <Stack gap={6}>
        <YouTubeChannels />
        <KnowledgeScopes />
      </Stack>
    </AdminLayout>
  );
}
