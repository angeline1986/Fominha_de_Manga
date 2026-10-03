"use strict";

const fs = require("fs/promises");
const path = require("path");
const { sha256File } = require("./report");

const SUPPORTED_EXTENSIONS = new Set([".png", ".jpg", ".jpeg", ".webp"]);

async function discoverPages(inputDir) {
  const absoluteDir = path.resolve(inputDir);
  let directoryStat;

  try {
    directoryStat = await fs.stat(absoluteDir);
  } catch (error) {
    if (error.code === "ENOENT") {
      throw new Error(`Diretório de entrada inexistente: ${absoluteDir}`, { cause: error });
    }
    throw error;
  }

  if (!directoryStat.isDirectory()) {
    throw new Error(`O caminho de entrada não é um diretório: ${absoluteDir}`);
  }

  const entries = await fs.readdir(absoluteDir, { withFileTypes: true });
  const files = entries
    .filter(entry => entry.isFile() && SUPPORTED_EXTENSIONS.has(path.extname(entry.name).toLowerCase()))
    .map(entry => entry.name)
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));

  if (!files.length) {
    throw new Error(`Nenhuma página PNG/JPG/JPEG/WEBP encontrada em: ${absoluteDir}`);
  }

  const pages = [];
  for (const file of files) {
    const absolutePath = path.join(absoluteDir, file);
    pages.push({
      id: file,
      file,
      path: absolutePath,
      sha256: await sha256File(absolutePath)
    });
  }

  return pages;
}

module.exports = { SUPPORTED_EXTENSIONS, discoverPages };
