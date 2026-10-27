// Carrega capitulos e paginas reais da obra ativa, sem processar imagens.
import { getContext, subscribeContext } from "/_app/state/context.js";

export function connectLaboratorio(root) {
  let controller = null;
  let serial = 0;
  let disposed = false;
  let source = "glass";

  async function load() {
    const id = ++serial;
    controller?.abort();
    controller = new AbortController();
    const { provider, manga } = getContext();
    const send = (chapters) => root.dispatchEvent(new CustomEvent(
      "laboratorio:pages", { detail: { chapters } },
    ));
    if (!provider || !manga) { send({}); return; }
    const query = new URLSearchParams({ provider, manga, source });
    if (source === "merge") query.set("check_other", "1");
    try {
      const response = await fetch(`/api/textoff/laboratorio/pages?${query}`, {
        signal: controller.signal, cache: "no-store",
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      if (!disposed && id === serial) send(payload.chapters || {});
    } catch (error) {
      if (error.name !== "AbortError" && !disposed && id === serial) {
        console.error("Laboratório: erro ao carregar páginas:", error);
        send({});
      }
    }
  }

  const onSource = (event) => {
    const next = event.detail?.source;
    if (!["img", "merge", "glass", "check"].includes(next)) return;
    source = next;
    load();
  };
  root.addEventListener("laboratorio:source", onSource);
  const unsubscribe = subscribeContext(load);
  load();
  return () => {
    disposed = true;
    serial++;
    controller?.abort();
    unsubscribe();
    root.removeEventListener("laboratorio:source", onSource);
  };
}
