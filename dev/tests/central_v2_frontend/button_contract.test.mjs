import test from 'node:test';
import assert from 'node:assert/strict';
import { readdir, readFile } from 'node:fs/promises';
import { resolve, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontend = resolve(fileURLToPath(new URL('../../../central_v2/frontend/', import.meta.url)));

async function filesUnder(folder, extension) {
  const entries = await readdir(folder, { withFileTypes: true });
  const nested = await Promise.all(entries.map((entry) => {
    const path = resolve(folder, entry.name);
    return entry.isDirectory() ? filesUnder(path, extension)
      : path.endsWith(extension) ? [path] : [];
  }));
  return nested.flat();
}

test('every JavaScript-created button declares a styled component class', async () => {
  const scripts = await filesUnder(frontend, '.js');
  const styles = (await Promise.all((await filesUnder(frontend, '.css'))
    .map((path) => readFile(path, 'utf8')))).join('\n');
  const violations = [];
  for (const path of scripts) {
    const source = await readFile(path, 'utf8');
    const constructors = [...source.matchAll(/(?:const|let)\s+(\w+)\s*=\s*document\.createElement\((['"])button\2\)/g)];
    constructors.forEach((match, index) => {
      const name = match[1];
      const end = constructors[index + 1]?.index ?? source.length;
      const body = source.slice(match.index, end);
      const classMatch = body.match(new RegExp(`\\b${name}\\.className\\s*=\\s*([\"'\x60])([^\\n]*?)\\1`));
      if (!classMatch) {
        violations.push(`${relative(frontend, path)}: botão sem classe de componente`);
        return;
      }
      const classes = classMatch[2].match(/[A-Za-z_][\w-]*/g) || [];
      const styled = classes.some((className) => className === 'btn'
        ? /\.btn\s*\{/.test(styles)
        : styles.includes(`.${className}`));
      if (!styled) violations.push(`${relative(frontend, path)}: classe sem regra visual (${classMatch[2]})`);
    });
  }
  assert.deepEqual(violations, [], violations.join('\n'));
});
