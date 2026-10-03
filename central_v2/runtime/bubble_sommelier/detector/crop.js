"use strict";

const sharp = require("sharp");

function cropGeometry(detection, profileId, page) {
  const { x1, y1, x2, y2 } = detection.bbox;

  if (profileId === "poc_a_v1") {
    const left = Math.floor(x1);
    const top = Math.floor(y1);
    const width = Math.min(
      page.width - left,
      Math.max(1, Math.ceil(x2) - left)
    );
    const height = Math.min(
      page.height - top,
      Math.max(1, Math.ceil(y2) - top)
    );

    return {
      profile_id: profileId,
      left,
      top,
      right: left + width,
      bottom: top + height,
      width,
      height
    };
  }

  if (profileId === "poc_b_v1") {
    const left = Math.round(x1);
    const top = Math.round(y1);
    const right = Math.round(x2);
    const bottom = Math.round(y2);
    const width = Math.max(1, right - left);
    const height = Math.max(1, bottom - top);

    return {
      profile_id: profileId,
      left,
      top,
      right: left + width,
      bottom: top + height,
      width,
      height
    };
  }

  throw new Error(`Perfil de crop desconhecido: ${profileId}`);
}

async function cropRegion(inputPath, detection, profileId) {
  const page = await sharp(inputPath).metadata();
  const geometry = cropGeometry(detection, profileId, page);
  const png = await sharp(inputPath)
    .extract({
      left: geometry.left,
      top: geometry.top,
      width: geometry.width,
      height: geometry.height
    })
    .png()
    .toBuffer();

  return { geometry, png };
}

module.exports = { cropGeometry, cropRegion };
