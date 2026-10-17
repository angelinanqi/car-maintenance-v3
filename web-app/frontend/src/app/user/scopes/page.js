"use client";

import AdminLayout from "@/components/layouts/AdminLayout";
import KnowledgeScopes from "@/components/KnowledgeScopes";
import { useContent } from "@/components/ContentProvider";

export default function ScopesPage() {
  const { documents, refresh } = useContent();
  return <AdminLayout title="Knowledge scopes" description="Choose which vehicles and topics can use each source. Publish a scope separately to make it available in Roadie chat.">
    <KnowledgeScopes documents={documents} onChanged={refresh} />
  </AdminLayout>;
}
