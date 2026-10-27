/** Keeps the Original first and sorts visible results by execution time. */
export function connectCardOrder(root) {
  const container = root.querySelector(".lab-cards");
  const names = ["degrade", "estilizado", "gradiente_suave", "solidos"];
  const cards = new Map(names.map((name) => [name,
    container.querySelector(`[data-lab-card="${name}"]`)]));
  const completed = new Map();
  let pageKey = "", sequence = 0;

  function draw() {
    const ordered = [...names].sort((left, right) => {
      const a = completed.get(left), b = completed.get(right);
      if (a && b) return a.time - b.time || a.sequence - b.sequence;
      if (a || b) return a ? -1 : 1;
      return names.indexOf(left) - names.indexOf(right);
    });
    ordered.forEach((name) => container.append(cards.get(name)));
  }
  return {
    setPage(key) {
      if (key === pageKey) return;
      pageKey = key;
      completed.clear();
      draw();
    },
    complete(name, time) {
      if (!cards.has(name)) return;
      completed.set(name, { time: Number.isFinite(time) ? time : Date.now(),
        sequence: ++sequence });
      draw();
    },
    clear(name) {
      if (completed.delete(name)) draw();
    },
  };
}
