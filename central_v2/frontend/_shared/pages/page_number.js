export function isOddPage(file) {
  return Number(file.match(/page-(\d+)/i)?.[1] || 0) % 2 === 1;
}
