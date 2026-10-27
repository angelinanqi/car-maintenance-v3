import type { ReactNode } from "react";
import type { ReviewQuestion } from "@/api/reviewQuestions";

export type LearningGuideSummary = {
  id: string;
  title: string;
  status: "draft" | "published";
  maintenance_item_ids: string[];
};

export function ContentProvider(props: { children: ReactNode }): ReactNode;
export function useContent(): {
  cards: LearningGuideSummary[];
  reviewQuestions: ReviewQuestion[];
  error: string;
  loading: boolean;
  refresh: (options?: {
    documentsOnly?: boolean;
    resources?: string[];
  }) => Promise<string>;
  [key: string]: unknown;
};
