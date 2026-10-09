import { browserModules } from './modules.mjs';

export class Element {
  constructor(tag = 'div') {
    this.tag = tag; this.children = []; this.events = {}; this.value = '';
    this.style = {}; this.dataset = {};
    this.classList = { toggle() {}, remove() {}, add() {} };
    if (tag === 'section') this.nodes = Object.fromEntries([
      'query', 'filters', 'results', 'status', 'execute', 'count', 'footer',
    ].map((name) => [`[data-${name}]`, new Element()]));
    if (tag === 'section') this.nodes['.auto-merge-toolbar'] = new Element();
    if (tag === 'section') this.nodes['.artistico-toolbar'] = new Element();
  }
  set innerHTML(value) { this.markup = value; }
  querySelector(selector) { return this.nodes?.[selector]; }
  replaceChildren(...children) { this.children = children; }
  append(...children) { this.children.push(...children); }
  insertAdjacentHTML(_position, markup) { this.markup = (this.markup || '') + markup; }
  getBoundingClientRect() { return { left: 50, right: 100, top: 50 }; }
  getContext() { return { clearRect() {}, drawImage: (...args) => {
    this.draws ??= []; this.draws.push(args);
  } }; }
  after(element) { this.afterElement = element; }
  setAttribute(name, value) { this[name] = value; }
  addEventListener(name, callback) { this.events[name] = callback; }
  removeEventListener(name) { delete this.events[name]; }
  remove() { this.removed = true; }
  showModal() { this.open = true; }
  close(value) { this.returnValue = value; this.events.close?.(); }
}

export function setup({ mockReview = false } = {}) {
  const calls = [], tables = [], requests = [], progressStates = [], confirmations = [], restoreCalls = [];
  const reviewOpens = [], images = [];
  const body = new Element('body');
  const data = {
    degrade: { treatment: 'degrade', chapters: [{ chapter: '1', pages: ['a.png'], page_count: 1,
      occurrence_count: 2, status: 'pending', occurrences: ['deg-1', 'deg-2'].map((id) => ({
        id, page: 'a.png', status: 'pending', roi: { x: 1, y: 2, width: 3, height: 4 },
        preview: { width: 100, height: 100, sha256: 'page-sha' } })) }],
      summary: { chapters: 1, pages: 1, occurrences: 2 } },
    estilizado: { treatment: 'estilizado', chapters: [{ chapter: '2', pages: ['art.png'],
      page_count: 1, occurrence_count: 1, status: 'pending', occurrences: [{ id: 'art-1',
        page: 'art.png', status: 'pending', roi: { x: 1, y: 2, width: 3, height: 4 },
        preview: { width: 100, height: 100, sha256: 'page-sha' } }] }],
      summary: { chapters: 1, pages: 1, occurrences: 1 } },
    gradiente_suave: { treatment: 'gradiente_suave', chapters: [{ chapter: '1', pages: ['b.png', 'c.png'],
      page_count: 2, occurrence_count: 2, status: 'processed', review_available: true,
      occurrences: ['b.png', 'c.png'].map((page, index) => ({ id: `smooth-${index}`,
        page, status: 'processed', roi: { x: 1, y: 2, width: 3, height: 4 },
        preview: { width: 100, height: 100, sha256: 'page-sha' } })) }],
    summary: { chapters: 1, pages: 2, occurrences: 2 } },
  };
  class ImageMock {
    constructor() { this.naturalWidth = 100; this.naturalHeight = 100; images.push(this); }
    set src(value) { this.url = value; }
  }
  const load = browserModules({ document: { createElement: (tag) => new Element(tag),
      createTextNode: (text) => Object.assign(new Element('text'), { textContent: text }), body },
    window: { addEventListener() {}, removeEventListener() {} },
    innerWidth: 1200, innerHeight: 800, Image: ImageMock,
    Option: class extends Element { constructor(text, value) { super('option'); this.textContent = text; this.value = value; } },
    AbortController, calls, tables, data, requests, progressStates, confirmations, restoreCalls, reviewOpens }, {
    '/_app/state/context.js': `export function getContext() { return {provider:'comix',manga:'Example'}; }
      export function subscribeContext() { return () => {}; }`,
    '/_app/api/textoff.js': `export async function fetchSpecialTreatments(provider,manga,treatment) {
      globalThis.calls.push(treatment); return globalThis.data[treatment]; }
      export function styledPreviewImageUrl(provider,manga,chapter,page,id,sha) {
        return '/preview/' + chapter + '/' + page + '?id=' + id + '&sha=' + sha; }
      export async function startSpecialTreatments(...args) {
        globalThis.requests.push(args); return {job:{id:'job'}}; }
      export async function previewSpecialPageRestore(provider,manga,chapter,page) {
        globalThis.restoreCalls.push(['preview',chapter,page]);
        return {proposal:{chapter,page,version:'version',current_sha256:'current',
          restored_sha256:'restored',affected_occurrences:6}}; }
      export function specialPageRestoreImageUrl(provider,manga,proposal,side) {
        return '/restore/' + side; }
      export async function startSpecialPageRestore(provider,manga,proposal) {
        globalThis.restoreCalls.push(['publish',proposal.page]); return {job:{id:'restore'}}; }
      export async function waitForTextoffJob(job, onProgress = () => {}) {
        onProgress({status:'running',progress:{percent:50,completed:0,total:1,message:'Tratando'}});
        return [{chapter:'1',status:'processed',backup:'backup/id',affected_occurrences:6}]; }`,
    '/_shared/messages/messages.js': `export async function confirmMessage(options) {
        globalThis.confirmations.push(options); return true; }
      export async function showMessage() { return true; }
      export async function showOperationSummary() { return true; }`,
    '/_shared/progress/progress.js': `export function createJobProgress() {
      return {element:{},update(state) { globalThis.progressStates.push(state); }}; }`,
    '/_shared/table/table.js': `export function createTable(columns, rows, label, options) {
      globalThis.tables.push({columns,rows,label,options}); return {tag:'table'}; }`,
    ...(mockReview ? { '/texto_off/comparison/launcher.js': `export function createComparisonLauncher() {
      return { open(row, button, target) { globalThis.reviewOpens.push({row,button,target}); },
        dispose() {} }; }` } : {}),
  });
  return { load, calls, tables, requests, progressStates, confirmations, data, restoreCalls,
    reviewOpens, images, body };
}
