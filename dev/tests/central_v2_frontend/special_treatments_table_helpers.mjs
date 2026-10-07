import { browserModules } from './modules.mjs';

export class Element {
  constructor(tag = 'div') {
    this.tag = tag; this.children = []; this.events = {}; this.value = '';
    this.classList = { toggle() {}, remove() {}, add() {} };
    if (tag === 'section') this.nodes = Object.fromEntries([
      'query', 'filters', 'results', 'status', 'execute',
    ].map((name) => [`[data-${name}]`, new Element()]));
    if (tag === 'section') this.nodes['.auto-merge-toolbar'] = new Element();
  }
  set innerHTML(value) { this.markup = value; }
  querySelector(selector) { return this.nodes?.[selector]; }
  replaceChildren(...children) { this.children = children; }
  append(...children) { this.children.push(...children); }
  after(element) { this.afterElement = element; }
  setAttribute(name, value) { this[name] = value; }
  addEventListener(name, callback) { this.events[name] = callback; }
  removeEventListener(name) { delete this.events[name]; }
  remove() { this.removed = true; }
}

export function setup() {
  const calls = [], tables = [], requests = [], progressStates = [], confirmations = [];
  const data = {
    degrade: { treatment: 'degrade', chapters: [{ chapter: '1', pages: ['a.png'], page_count: 1,
      occurrence_count: 2, status: 'pending' }], summary: { chapters: 1, pages: 1, occurrences: 2 } },
    estilizado: { treatment: 'estilizado', chapters: [], summary: { chapters: 0, pages: 0, occurrences: 0 } },
    gradiente_suave: { treatment: 'gradiente_suave', chapters: [{ chapter: '1', pages: ['b.png', 'c.png'],
      page_count: 2, occurrence_count: 11, status: 'processed', review_available: true }],
    summary: { chapters: 1, pages: 2, occurrences: 11 } },
  };
  const load = browserModules({ document: { createElement: (tag) => new Element(tag) },
    AbortController, calls, tables, data, requests, progressStates, confirmations }, {
    '/_app/state/context.js': `export function getContext() { return {provider:'comix',manga:'Example'}; }
      export function subscribeContext() { return () => {}; }`,
    '/_app/api/textoff.js': `export async function fetchSpecialTreatments(provider,manga,treatment) {
      globalThis.calls.push(treatment); return globalThis.data[treatment]; }
      export async function startSpecialTreatments(...args) {
        globalThis.requests.push(args); return {job:{id:'job'}}; }
      export async function waitForTextoffJob(job, onProgress) {
        onProgress({status:'running',progress:{percent:50,completed:0,total:1,message:'Tratando'}});
        return [{chapter:'1',status:'processed'}]; }`,
    '/_shared/messages/messages.js': `export async function confirmMessage(options) {
        globalThis.confirmations.push(options); return true; }
      export async function showMessage() { return true; }
      export async function showOperationSummary() { return true; }`,
    '/_shared/progress/progress.js': `export function createJobProgress() {
      return {element:{},update(state) { globalThis.progressStates.push(state); }}; }`,
    '/_shared/table/table.js': `export function createTable(columns, rows, label, options) {
      globalThis.tables.push({columns,rows,label,options}); return {tag:'table'}; }`,
  });
  return { load, calls, tables, requests, progressStates, confirmations, data };
}
