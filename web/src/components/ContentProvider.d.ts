import type { ReactNode } from "react";
import type { ReviewQuestion } from "@/api/reviewQuestions";

export type LearningGuideSummary = {
  id: string;
  title: string;
  status: "draft" | "published";
  maintenance_item_ids: string[];
  beginner_friendly?: boolean;
  featured_in_companion?: boolean;
  learning_outcomes?: string[];
};

export function ContentProvider(props: { children: ReactNode; emergencyOnly?: boolean }): ReactNode;
export function useContent(): {
  cards: LearningGuideSummary[];
  reviewQuestions: ReviewQuestion[];
  error: string;
  documentTestError: string;
  loading: boolean;
  emergencyReady: boolean;
  refresh: (options?: {
    documentsOnly?: boolean;
    resources?: string[];
  }) => Promise<string>;
  [key: string]: unknown;
};
