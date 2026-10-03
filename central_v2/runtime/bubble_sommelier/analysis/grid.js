"use strict";

const { median } = require("./statistics");

const GRID_SIZE = 12;
const MIN_CELL_COVERAGE = 0.05;
const ANALYZED_START = 0.10;
const ANALYZED_END = 0.90;

function analyzeGrid(data, info, reference, acceptsRGB) {
  const x0 = Math.floor(info.width * ANALYZED_START);
  const x1 = Math.ceil(info.width * ANALYZED_END);
  const y0 = Math.floor(info.height * ANALYZED_START);
  const y1 = Math.ceil(info.height * ANALYZED_END);

  const analyzedWidth = x1 - x0;
  const analyzedHeight = y1 - y0;
  const cells = [];
  let totalAccepted = 0;
  let totalExamined = 0;

  for (let gy = 0; gy < GRID_SIZE; gy++) {
    for (let gx = 0; gx < GRID_SIZE; gx++) {
      const sx0 = x0 + Math.floor(gx * analyzedWidth / GRID_SIZE);
      const sx1 = x0 + Math.floor((gx + 1) * analyzedWidth / GRID_SIZE);
      const sy0 = y0 + Math.floor(gy * analyzedHeight / GRID_SIZE);
      const sy1 = y0 + Math.floor((gy + 1) * analyzedHeight / GRID_SIZE);

      const red = [];
      const green = [];
      const blue = [];
      let accepted = 0;
      let examined = 0;

      for (let y = sy0; y < sy1; y++) {
        for (let x = sx0; x < sx1; x++) {
          const offset = (y * info.width + x) * info.channels;
          const r = data[offset];
          const g = data[offset + 1];
          const b = data[offset + 2];

          examined++;
          totalExamined++;

          if (acceptsRGB(r, g, b, reference)) {
            red.push(r);
            green.push(g);
            blue.push(b);
            accepted++;
            totalAccepted++;
          }
        }
      }

      const coverage = examined ? accepted / examined : 0;

      if (accepted && coverage >= MIN_CELL_COVERAGE) {
        cells.push({
          gx,
          gy,
          r: median(red),
          g: median(green),
          b: median(blue),
          coverage
        });
      }
    }
  }

  return {
    cells,
    coverage: totalExamined ? totalAccepted / totalExamined : 0
  };
}

module.exports = {
  GRID_SIZE,
  MIN_CELL_COVERAGE,
  ANALYZED_START,
  ANALYZED_END,
  analyzeGrid
};
