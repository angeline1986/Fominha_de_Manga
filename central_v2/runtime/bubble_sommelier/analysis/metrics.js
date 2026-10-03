"use strict";

const sharp = require("sharp");
const referenceMask = require("./reference_mask");
const { analyzeGrid } = require("./grid");
const { mad, median } = require("./statistics");

async function analyzeCrop(input) {
  const { data, info } = await sharp(input)
    .removeAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

  const reference = referenceMask.getReference(data, info);
  const grid = analyzeGrid(
    data,
    info,
    reference,
    referenceMask.acceptsRGB
  );

  const lumas = grid.cells.map(cell =>
    0.2126 * cell.r + 0.7152 * cell.g + 0.0722 * cell.b
  );
  const red = grid.cells.map(cell => cell.r);
  const green = grid.cells.map(cell => cell.g);
  const blue = grid.cells.map(cell => cell.b);

  return {
    coverage: grid.coverage,
    validCells: grid.cells.length,
    lumaMedian: median(lumas),
    lumaMad: mad(lumas),
    rgbMad: {
      r: mad(red),
      g: mad(green),
      b: mad(blue)
    },
    reference,
    cells: grid.cells
  };
}

module.exports = { analyzeCrop };
