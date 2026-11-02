"use client";

import AdminLayout from "@/components/layouts/AdminLayout";
import ReviewQuestions from "@/components/admin/ReviewQuestions";

export default function QuestionsPage() {
  return (
    <AdminLayout
      title="Questions to Clarify"
      description="Return to uncertain instructions, check their references, and record what you confirmed."
    >
      <ReviewQuestions />
    </AdminLayout>
  );
}
