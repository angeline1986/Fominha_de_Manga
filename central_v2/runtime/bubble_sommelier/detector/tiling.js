"use strict";

const path = require("path");
const sharp = require("sharp");

const STRIDE_RATIO = 0.75;
const MIN_TILE_HEIGHT = 200;

async function planTiles(inputPath) {
  const page = await sharp(inputPath).metadata();
  const stride = Math.round(page.width * STRIDE_RATIO);
  const tiles = [];

  for (let top = 0; top < page.height; top += stride) {
    const height = Math.min(page.width, page.height - top);
    if (height < MIN_TILE_HEIGHT) break;

    tiles.push({
      tile_id: `${path.parse(inputPath).name}:tile-${String(tiles.length + 1).padStart(2, "0")}`,
      top,
      width: page.width,
      height
    });
  }

  return {
    page: { width: page.width, height: page.height },
    tileWidth: page.width,
    stride,
    tiles
  };
}

module.exports = { STRIDE_RATIO, MIN_TILE_HEIGHT, planTiles };
