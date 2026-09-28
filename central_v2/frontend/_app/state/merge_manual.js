let selection = null;

export function setMergeManualSelection(value) {
  selection = value ? { ...value } : null;
}

export function getMergeManualSelection() {
  return selection ? { ...selection } : null;
}
