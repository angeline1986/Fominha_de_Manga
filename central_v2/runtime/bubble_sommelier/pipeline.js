"use strict";

const crypto = require("crypto");
const path = require("path");
const { createSession } = require("./detector/session");
const { inferPage } = require("./detector/infer");
const { PROFILES, applyStrategy } = require("./detector/strategies");
const { cropRegion } = require("./detector/crop");
const { analyzeCrop } = require("./analysis/metrics");
const { isCandidate } = require("./analysis/candidate_gate");
const { countLabels, inputPageId, sumRawLabels, sumStrategyCounts } = require("./pipeline_summary");

async function runPipeline({ pages, profile, modelPath, onCheckpoint, onCrop, onProgress,
  visualAnalysisEnabled = false, visualAnalyzer = null }) {
  if (!Array.isArray(pages)) throw new TypeError("pages deve ser um array");
  if (!PROFILES[profile]) throw new Error(`Perfil desconhecido: ${profile}`);
  if (!modelPath) throw new Error("modelPath é obrigatório");

  const session = await createSession(modelPath);
  try {
    const pageRuns = [];
    let tileCount = 0;
    let rawDetectionCount = 0;
    let crops = 0;
    let coverageGe075 = 0;
    let candidateCount = 0;
    const resultPages = [];

    for (let pageIndex = 0; pageIndex < pages.length; pageIndex++) {
      const inputPage = pages[pageIndex];
      const pageId = inputPageId(inputPage);
      const current = pageIndex + 1;
      if (onProgress) {
        await onProgress({ type: "page_started", current, total: pages.length, page_id: pageId });
      }

      const inference = await inferPage(session, inputPage.path);
      tileCount += inference.tiles.length;
      rawDetectionCount += inference.detections.length;
      const strategy = applyStrategy(inference.detections, profile);
      const page = { inputPage, inference, strategy };
      pageRuns.push(page);

      const bubbles = [];
      let pageCandidates = 0;
      for (let index = 0; index < strategy.detections.length; index++) {
        const detection = strategy.detections[index];
        const crop = await cropRegion(inputPage.path, detection, profile);
        const cropIdentity = `${path.parse(pageId).name}-bubble-${String(index + 1).padStart(2, "0")}`;

        if (onCrop) {
          await onCrop({
            identity: cropIdentity,
            page_id: pageId,
            profile_id: profile,
            detection,
            geometry: crop.geometry,
            png: crop.png
          });
        }

        const measured = await analyzeCrop(crop.png);
        const metrics = {
          coverage: measured.coverage,
          validCells: measured.validCells,
          lumaMedian: measured.lumaMedian,
          lumaMad: measured.lumaMad,
          rgbMad: measured.rgbMad,
          reference: measured.reference
        };
        const candidate = isCandidate(metrics);

        crops++;
        if (metrics.coverage >= 0.75) coverageGe075++;
        if (candidate) {
          candidateCount++;
          pageCandidates++;
        }

        let visualAnalysis;
        if (visualAnalysisEnabled === true) {
          visualAnalysis = await safeVisualAnalysis({
            cropPng: Buffer.from(crop.png),
            analyzer: visualAnalyzer,
            context: {
              identity: cropIdentity,
              page_id: pageId,
              profile_id: profile,
              detection,
              geometry: crop.geometry,
              metrics,
              cells: measured.cells,
              candidate
            }
          });
        }

        const bubble = {
          identity: cropIdentity,
          page_id: pageId,
          bubble_index: index + 1,
          label: detection.label,
          confidence: detection.confidence,
          bbox: detection.bbox,
          tile_id: detection.tile_id,
          profile_id: profile,
          crop: {
            coordinates: crop.geometry,
            width: crop.geometry.width,
            height: crop.geometry.height,
            sha256: crypto.createHash("sha256").update(crop.png).digest("hex")
          },
          metrics,
          candidate
        };
        if (visualAnalysisEnabled === true) bubble.visual_analysis = visualAnalysis;
        bubbles.push(bubble);
      }

      resultPages.push({
        page_id: pageId,
        input_sha256: inputPage.sha256 || null,
        width: inference.page.width,
        height: inference.page.height,
        tiles: inference.tiles.length,
        raw_detections: inference.detections.length,
        raw_labels: countLabels(inference.detections),
        strategy: strategy.counts,
        bubbles
      });

      if (onProgress) {
        await onProgress({
          type: "page_completed",
          current,
          total: pages.length,
          page_id: pageId,
          raw_detections: inference.detections.length,
          bubbles: bubbles.length,
          candidates: pageCandidates,
          percent: Math.floor(current * 100 / pages.length)
        });
      }
    }

    const inferenceCheckpoint = {
      pages: pageRuns.length,
      tiles: tileCount,
      rawDetections: rawDetectionCount,
      rawLabels: sumRawLabels(pageRuns.map(page => ({ inference: page.inference })))
    };
    if (onCheckpoint) await onCheckpoint("inference", inferenceCheckpoint);

    const strategyCounts = sumStrategyCounts(pageRuns);
    const strategyCheckpoint = {
      ...strategyCounts,
      postNmsBeforeFinalLabelSelection: strategyCounts.afterNms
    };
    if (onCheckpoint) await onCheckpoint("strategy", strategyCheckpoint);

    return {
      profile_id: profile,
      model: modelPath,
      checkpoints: {
        inference: inferenceCheckpoint,
        strategy: strategyCheckpoint,
        result: {
          pages: resultPages.length,
          tiles: inferenceCheckpoint.tiles,
          rawDetections: inferenceCheckpoint.rawDetections,
          afterInitialLabelSelection: strategyCounts.afterInitialLabelSelection,
          afterNms: strategyCounts.afterNms,
          finalDetections: strategyCounts.finalDetections,
          crops,
          coverageGe075,
          candidates: candidateCount
        }
      },
      pages: resultPages
    };
  } finally {
    if (typeof session.release === "function") await session.release();
  }
}

async function safeVisualAnalysis(input) {
  try {
    return await require("./analysis/visual_analysis").runOptionalVisualAnalysis(input);
  } catch (error) {
    return { status: "failed", error: {
      name: error.name || "Error", message: error.message || String(error)
    } };
  }
}

module.exports = { runPipeline };
