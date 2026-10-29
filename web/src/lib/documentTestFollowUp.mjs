export const testFollowUpStates = ["needs_fixing", "outdated", "failed", "not_reviewed", "never_run"];

export function testNeedsAttention(summary) {
  return testFollowUpStates.some((state) => summary?.[state] > 0);
}

export function testSummaryText(summary) {
  if (!summary.total) return "No tests added.";
  const messages = [];
  const add = (state, singular, plural) => {
    const count = summary[state] || 0;
    if (count) messages.push(`${count} ${count === 1 ? singular : plural}`);
  };
  add("needs_fixing", "answer needs fixing", "answers need fixing");
  add("outdated", "test result out of date", "test results out of date");
  add("failed", "test run failed", "test runs failed");
  add("not_reviewed", "result needs review", "results need review");
  add("never_run", "question not run", "questions not run");
  add("running", "test running", "tests running");
  add("passed", "current result passed review", "current results passed review");
  return messages.join("; ") + ".";
}

export function documentTestHref(documentId, summary, state = null) {
  const target = state ? summary?.targets?.[state]
    : testFollowUpStates.map((key) => summary?.targets?.[key]).find(Boolean);
  const query = new URLSearchParams();
  if (target?.question_id) query.set("testQuestion", target.question_id);
  if (target?.run_id) query.set("testRun", target.run_id);
  return `/admin/kb/${documentId}${query.size ? `?${query}` : ""}#document-tests`;
}

export function matchesTestFilter(summary, filter) {
  if (!summary) return false;
  return filter === "attention" ? testNeedsAttention(summary) : summary[filter] > 0;
}
