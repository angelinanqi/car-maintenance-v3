-- Support the per-question latest-run lookup used by admin follow-up summaries.
create index if not exists document_test_runs_question_recent
    on public.document_test_runs(question_id, started_at desc, id desc);
