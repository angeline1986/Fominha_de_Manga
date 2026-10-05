"use strict";

const path = require("path");

function sumStrategyCounts(pages) {
  return pages.reduce((totals, page) => {
    totals.input += page.strategy.counts.input;
    totals.afterInitialLabelSelection += page.strategy.counts.after_initial_label_selection;
    totals.afterNms += page.strategy.counts.after_nms;
    totals.finalDetections += page.strategy.counts.final;
    return totals;
  }, { input: 0, afterInitialLabelSelection: 0, afterNms: 0, finalDetections: 0 });
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

function countLabels(detections) {
  const counts = {};
  for (const detection of detections) {
    const label = String(detection.label);
    counts[label] = (counts[label] || 0) + 1;
  }
  return counts;
}

function inputPageId(inputPage) {
  return inputPage.id || inputPage.file || path.basename(inputPage.path);
}

module.exports = { countLabels, inputPageId, sumRawLabels, sumStrategyCounts };
