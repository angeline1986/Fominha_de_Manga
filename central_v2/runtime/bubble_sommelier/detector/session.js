"use strict";

const ort = require("onnxruntime-node");

async function createSession(modelPath) {
  return ort.InferenceSession.create(modelPath);
}

module.exports = { createSession };
