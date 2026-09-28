let selection = null;

export function setBalanceSelection(value) {
  selection = value ? { ...value, merges: [...(value.merges || [])] } : null;
}

export function getBalanceSelection() {
  return selection ? { ...selection, merges: [...selection.merges] } : null;
}

export function clearBalanceSelection() {
  selection = null;
}
