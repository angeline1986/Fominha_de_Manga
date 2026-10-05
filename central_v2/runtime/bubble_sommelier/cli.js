"use strict";

const path = require("path");
const { runBubbleSommelier } = require("./runner");

const REQUIRED_OPTIONS = new Set(["--input", "--output", "--model", "--profile"]);

function writeProgress(event) {
  return new Promise((resolve, reject) => {
    process.stdout.write(`${JSON.stringify({ type: "progress", payload: event })}\n`, error => {
      if (error) reject(error);
      else resolve();
    });
  });
}

function parseArguments(args) {
  const options = new Map();
  for (let index = 0; index < args.length;) {
    const key = args[index];
    if (key === "--visual-analysis") {
      if (options.has(key)) throw new Error(`Argumento duplicado: ${key}`);
      options.set(key, true);
      index++;
      continue;
    }
    const value = args[index + 1];
    if (!REQUIRED_OPTIONS.has(key)) throw new Error(`Argumento desconhecido: ${key}`);
    if (options.has(key)) throw new Error(`Argumento duplicado: ${key}`);
    if (!value || value.startsWith("--")) throw new Error(`Valor ausente para ${key}`);
    options.set(key, value);
    index += 2;
  }

  for (const key of REQUIRED_OPTIONS) {
    if (!options.has(key)) throw new Error(`Argumento obrigatório ausente: ${key}`);
  }

  return {
    inputDir: path.resolve(options.get("--input")),
    outputDir: path.resolve(options.get("--output")),
    modelPath: path.resolve(options.get("--model")),
    profileId: options.get("--profile"),
    visualAnalysisEnabled: options.has("--visual-analysis")
  };
}

async function main() {
  const options = parseArguments(process.argv.slice(2));
  const report = await runBubbleSommelier({
    ...options,
    progressContext: {
      provider: process.env.BUBBLE_SOMMELIER_PROVIDER,
      manga: process.env.BUBBLE_SOMMELIER_MANGA,
      chapter: process.env.BUBBLE_SOMMELIER_CHAPTER
    },
    onProgress: writeProgress
  });
  console.log(JSON.stringify({
    status: report.status,
    profile_id: report.profile_id,
    output: path.join(options.outputDir, "report.json"),
    checkpoints: report.checkpoints
  }));
}

if (require.main === module) {
  main().catch(error => {
    console.error(`BubbleSommelier: ${error && error.message ? error.message : error}`);
    process.exitCode = 1;
  });
}

module.exports = { parseArguments };
