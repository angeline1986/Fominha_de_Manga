"use strict";

const path = require("path");
const { PROFILES } = require("./detector/strategies");
const { runPipeline } = require("./pipeline");
const { discoverPages } = require("./input");
const {
  sha256File,
  prepareOutputDirectory,
  persistCrop,
  buildReport,
  writeReportAtomic
} = require("./report");

async function runBubbleSommelier(options) {
  if (!options || typeof options !== "object") {
    throw new TypeError("As opções da execução são obrigatórias");
  }

  const { inputDir, outputDir, modelPath, profileId } = options;
  if (!inputDir) throw new Error("inputDir é obrigatório");
  if (!outputDir) throw new Error("outputDir é obrigatório");
  if (!modelPath) throw new Error("modelPath é obrigatório");
  if (!profileId) throw new Error("profileId é obrigatório");
  if (!Object.prototype.hasOwnProperty.call(PROFILES, profileId)) {
    throw new Error(`profileId desconhecido: ${profileId}`);
  }

  const absoluteInputDir = path.resolve(inputDir);
  const absoluteOutputDir = path.resolve(outputDir);
  const absoluteModelPath = path.resolve(modelPath);

  const pages = await discoverPages(absoluteInputDir);
  const modelSha256 = await sha256File(absoluteModelPath);
  await prepareOutputDirectory(absoluteOutputDir);

  const persistedCrops = new Map();
  const progressContext = options.progressContext || {};
  if (options.onProgress) {
    await options.onProgress({
      type: "run_started",
      provider: progressContext.provider || "—",
      manga: progressContext.manga || path.basename(absoluteInputDir),
      chapter: progressContext.chapter || "—",
      profile_id: profileId,
      total_pages: pages.length
    });
  }

  const pipelineResult = await runPipeline({
    pages,
    profile: profileId,
    modelPath: absoluteModelPath,
    onProgress: options.onProgress,
    onCrop: async crop => {
      const persisted = await persistCrop(absoluteOutputDir, crop);
      persistedCrops.set(crop.identity, persisted);
    }
  });

  const report = buildReport({
    profileId,
    modelPath: absoluteModelPath,
    modelSha256,
    inputDir: absoluteInputDir,
    pages,
    pipelineResult,
    persistedCrops
  });
  await writeReportAtomic(absoluteOutputDir, report);
  return report;
}

module.exports = { runBubbleSommelier };
