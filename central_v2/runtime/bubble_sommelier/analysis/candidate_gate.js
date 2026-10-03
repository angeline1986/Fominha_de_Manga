"use strict";

const MIN_COVERAGE = 0.75;
const MIN_LUMA_MAD = 1.0;

function isCandidate(metrics) {
  return metrics.coverage >= MIN_COVERAGE &&
    metrics.lumaMad > MIN_LUMA_MAD;
}

module.exports = { MIN_COVERAGE, MIN_LUMA_MAD, isCandidate };
