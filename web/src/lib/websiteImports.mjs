export const ACTIVE_IMPORTS = new Set(['queued', 'capturing', 'captured', 'storing', 'retry_wait']);
export function importLabel(job) {
  return ({ queued: 'Waiting to capture', capturing: 'Opening and rendering the webpage',
    captured: 'PDF captured', storing: 'Saving the PDF', retry_wait: 'Temporary failure — retry scheduled',
    completed: 'PDF ready', failed: 'Capture failed', cancelled: 'Import cancelled' })[job.status] || job.status;
}
