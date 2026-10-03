"use strict";

const { planTiles } = require("./tiling");
const { preprocessTile } = require("./preprocess");

const MIN_CONFIDENCE = 0.30;

function pageCoordinate(value, offset, limit) {
  return Math.max(0, Math.min(limit, value + offset));
}

async function inferPage(session, inputPath) {
  const plan = await planTiles(inputPath);
  const detections = [];

  for (const tile of plan.tiles) {
    const inputs = await preprocessTile(inputPath, tile, plan.page);
    const outputs = await session.run({
      images: inputs.images,
      orig_target_sizes: inputs.orig_target_sizes
    });

    const labels = outputs.labels.data;
    const boxes = outputs.boxes.data;
    const scores = outputs.scores.data;

    for (let i = 0; i < scores.length; i++) {
      const confidence = Number(scores[i]);
      if (confidence < MIN_CONFIDENCE) continue;

      const base = i * 4;
      const bbox = {
        x1: pageCoordinate(Number(boxes[base]), 0, plan.page.width),
        y1: pageCoordinate(Number(boxes[base + 1]), tile.top, plan.page.height),
        x2: pageCoordinate(Number(boxes[base + 2]), 0, plan.page.width),
        y2: pageCoordinate(Number(boxes[base + 3]), tile.top, plan.page.height)
      };

      if (bbox.x2 <= bbox.x1 || bbox.y2 <= bbox.y1) continue;

      detections.push({
        label: Number(labels[i]),
        confidence,
        bbox,
        tile_id: tile.tile_id
      });
    }
  }

  return {
    page: plan.page,
    stride: plan.stride,
    tiles: plan.tiles,
    detections
  };
}

module.exports = { MIN_CONFIDENCE, inferPage };
