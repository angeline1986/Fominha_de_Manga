import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { test } from "node:test";

const require = createRequire(import.meta.url);
const Module = require("node:module");
const runtime = new URL("../../central_v2/runtime/bubble_sommelier/", import.meta.url);
const modulePath = (name) => require.resolve(new URL(name, runtime).pathname);

function loadWithMocks(file, mocks) {
  const target = modulePath(file);
  delete require.cache[target];
  const originalLoad = Module._load;
  Module._load = function (request, parent, isMain) {
    if (parent?.filename === target && Object.hasOwn(mocks, request)) return mocks[request];
    return originalLoad.call(this, request, parent, isMain);
  };
  try { return require(target); } finally { Module._load = originalLoad; }
}

function pipelineFixture(count = 1) {
  const generated = [];
  const detections = Array.from({ length: count }, (_, index) => ({
    label: 0, confidence: 0.91, bbox: { x1: index * 10, y1: 2, x2: index * 10 + 8, y2: 9 },
    tile_id: "tile-1"
  }));
  const strategyCounts = {
    input: count, after_initial_label_selection: count, after_nms: count, final: count
  };
  const mocks = {
    "./detector/session": { createSession: async () => ({ release() {} }) },
    "./detector/infer": { inferPage: async () => ({
      page: { width: 100, height: 80 }, tiles: [{ tile_id: "tile-1" }], detections
    }) },
    "./detector/strategies": { PROFILES: { poc_a_v1: {} }, applyStrategy: () => ({
      counts: strategyCounts, detections
    }) },
    "./detector/crop": { cropRegion: async (_path, detection) => {
      const png = Buffer.from(`encoded-png-${detection.bbox.x1}`);
      const geometry = { left: detection.bbox.x1, top: 2, width: 8, height: 7 };
      generated.push({ png, geometry });
      return { png, geometry };
    } },
    "./analysis/metrics": { analyzeCrop: async () => ({
      coverage: 0.8, validCells: 1, lumaMedian: 240, lumaMad: 2,
      rgbMad: { r: 1, g: 2, b: 3 }, reference: { r: 250, g: 250, b: 250 },
      cells: [{ gx: 0, gy: 0, r: 240, g: 241, b: 242, coverage: 0.8 }]
    }) },
    "./analysis/candidate_gate": { isCandidate: (metrics) => metrics.coverage >= 0.75 && metrics.lumaMad > 1 }
  };
  const { runPipeline } = loadWithMocks("pipeline.js", mocks);
  const inputPage = { id: "page-001.png", path: "/fixture/page-001.png", sha256: "input-hash" };
  return { generated, inputPage, runPipeline };
}

async function runFixture(options = {}, count = 1) {
  const fixture = pipelineFixture(count);
  const persisted = [];
  const result = await fixture.runPipeline({
    pages: [fixture.inputPage], profile: "poc_a_v1", modelPath: "/fixture/model.onnx",
    onCrop: async (crop) => persisted.push(Buffer.from(crop.png)),
    ...options
  });
  return { ...fixture, persisted, result };
}

test("visual extension is default-off and preserves the baseline bubble schema", async () => {
  const fixture = pipelineFixture();
  let optionalModuleRequested = false;
  const originalLoad = Module._load;
  Module._load = function (request, parent, isMain) {
    if (parent?.filename === modulePath("pipeline.js") && request === "./analysis/visual_analysis") {
      optionalModuleRequested = true;
      throw new Error("optional module unavailable");
    }
    return originalLoad.call(this, request, parent, isMain);
  };
  let result;
  try {
    result = await fixture.runPipeline({
      pages: [fixture.inputPage], profile: "poc_a_v1", modelPath: "/fixture/model.onnx"
    });
  } finally {
    Module._load = originalLoad;
  }
  const bubble = result.pages[0].bubbles[0];
  assert.equal(bubble.candidate, true);
  assert.equal(optionalModuleRequested, false);
  assert.deepEqual(result.checkpoints, {
    inference: { pages: 1, tiles: 1, rawDetections: 1, rawLabels: { "0": 1 } },
    strategy: {
      input: 1, afterInitialLabelSelection: 1, afterNms: 1, finalDetections: 1,
      postNmsBeforeFinalLabelSelection: 1
    },
    result: {
      pages: 1, tiles: 1, rawDetections: 1, afterInitialLabelSelection: 1,
      afterNms: 1, finalDetections: 1, crops: 1, coverageGe075: 1, candidates: 1
    }
  });
  assert.deepEqual(bubble.metrics, {
    coverage: 0.8, validCells: 1, lumaMedian: 240, lumaMad: 2,
    rgbMad: { r: 1, g: 2, b: 3 }, reference: { r: 250, g: 250, b: 250 }
  });
  assert.equal(Object.hasOwn(bubble, "visual_analysis"), false);
  assert.deepEqual(Object.keys(bubble), [
    "identity", "page_id", "bubble_index", "label", "confidence", "bbox", "tile_id",
    "profile_id", "crop", "metrics", "candidate"
  ]);
});

test("an unavailable optional module is reported without failing the primary analysis", async () => {
  const fixture = pipelineFixture();
  const originalLoad = Module._load;
  Module._load = function (request, parent, isMain) {
    if (parent?.filename === modulePath("pipeline.js") && request === "./analysis/visual_analysis") {
      throw new Error("visual module unavailable");
    }
    return originalLoad.call(this, request, parent, isMain);
  };
  let result;
  try {
    result = await fixture.runPipeline({
      pages: [fixture.inputPage], profile: "poc_a_v1", modelPath: "/fixture/model.onnx",
      visualAnalysisEnabled: true
    });
  } finally {
    Module._load = originalLoad;
  }
  const bubble = result.pages[0].bubbles[0];
  assert.equal(bubble.candidate, true);
  assert.deepEqual(bubble.visual_analysis, {
    status: "failed", error: { name: "Error", message: "visual module unavailable" }
  });
});

test("opt-in receives a defensive PNG copy and frozen real context without disk reload", async () => {
  let received;
  const execution = await runFixture({ visualAnalysisEnabled: true, visualAnalyzer: (png, context) => {
    received = { png, context };
    return { status: "not_analyzed" };
  } });
  assert.notStrictEqual(received.png, execution.generated[0].png);
  assert.deepEqual(received.png, execution.generated[0].png);
  assert.deepEqual(Object.keys(received.context).sort(), [
    "candidate", "cells", "detection", "geometry", "identity", "metrics", "page_id", "profile_id"
  ]);
  assert.equal(received.context.identity, "page-001-bubble-01");
  assert.equal(received.context.candidate, true);
  assert.equal(Object.isFrozen(received.context), true);
  assert.equal(Object.isFrozen(received.context.detection.bbox), true);
  assert.equal(Object.isFrozen(received.context.metrics), true);
  assert.equal(Object.isFrozen(received.context.cells[0]), true);
  assert.deepEqual(execution.result.pages[0].bubbles[0].visual_analysis, { status: "not_analyzed" });
  assert.deepEqual(execution.persisted[0], execution.generated[0].png);
});

test("visual output is additive and leaves primary decision, metrics and crop identity unchanged", async () => {
  const baseline = await runFixture();
  const enabled = await runFixture({ visualAnalysisEnabled: true });
  const baselineBubble = baseline.result.pages[0].bubbles[0];
  const enabledBubble = { ...enabled.result.pages[0].bubbles[0] };
  delete enabledBubble.visual_analysis;
  assert.deepEqual(enabledBubble, baselineBubble);
  assert.deepEqual(enabled.result.checkpoints, baseline.result.checkpoints);
});

test("extension exceptions are recorded locally and do not stop later bubbles", async () => {
  const calls = [];
  const execution = await runFixture({ visualAnalysisEnabled: true, visualAnalyzer: (_png, context) => {
    calls.push(context.identity);
    if (calls.length === 1) throw new Error("visual extension fixture failure");
    return { status: "not_analyzed" };
  } }, 2);
  const bubbles = execution.result.pages[0].bubbles;
  assert.equal(calls.length, 2);
  assert.deepEqual(bubbles.map((bubble) => bubble.candidate), [true, true]);
  assert.deepEqual(bubbles[0].visual_analysis, {
    status: "failed", error: { name: "Error", message: "visual extension fixture failure" }
  });
  assert.deepEqual(bubbles[1].visual_analysis, { status: "not_analyzed" });
});

test("mutating the extension copy leaves original, persisted crop, hash and candidates intact", async () => {
  const receivedBuffers = [];
  const originalBytes = [];
  const execution = await runFixture({ visualAnalysisEnabled: true, visualAnalyzer: (png) => {
    const index = receivedBuffers.length;
    receivedBuffers.push(png);
    originalBytes.push(Buffer.from(png));
    png[0] ^= 1;
    return { status: "not_analyzed" };
  } }, 2);
  const bubbles = execution.result.pages[0].bubbles;
  const crypto = require("node:crypto");
  assert.equal(receivedBuffers.length, 2);
  for (let index = 0; index < receivedBuffers.length; index++) {
    assert.notStrictEqual(receivedBuffers[index], execution.generated[index].png);
    assert.deepEqual(originalBytes[index], execution.generated[index].png);
    assert.notDeepEqual(receivedBuffers[index], originalBytes[index]);
    assert.deepEqual(execution.generated[index].png, execution.persisted[index]);
    assert.equal(bubbles[index].crop.sha256,
      crypto.createHash("sha256").update(execution.persisted[index]).digest("hex"));
    assert.equal(bubbles[index].candidate, true);
    assert.deepEqual(bubbles[index].visual_analysis, { status: "not_analyzed" });
  }
  assert.equal(bubbles.length, 2);
});

test("CLI opt-in is explicit and defaults off", () => {
  const { parseArguments } = require(modulePath("cli.js"));
  const required = ["--input", "/input", "--output", "/output", "--model", "/model", "--profile", "poc_a_v1"];
  assert.equal(parseArguments(required).visualAnalysisEnabled, false);
  assert.equal(parseArguments([...required, "--visual-analysis"]).visualAnalysisEnabled, true);
  assert.throws(() => parseArguments([...required, "--visual-analysis", "--visual-analysis"]), /duplicado/);
});

test("runner forwards the explicit opt-in and keeps its default off", async () => {
  let pipelineOptions;
  const mocks = {
    "./detector/strategies": { PROFILES: { poc_a_v1: {} } },
    "./pipeline": { runPipeline: async (options) => {
      pipelineOptions = options;
      return { pages: [], checkpoints: { result: {} } };
    } },
    "./input": { discoverPages: async () => [{ id: "page.png", file: "page.png", path: "/input/page.png", sha256: "page-hash" }] },
    "./report": {
      sha256File: async () => "model-hash", prepareOutputDirectory: async () => {},
      persistCrop: async () => ({ path: "crops/x.png", sha256: "crop-hash" }),
      buildReport: ({ pipelineResult }) => ({ ...pipelineResult, status: "completed" }),
      writeReportAtomic: async () => "/output/report.json"
    }
  };
  const { runBubbleSommelier } = loadWithMocks("runner.js", mocks);
  const options = { inputDir: "/input", outputDir: "/output", modelPath: "/model", profileId: "poc_a_v1" };
  await runBubbleSommelier(options);
  assert.equal(pipelineOptions.visualAnalysisEnabled, false);
  await runBubbleSommelier({ ...options, visualAnalysisEnabled: true });
  assert.equal(pipelineOptions.visualAnalysisEnabled, true);
});
