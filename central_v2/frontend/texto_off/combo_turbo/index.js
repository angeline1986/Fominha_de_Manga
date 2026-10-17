import { getContext } from "/_app/state/context.js";
import { invalidateCleanerOverview } from "/_app/state/cleaner_revision.js";
import { describeError, fetchComboJob, fetchComboResult, planCombo, startCombo } from "/texto_off/combo_turbo/api.js";
import { comboState, MAX_CHAPTERS, TERMINAL, summarizePlan } from "/texto_off/combo_turbo/model.js";
import { isConflict, reconcileSelection, selectChapter, selectChapters, selectEligible } from "/texto_off/combo_turbo/behavior.js";
import { readStoredJob, saveStoredJob, watchJob } from "/texto_off/combo_turbo/jobs.js";
import { createComboView } from "/texto_off/combo_turbo/view.js";
import { loadComboRows, markComboResultInvalidated, savedComboUiState, saveComboUiState } from "/texto_off/combo_turbo/cache.js";
import { watchComboChanges } from "/texto_off/combo_turbo/lifecycle.js";

const keyFor = (provider, manga) => `${provider}:${manga}`;

export function render(container) {
  const element = document.createElement("div");
  const stylesheet = document.createElement("link");
  stylesheet.rel = "stylesheet"; stylesheet.href = "/texto_off/combo_turbo/style.css";
  document.head.append(stylesheet);
  container.replaceChildren(element);
  let disposed = false, generation = 0, busy = false, loading = false, reloadQueued = false;
  let contextKey = "", planToken = null, plannedSelection = "", planApproved = false;
  let selected = new Set(), rows = [], activeJob = null, conflict = false, planExpiresAt = 0;
  let planExpiryTimer = null, currentResult = null;
  const view = createComboView({
    refresh: () => load(true, true), plan: planSelected, run: execute,
    select, selectMany, selectEligible: chooseEligible,
    onUiState: (state) => saveComboUiState(getContext().provider, getContext().manga, state),
  }, savedComboUiState(getContext().provider, getContext().manga));
  element.append(view.element);

  function update(extra = {}) {
    const context = getContext();
    view.update({ provider: context.provider, manga: context.manga, rows, selected, busy, loading, conflict, job: activeJob, result: currentResult, planValid: Boolean(planToken) && planApproved && Date.now() < planExpiresAt, ...extra });
  }
  function message(text) {
    const node = view.element.querySelector("[data-message]");
    node.textContent = text || "";
    node.classList.toggle("is-error", Boolean(text));
  }
  function invalidatePlan() {
    planToken = null; plannedSelection = "";
    planApproved = false;
    planExpiresAt = 0; clearTimeout(planExpiryTimer);
  }
  function select(chapter, checked) {
    const result = selectChapter(selected, rows, chapter, checked);
    if (result.reason) { message(result.reason); return; }
    if (!result.changed) return;
    selected = result.selected; rememberSelection(); invalidatePlan(); update();
  }
  function selectMany(chapters, checked) {
    const result = selectChapters(selected, rows, chapters, checked);
    if (result.reason) { message(result.reason); return; }
    if (!result.changed) return;
    selected = result.selected; rememberSelection(); invalidatePlan(); update();
  }
  function chooseEligible() {
    selected = selectEligible(rows);
    rememberSelection();
    invalidatePlan();
    message(rows.filter((row) => comboState(row) === "PLANNED").length > MAX_CHAPTERS
      ? `Selecionados os primeiros ${MAX_CHAPTERS} capítulos elegíveis; esse é o limite por execução.` : "");
    update();
  }
  function rememberSelection() {
    saveComboUiState(getContext().provider, getContext().manga, { selected: [...selected] });
  }

  async function load(preserveSelection = true, refresh = false) {
    if (loading && preserveSelection) { reloadQueued = true; return; }
    const { provider, manga } = getContext();
    const id = ++generation;
    loading = true;
    if (!provider || !manga) {
      rows = []; selected.clear(); activeJob = null; currentResult = null;
      loading = false; invalidatePlan(); update({ loading: false, job: null, result: null });
      message("Selecione provider e obra para consultar os capítulos."); return;
    }
    const nextKey = keyFor(provider, manga);
    if (contextKey !== nextKey) {
      selected = new Set(savedComboUiState(provider, manga).selected || []);
      view.restore(savedComboUiState(provider, manga));
      invalidatePlan(); activeJob = null; currentResult = null;
      update({ job: null, result: null });
    }
    contextKey = nextKey; conflict = false; invalidatePlan();
    update({ loading: true }); message("Consultando capítulos e elegibilidade…");
    try {
      const previous = preserveSelection ? selected
        : new Set(savedComboUiState(provider, manga).selected || []);
      rows = await loadComboRows(provider, manga, { refresh,
        onBatch: (done, total) => { if (!disposed && id === generation) message(`Consultando elegibilidade: ${done} de ${total} capítulos…`); } });
      if (disposed || id !== generation) return;
      selected = new Set([...previous].filter((chapter) => rows.some((row) =>
        row.chapter === chapter && comboState(row) === "PLANNED")));
      const reconciled = reconcileSelection(selected, rows);
      if (reconciled.changed) { selected = reconciled.selected; invalidatePlan(); }
      saveComboUiState(provider, manga, { selected: [...selected] });
      update({ loading: false });
      if (disposed || id !== generation) return;
      message(rows.some((row) => comboState(row) === "PLANNED") ? "" : "Nenhum capítulo elegível para o Combo Turbo.");
      await restoreJob(provider, manga, id);
    } catch (error) {
      if (!disposed && id === generation) { update({ loading: false }); message(describeError(error)); }
    } finally {
      if (id === generation) {
        loading = false; update({ loading: false });
        if (reloadQueued) { reloadQueued = false; load(true); }
      }
    }
  }
  async function planSelected() {
    if (busy || !selected.size) return;
    const selection = [...selected];
    const requestKey = keyFor(getContext().provider, getContext().manga);
    busy = true; invalidatePlan(); update(); message("Planejando a seleção…");
    try {
      const { provider, manga } = getContext();
      const response = await planCombo(provider, manga, selection);
      if (disposed || requestKey !== contextKey) return;
      (response.plan?.chapters || []).forEach((row) => replaceRow(row));
      planToken = response.plan_token;
      plannedSelection = JSON.stringify(selection);
      planExpiresAt = Date.now() + 29 * 60 * 1000;
      clearTimeout(planExpiryTimer);
      planExpiryTimer = setTimeout(() => { invalidatePlan(); update();
        message("O plano expirou. Planeje novamente antes de executar."); }, 29 * 60 * 1000);
      const summary = summarizePlan(response.plan);
      planApproved = summary.eligible > 0;
      message(summary.eligible ? `${summary.eligible} elegível(is), ${summary.blocked} bloqueado(s), ${summary.noWork} sem trabalho.`
        : "A seleção não contém capítulos elegíveis.");
    } catch (error) { if (requestKey === contextKey) message(describeError(error)); }
    finally { busy = false; update(); }
  }
  function replaceRow(row) {
    const index = rows.findIndex((item) => item.chapter === String(row.chapter));
    if (index >= 0) rows[index] = row;
  }
  async function execute() {
    if (busy || conflict || !planToken || !planApproved || Date.now() >= planExpiresAt
        || plannedSelection !== JSON.stringify([...selected])) {
      if (planToken && Date.now() >= planExpiresAt) { invalidatePlan(); update(); message("O plano expirou. Planeje novamente."); }
      return;
    }
    busy = true; update(); message("Iniciando execução isolada…");
    try {
      const { provider, manga } = getContext();
      const response = await startCombo(provider, manga, [...selected], planToken);
      activeJob = { ...response.job, status_url: response.status_url, result_url: response.result_url };
      saveStoredJob(provider, manga, activeJob);
      planToken = null; update({ job: activeJob, result: null });
      await watch(activeJob, generation);
    } catch (error) {
      if (isConflict(error)) { invalidatePlan(); update(); }
      conflict = /já existe/i.test(error.message);
      if (activeJob) conflict = true;
      message(describeError(error));
    } finally { busy = false; update(); }
  }
  async function restoreJob(provider, manga, id) {
    const saved = readStoredJob(provider, manga);
    if (!saved?.status_url || disposed || id !== generation) return;
    try {
      const response = await fetchComboJob(saved.status_url);
      activeJob = { ...saved, ...response.job };
      conflict = !TERMINAL.has(String(activeJob.status).toLowerCase());
      update({ job: activeJob });
      if (conflict) await watch(activeJob, id);
      else await loadResult(activeJob);
    } catch (error) { conflict = true; update(); message(describeError(error)); }
  }
  function watch(job, id) {
    return watchJob(job, { isActive: () => !disposed && id === generation,
      save: (current) => saveStoredJob(current.provider || getContext().provider,
        current.manga || getContext().manga, current),
      onUpdate: (current, active) => { activeJob = current; conflict = active; update({ job: current }); },
      onFinish: loadResult,
    });
  }
  async function loadResult(job) {
    try {
      const response = await fetchComboResult(job.result_url);
      if (markComboResultInvalidated(job.id)) {
        invalidateCleanerOverview(job.provider || getContext().provider, job.manga || getContext().manga);
      }
      currentResult = response.result || { status: response.status, results: [] };
      update({ result: currentResult });
      message(response.status === "STALE" || response.status === "INVALID"
        ? "O resultado não pode ser validado. Atualize o planejamento antes de uma nova execução."
        : "");
    } catch (error) { message(describeError(error)); }
  }
  const unsubscribeChanges = watchComboChanges(load);
  load(false);
  return () => {
    disposed = true; generation++;
    unsubscribeChanges();
    clearTimeout(planExpiryTimer);
    stylesheet.remove(); element.remove();
  };
}
