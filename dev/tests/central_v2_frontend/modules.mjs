import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createContext, SourceTextModule } from 'node:vm';

const frontend = fileURLToPath(new URL('../../../central_v2/frontend/', import.meta.url));

// Fresh module graph per test; browser imports keep their production URLs.
export function browserModules(globals = {}, sources = {}) {
  const context = createContext({ URLSearchParams, console, ...globals });
  const modules = new Map();

  function load(specifier) {
    if (!modules.has(specifier)) {
      modules.set(specifier, (async () => {
        const source = sources[specifier]
          ?? await readFile(resolve(frontend, `.${specifier}`), 'utf8');
        const module = new SourceTextModule(source, {
          context,
          identifier: specifier,
          async importModuleDynamically(path) {
            const imported = await load(path);
            await imported.evaluate();
            return imported;
          },
        });
        await module.link(load);
        return module;
      })());
    }
    return modules.get(specifier);
  }

  return async (specifier) => {
    const module = await load(specifier);
    await module.evaluate();
    return module.namespace;
  };
}

export function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

export const textDocument = {
  createElement() {
    return {
      textContent: '',
      get innerHTML() {
        return this.textContent.replaceAll('&', '&amp;')
          .replaceAll('<', '&lt;').replaceAll('>', '&gt;');
      },
    };
  },
};

export function mangaState(manga, count = 3) {
  return { provider: 'comix', manga, chapters: ['1'], summary: { chapters: count } };
}
