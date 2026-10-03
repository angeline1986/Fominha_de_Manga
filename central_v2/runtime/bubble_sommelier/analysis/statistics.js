"use strict";

function median(values) {
  if (!values.length) return null;

  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);

  return sorted.length % 2
    ? sorted[middle]
    : (sorted[middle - 1] + sorted[middle]) / 2;
}

function mad(values) {
  const center = median(values);
  if (center === null) return null;

  return median(values.map(value => Math.abs(value - center)));
}

module.exports = { median, mad };
