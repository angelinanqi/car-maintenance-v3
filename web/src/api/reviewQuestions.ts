import { request, listAll } from "./client.mjs";

export type ReviewQuestion = {
  id: string;
  document_id: string;
  source_revision: string;
  vehicle_id: string | null;
  schedule_id: string | null;
  item_id: string | null;
  source_page: number | null;
  title: string;
  question: string;
  excerpt: string;
  status: "open" | "resolved";
  resolution: string;
  version: number;
  created_at: string;
  updated_at: string;
  document_name?: string;
  vehicle_name?: string | null;
  source_changed?: boolean;
};
export type QuestionDraft = Omit<
  ReviewQuestion,
  | "id"
  | "status"
  | "resolution"
  | "version"
  | "created_at"
  | "updated_at"
  | "document_name"
  | "vehicle_name"
  | "source_changed"
>;
export const loadQuestions = (
  filters: Record<string, string> = {},
): Promise<ReviewQuestion[]> => listAll("/admin/review-questions", filters);
export const createQuestion = (body: QuestionDraft): Promise<ReviewQuestion> =>
  request("/admin/review-questions", { method: "POST", body });
export const decideQuestion = (
  question: ReviewQuestion,
  status: ReviewQuestion["status"],
  resolution: string,
): Promise<ReviewQuestion> =>
  request(`/admin/review-questions/${question.id}`, {
    method: "PATCH",
    body: { version: question.version, status, resolution },
  });
