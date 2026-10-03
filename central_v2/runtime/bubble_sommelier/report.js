"use strict";

const crypto = require("crypto");
const fs = require("fs/promises");
const path = require("path");

function sha256File(filePath) {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash("sha256");
    const stream = require("fs").createReadStream(filePath);
    stream.on("error", reject);
    stream.on("data", chunk => hash.update(chunk));
    stream.on("end", () => resolve(hash.digest("hex")));
  });
}

async function prepareOutputDirectory(outputDir) {
  let stat;
  try {
    stat = await fs.stat(outputDir);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }

  if (stat && !stat.isDirectory()) {
    throw new Error(`outputDir não é um diretório: ${outputDir}`);
  }
  if (stat) {
    const entries = await fs.readdir(outputDir);
    if (entries.length) {
      throw new Error(`outputDir precisa estar vazio para uma nova execução: ${outputDir}`);
    }
  } else {
    await fs.mkdir(outputDir, { recursive: true });
  }

  await fs.mkdir(path.join(outputDir, "crops"));
}

async function persistCrop(outputDir, { identity, png, sha256 }) {
  if (typeof identity !== "string" || !identity || path.basename(identity) !== identity) {
    throw new Error(`Identidade de crop inválida: ${identity}`);
  }
  if (!Buffer.isBuffer(png)) throw new TypeError(`Crop ${identity} não contém um Buffer PNG`);

  const relativePath = path.posix.join("crops", `${identity}.png`);
  const destination = path.join(outputDir, "crops", `${identity}.png`);
  await fs.writeFile(destination, png, { flag: "wx" });

  const persistedSha256 = await sha256File(destination);
  if (sha256 && persistedSha256 !== sha256) {
    throw new Error(`SHA-256 do crop persistido diverge do pipeline: ${identity}`);
  }

  return { path: relativePath, sha256: persistedSha256 };
}

function buildReport({ profileId, modelPath, modelSha256, inputDir, pages, pipelineResult, persistedCrops }) {
  const reportPages = pipelineResult.pages.map(page => ({
    ...page,
    bubbles: page.bubbles.map(bubble => {
      const persisted = persistedCrops.get(bubble.identity);
      if (!persisted) throw new Error(`Crop não persistido: ${bubble.identity}`);
      if (persisted.sha256 !== bubble.crop.sha256) {
        throw new Error(`Hash do crop no report diverge do pipeline: ${bubble.identity}`);
      }
      return {
        ...bubble,
        crop: { ...bubble.crop, path: persisted.path }
      };
    })
  }));

  return {
    schema: "bubble_sommelier_run_v1",
    status: "completed",
    profile_id: profileId,
    model: { path: modelPath, sha256: modelSha256 },
    input: {
      directory: inputDir,
      pages: pages.map(page => ({ id: page.id, file: page.file, path: page.path, sha256: page.sha256 }))
    },
    checkpoints: pipelineResult.checkpoints,
    pages: reportPages
  };
}

async function writeReportAtomic(outputDir, report) {
  const reportPath = path.join(outputDir, "report.json");
  const temporaryPath = path.join(
    outputDir,
    `.report.${process.pid}.${crypto.randomUUID()}.tmp`
  );

  try {
    await fs.writeFile(temporaryPath, `${JSON.stringify(report, null, 2)}\n`, { flag: "wx" });
    await fs.rename(temporaryPath, reportPath);
  } catch (error) {
    await fs.unlink(temporaryPath).catch(unlinkError => {
      if (unlinkError.code !== "ENOENT") throw unlinkError;
    });
    throw error;
  }

  return reportPath;
}

module.exports = {
  sha256File,
  prepareOutputDirectory,
  persistCrop,
  buildReport,
  writeReportAtomic
};
