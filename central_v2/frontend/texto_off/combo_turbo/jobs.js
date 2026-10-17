import { fetchComboJob } from "/texto_off/combo_turbo/api.js";
import { TERMINAL } from "/texto_off/combo_turbo/model.js";

export const jobStorageKey = (provider, manga) => `combo-turbo-job:${provider}:${manga}`;
export function readStoredJob(provider, manga) {
  try { return JSON.parse(localStorage.getItem(jobStorageKey(provider, manga)) || "null"); }
  catch { return null; }
}
export function saveStoredJob(provider, manga, job) {
  try { localStorage.setItem(jobStorageKey(provider, manga), JSON.stringify(job)); }
  catch { /* The active tab still polls the server without persistent recovery. */ }
}

export async function watchJob(job, options) {
  let current = job;
  while (options.isActive()) {
    await new Promise((resolve) => setTimeout(resolve, 700));
    const response = await fetchComboJob(current.status_url);
    current = { ...current, ...response.job };
    options.save(current);
    const active = !TERMINAL.has(String(current.status).toLowerCase());
    options.onUpdate(current, active);
    if (!active) break;
  }
  if (options.isActive()) await options.onFinish(current);
  return current;
}
