"use strict";

const sharp = require("sharp");
const ort = require("onnxruntime-node");

const INPUT_SIZE = 640;

async function preprocessTile(inputPath, tile, page) {
  const { data } = await sharp(inputPath)
    .extract({
      left: 0,
      top: tile.top,
      width: page.width,
      height: tile.height
    })
    .resize(INPUT_SIZE, INPUT_SIZE, {
      fit: "contain",
      background: { r: 0, g: 0, b: 0 }
    })
    .removeAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

  const tensorData = new Float32Array(3 * INPUT_SIZE * INPUT_SIZE);
  const plane = INPUT_SIZE * INPUT_SIZE;

  for (let y = 0; y < INPUT_SIZE; y++) {
    for (let x = 0; x < INPUT_SIZE; x++) {
      const source = (y * INPUT_SIZE + x) * 3;
      const destination = y * INPUT_SIZE + x;

      tensorData[destination] = data[source] / 255;
      tensorData[plane + destination] = data[source + 1] / 255;
      tensorData[2 * plane + destination] = data[source + 2] / 255;
    }
  }

  return {
    images: new ort.Tensor(
      "float32",
      tensorData,
      [1, 3, INPUT_SIZE, INPUT_SIZE]
    ),
    orig_target_sizes: new ort.Tensor(
      "int64",
      BigInt64Array.from([BigInt(tile.height), BigInt(page.width)]),
      [1, 2]
    )
  };
}

module.exports = { INPUT_SIZE, preprocessTile };
