const section = document.querySelector('#imports');
if (section) {
  section.innerHTML = '<h2>Import CSV history</h2><p>Upload Account.csv or Transactions.csv (UTF-8, up to 5 MB). Previous accepted values remain visible until processing succeeds. The hosted runner checks the queue hourly; scheduled jobs can be delayed.</p><form><label>CSV file <input type="file" accept=".csv,text/csv" required></label><button type="submit">Upload privately</button></form><button type="button" id="import-status">Check import status</button><p role="status" id="import-message"></p><ul id="import-jobs"></ul>';
  const message = section.querySelector('#import-message');
  const jobsList = section.querySelector('#import-jobs');
  async function status() {
    try {
      const response = await fetch('/api/imports', { cache: 'no-store' });
      if (!response.ok) throw Error(response.status === 503 ? 'Import processing is not configured or unavailable. Existing accepted values are preserved.' : 'Sign in again to view imports.');
      const { jobs } = await response.json();
      jobsList.replaceChildren();
      for (const job of jobs) {
        const row = document.createElement('li');
        row.textContent = `Import ${job.job_id}: ${job.state}. Background history: ${job.history_state}. ${(job.diagnostics || []).join(', ')}`;
        if (job.state === 'failed' || (job.state === 'processing' && Date.now() - Date.parse(job.updated_at) > 15 * 60 * 1000)) {
          const retry = document.createElement('button'); retry.textContent = 'Retry safely';
          retry.onclick = async () => {
            retry.disabled = true;
            try {
              const response = await fetch(`/api/imports/${encodeURIComponent(job.job_id)}/retry`, { method: 'POST' });
              if (!response.ok) throw Error('Retry unavailable. Check status before trying again.');
              message.textContent = 'Retry queued. Previous accepted values remain available.';
              await status();
            } catch (error) { message.textContent = error.message; retry.disabled = false; }
          };
          row.append(' ', retry);
        }
        jobsList.append(row);
      }
      if (!jobs.length) message.textContent = 'No CSV imports yet.';
    } catch (error) { message.textContent = error.message; }
  }
  section.querySelector('form').onsubmit = async event => {
    event.preventDefault();
    const file = section.querySelector('input').files[0];
    if (!file || !file.size || file.size > 5 * 1024 * 1024) { message.textContent = 'Choose a nonempty CSV up to 5 MB.'; return; }
    const button = section.querySelector('button[type="submit"]'); button.disabled = true;
    try {
      const response = await fetch('/api/imports', { method: 'POST', headers: { 'Content-Type': 'text/csv' }, body: file });
      if (!response.ok) throw Error('Upload unavailable. Check import status before retrying; identical files share one import identity.');
      message.textContent = 'Upload staged privately. Processing does not refresh current prices. Check status for completion, then reload the overview.';
      await status();
    } catch (error) { message.textContent = error.message; }
    finally { button.disabled = false; }
  };
  section.querySelector('#import-status').onclick = status;
  status();
}
