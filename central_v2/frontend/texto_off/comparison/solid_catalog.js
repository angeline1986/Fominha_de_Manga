// Stage 05 is read-only. Keep the shared viewer but disable residue editing.
export function createSolidCatalog() {
  const element = document.createElement("aside");
  element.hidden = true;
  return {
    element,
    render() {}, setPages() {}, setPage() {},
    draftOccurrenceCount() { return 0; },
    toggle() {}, dispose() { element.remove(); },
  };
}
