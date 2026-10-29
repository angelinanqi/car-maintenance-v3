import { request } from './client.mjs';
import { API_URL } from '../lib/config.mjs';
import type { MaintenanceItem, ScheduleEntry } from './admin';

type Cell = { row: number; column: number; text: string; header?: boolean; rowspan?: number; colspan?: number };
export type DetectedTable = {
  table_id: string; title: string; pages: number[]; review_status: string;
  ranking: { score: number; classification: string; reasons: string[] };
  uncertainty: string[];
  source: { cells: Cell[]; section_path?: string[]; context?: string[]; notes?: string[]; original_html?: string; original_markdown?: string };
};
export type Selection = { table_id: string; confirmed: true; columns: number[]; excluded_rows: number[] };
export type DraftRule = Pick<ScheduleEntry['rule'], 'type' | 'distanceKm' | 'months' | 'distanceMilestones' | 'monthMilestones' | 'conditions' | 'notes'>;
export type AIDraft = {
  vehicle_id: string; generation_id: string; generated_at: string;
  provider: string | null; model: string | null; warnings: string[];
  action: MaintenanceItem['action'] | null; rule: DraftRule | null; source_page: number | null;
  manual_entry_required: boolean; reviewed_at: string | null; source_rows: number[];
  evidence: { cells: Cell[]; notes: string[]; context: string[] };
};
export type DraftRowEdit = {
  edited_name: string; mapped_item_id: string | null; status: 'suggested' | 'accepted' | 'rejected';
  action: MaintenanceItem['action'] | null; rule: DraftRule | null;
  source_page: number | null; confirm_review: boolean;
};
export type Suggestion = {
  suggestion_id: string; table_id: string; original_text: string | null; suggested_name: string;
  edited_name?: string; mapped_item_id: string | null; status: 'suggested' | 'accepted' | 'rejected';
  pages?: number[]; manual?: boolean; row?: number; uncertainty: string[]; potential_duplicate?: boolean;
  catalogue_matches: { item_id: string; title: string; action: string; method: string }[];
  ai_draft?: AIDraft;
};
export type Review = {
  document_id: string; source_revision: string; version: number; source_type: string; original_url: string;
  catalogue: { tables: DetectedTable[]; table_count: number; extraction_available: boolean };
  selections: Selection[]; suggestions: Suggestion[];
  bookmarks: { table_id: string; title: string; page: number | null; section: string; notes: string }[];
};
const base = (id: string) => `/admin/maintenance-assistance/documents/${encodeURIComponent(id)}`;
export const loadReview = (id: string, revision: string, signal?: AbortSignal): Promise<Review> =>
  request(`${base(id)}?source_revision=${encodeURIComponent(revision)}`, { signal });
export const sourceUrl = (id: string, revision: string) =>
  `${API_URL}${base(id)}/original?source_revision=${encodeURIComponent(revision)}`;
export const updateReview = (state: Review, path: string, method: string, body: object = {}): Promise<Review> =>
  request(`${base(state.document_id)}${path}`, { method, body: { ...body, source_revision: state.source_revision, version: state.version } });
