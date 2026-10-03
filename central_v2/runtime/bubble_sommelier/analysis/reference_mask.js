"use strict";

const { median } = require("./statistics");

const REFERENCE_START = 0.40;
const REFERENCE_END = 0.60;
const RGB_DISTANCE_MAX = 42;

function referenceBounds(info) {
  return {
    x0: Math.floor(info.width * REFERENCE_START),
    x1: Math.ceil(info.width * REFERENCE_END),
    y0: Math.floor(info.height * REFERENCE_START),
    y1: Math.ceil(info.height * REFERENCE_END)
  };
}

function rgbDistance(r, g, b, reference) {
  return Math.sqrt(
    (r - reference.r) ** 2 +
    (g - reference.g) ** 2 +
    (b - reference.b) ** 2
  );
}

function getReference(data, info) {
  const bounds = referenceBounds(info);
  const red = [];
  const green = [];
  const blue = [];

  for (let y = bounds.y0; y < bounds.y1; y++) {
    for (let x = bounds.x0; x < bounds.x1; x++) {
      const offset = (y * info.width + x) * info.channels;
      red.push(data[offset]);
      green.push(data[offset + 1]);
      blue.push(data[offset + 2]);
    }
  }

  return {
    r: median(red),
    g: median(green),
    b: median(blue)
  };
}

function acceptsRGB(r, g, b, reference) {
  return rgbDistance(r, g, b, reference) <= RGB_DISTANCE_MAX;
}

module.exports = {
  REFERENCE_START,
  REFERENCE_END,
  RGB_DISTANCE_MAX,
  referenceBounds,
  rgbDistance,
  getReference,
  acceptsRGB
};
