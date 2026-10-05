"use strict";

function freezeCopy(value) {
  if (Array.isArray(value)) return Object.freeze(value.map(freezeCopy));
  if (!value || typeof value !== "object") return value;
  return Object.freeze(Object.fromEntries(
    Object.entries(value).map(([key, item]) => [key, freezeCopy(item)])
  ));
}

function createReadOnlyContext(context) {
  return freezeCopy(context);
}

function analyzeVisual(cropPng, context) {
  if (!Buffer.isBuffer(cropPng)) throw new TypeError("crop.png precisa ser um Buffer PNG.");
  if (!context || typeof context !== "object") throw new TypeError("Contexto visual inválido.");
  return { status: "not_analyzed" };
}

async function runOptionalVisualAnalysis({ cropPng, analyzer, context }) {
  let result;
  let failure;
  try {
    result = await (analyzer || analyzeVisual)(cropPng, createReadOnlyContext(context));
    if (!result || typeof result !== "object" || Array.isArray(result)
        || result.status !== "not_analyzed" || Object.keys(result).length !== 1) {
      throw new TypeError("A extensão visual retornou um resultado fora do contrato neutro.");
    }
  } catch (error) {
    failure = error;
  }

  if (failure) {
    result = {
      status: "failed",
      error: { name: failure.name || "Error", message: failure.message || String(failure) }
    };
  }
  return result;
}

module.exports = { analyzeVisual, createReadOnlyContext, runOptionalVisualAnalysis };
