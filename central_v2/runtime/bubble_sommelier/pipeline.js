"use strict";

const crypto = require("crypto");
const path = require("path");
const { createSession } = require("./detector/session");
const { inferPage } = require("./detector/infer");
const { PROFILES, applyStrategy } = require("./detector/strategies");
const { cropRegion } = require("./detector/crop");
const { analyzeCrop } = require("./analysis/metrics");
const { isCandidate } = require("./analysis/candidate_gate");

function sumStrategyCounts(pages) {
  return pages.reduce((totals, page) => {
    totals.input += page.strategy.counts.input;
    totals.afterInitialLabelSelection += page.strategy.counts.after_initial_label_selection;
    totals.afterNms += page.strategy.counts.after_nms;
    totals.finalDetections += page.strategy.counts.final;
    return totals;
  }, {
    input: 0,
    afterInitialLabelSelection: 0,
    afterNms: 0,
    finalDetections: 0
  });
}

function sumRawLabels(pages) {
  const counts = {};
  for (const page of pages) {
    for (const detection of page.inference.detections) {
      const label = String(detection.label);
      counts[label] = (counts[label] || 0) + 1;
    }
  }
  return counts;
}

async function runPipeline({ pages, profile, modelPath, onCheckpoint, onCrop }) {
  if (!Array.isArray(pages)) throw new TypeError("pages deve ser um array");
  if (!PROFILES[profile]) throw new Error(`Perfil desconhecido: ${profile}`);
  if (!modelPath) throw new Error("modelPath é obrigatório");

  const session = await createSession(modelPath);
  try {
    const pageRuns = [];

    for (const inputPage of pages) {
      const inference = await inferPage(session, inputPage.path);
      pageRuns.push({ inputPage, inference });
    }

    const inferenceCheckpoint = {
      pages: pageRuns.length,
      tiles: pageRuns.reduce((total, page) => total + page.inference.tiles.length, 0),
      rawDetections: pageRuns.reduce((total, page) => total + page.inference.detections.length, 0),
      rawLabels: sumRawLabels(pageRuns.map(page => ({ inference: page.inference })))
    };
    if (onCheckpoint) await onCheckpoint("inference", inferenceCheckpoint);

    for (const page of pageRuns) {
      page.strategy = applyStrategy(page.inference.detections, profile);
    }

    const strategyCounts = sumStrategyCounts(pageRuns);
    const strategyCheckpoint = {
      ...strategyCounts,
      postNmsBeforeFinalLabelSelection: strategyCounts.afterNms
    };
    if (onCheckpoint) await onCheckpoint("strategy", strategyCheckpoint);

    let crops = 0;
    let coverageGe075 = 0;
    let candidateCount = 0;
    const resultPages = [];

    for (const page of pageRuns) {
      const pageId = inputPageId(page.inputPage);
      const bubbles = [];

      for (let index = 0; index < page.strategy.detections.length; index++) {
        const detection = page.strategy.detections[index];
        const crop = await cropRegion(page.inputPage.path, detection, profile);
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
        if (candidate) candidateCount++;

        bubbles.push({
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
        });
      }

      resultPages.push({
        page_id: pageId,
        input_sha256: page.inputPage.sha256 || null,
        width: page.inference.page.width,
        height: page.inference.page.height,
        tiles: page.inference.tiles.length,
        raw_detections: page.inference.detections.length,
        raw_labels: countLabels(page.inference.detections),
        strategy: page.strategy.counts,
        bubbles
      });
    }

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

function inputPageId(inputPage) {
  return inputPage.id || inputPage.file || path.basename(inputPage.path);
}

function countLabels(detections) {
  const counts = {};
  for (const detection of detections) {
    const label = String(detection.label);
    counts[label] = (counts[label] || 0) + 1;
  }
  return counts;
}

module.exports = { runPipeline };
