import { loadSnapshot } from './app.js';
export async function startRefresh(target, button, status, load = loadSnapshot, request = fetch) {
  const refresh = async () => {
    if (document.visibilityState === 'hidden' || button.disabled) return;
    button.disabled = true;
    status.textContent = 'Refreshing current prices; finalized history is separate.';
    const controller = new AbortController();
    const deadline = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await request('/api/refresh', { method: 'POST', credentials: 'same-origin', signal: controller.signal });
      if (response.status === 401) { status.textContent = 'Session expired. Reload to sign in. Previous values have not refreshed.'; return; }
      if (!response.ok) throw Error();
      const result = await response.json();
      if (['refreshed', 'cached'].includes(result.state)) {
        if (document.visibilityState === 'hidden') return;
        await load(target);
        status.textContent = 'Current values refreshed together. Read each source observation time; finalized history remains separate.';
      } else status.textContent = `Previous accepted values retained (${result.reason ?? 'refresh_failed'}). Retry Refresh current prices.`;
    } catch { status.textContent = 'Current refresh failed or exceeded ten seconds. Previous accepted values retained. Retry Refresh current prices.'; }
    finally { clearTimeout(deadline); button.disabled = false; }
  };
  button.textContent = 'Refresh current prices';
  button.addEventListener('click', refresh);
  await load(target);
  await refresh();
}
const target = document.querySelector('#snapshot'), button = document.querySelector('#reload'), status = document.querySelector('#refresh-status');
if (target && button && status) startRefresh(target, button, status);
