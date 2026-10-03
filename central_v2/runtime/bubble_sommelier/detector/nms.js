"use strict";

const IOU_THRESHOLD = 0.50;

function intersectionOverUnion(a, b) {
  const x1 = Math.max(a.bbox.x1, b.bbox.x1);
  const y1 = Math.max(a.bbox.y1, b.bbox.y1);
  const x2 = Math.min(a.bbox.x2, b.bbox.x2);
  const y2 = Math.min(a.bbox.y2, b.bbox.y2);

  const intersectionWidth = Math.max(0, x2 - x1);
  const intersectionHeight = Math.max(0, y2 - y1);
  const intersection = intersectionWidth * intersectionHeight;

  const areaA = Math.max(0, a.bbox.x2 - a.bbox.x1) *
    Math.max(0, a.bbox.y2 - a.bbox.y1);
  const areaB = Math.max(0, b.bbox.x2 - b.bbox.x1) *
    Math.max(0, b.bbox.y2 - b.bbox.y1);

  return intersection / (areaA + areaB - intersection + 1e-6);
}

function greedyNms(detections) {
  const sorted = [...detections].sort(
    (a, b) => b.confidence - a.confidence
  );
  const kept = [];

  for (const detection of sorted) {
    if (!kept.some(existing =>
      intersectionOverUnion(detection, existing) > IOU_THRESHOLD
    )) {
      kept.push(detection);
    }
  }

  return kept;
}

module.exports = { IOU_THRESHOLD, intersectionOverUnion, greedyNms };
