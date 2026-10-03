"use strict";

const { greedyNms } = require("./nms");

const PROFILES = Object.freeze({
  poc_a_v1: Object.freeze({
    labelsBeforeNms: Object.freeze([0]),
    labelsAfterNms: null,
    sortAfterNms: false
  }),
  poc_b_v1: Object.freeze({
    labelsBeforeNms: Object.freeze([0, 1]),
    labelsAfterNms: Object.freeze([0]),
    sortAfterNms: true
  })
});

function applyStrategy(rawDetections, profileId) {
  const profile = PROFILES[profileId];
  if (!profile) {
    throw new Error(`Perfil de detecção desconhecido: ${profileId}`);
  }

  const selected = rawDetections.filter(detection =>
    profile.labelsBeforeNms.includes(detection.label)
  );
  const afterNms = greedyNms(selected);
  let finalDetections = profile.labelsAfterNms
    ? afterNms.filter(detection => profile.labelsAfterNms.includes(detection.label))
    : afterNms;

  if (profile.sortAfterNms) {
    finalDetections = [...finalDetections].sort((a, b) =>
      a.bbox.y1 - b.bbox.y1 ||
      a.bbox.x1 - b.bbox.x1
    );
  }

  return {
    profile_id: profileId,
    counts: {
      input: rawDetections.length,
      after_initial_label_selection: selected.length,
      after_nms: afterNms.length,
      final: finalDetections.length
    },
    detections: finalDetections
  };
}

module.exports = { PROFILES, applyStrategy };
