import { getContext } from "/_app/state/context.js";
import { positionPreview, previewNearElement } from "/texto_off/laboratorio/preview_position.js";

/** Explorador experimental de arquivos usados para selecionar páginas. */
export function connectFileExplorer(root, navigation) {
  const dialog = root.querySelector("[data-lab-explorer]");
  const pathLabel = root.querySelector("[data-lab-explorer-path]");
  const list = root.querySelector("[data-lab-explorer-list]");
  const explorerButton = root.querySelector("[data-lab-explore]");
  const preview = document.createElement("aside");
  preview.className = "lab-explorer-hover-preview";
  preview.hidden = true;
  const previewImage = document.createElement("img");
  previewImage.alt = "Prévia do arquivo";
  preview.append(previewImage);
  dialog.append(preview);
  let controller = null;
  let serial = 0;
  let browserPath = "";
  let pendingSelection = null;

  function hidePreview() {
    preview.hidden = true;
    previewImage.removeAttribute("src");
  }
  async function browse(path = "") {
    hidePreview();
    const { provider, manga } = getContext();
    if (!provider || !manga) { list.textContent = "Selecione uma obra."; return; }
    controller?.abort();
    controller = new AbortController();
    const id = ++serial;
    list.textContent = "Carregando arquivos...";
    const params = new URLSearchParams({ provider, manga, browse: "1", path });
    try {
      const response = await fetch(`/api/textoff/laboratorio/pages?${params}`, {
        signal: controller.signal, cache: "no-store",
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      if (id !== serial || !dialog.open) return;
      browserPath = payload.path;
      pathLabel.textContent = `${provider}/${manga}${browserPath ? `/${browserPath}` : ""}`;
      list.replaceChildren();
      if (browserPath) {
        const up = document.createElement("button");
        up.type = "button";
        up.className = "lab-explorer-item";
        up.textContent = "← Pasta anterior";
        up.addEventListener("click", () => browse(browserPath.split("/").slice(0, -1).join("/")));
        list.append(up);
      }
      for (const item of payload.entries) addEntry(item, provider, manga);
    } catch (error) {
      if (error.name !== "AbortError") list.textContent = error.message;
    }
  }
  function addEntry(item, provider, manga) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "lab-explorer-item";
    button.textContent = `${item.type === "directory" ? "📁" : "🖼"} ${item.name}`;
    button.addEventListener("click", () => {
      if (item.type === "directory") { browse(item.path); return; }
      const segments = item.path.split("/");
      const isImg = segments.length === 3 && segments[0] === "IMG";
      const isMerge = segments.length === 4 && segments[0] === "FLUXO_SECUNDARIO" && segments[1] === "02_MERGE";
      if (!isImg && !isMerge) return;
      const source = isImg ? "img" : "merge";
      const chapter = segments.at(-2), page = segments.at(-1);
      const choose = () => navigation.selectPage(chapter, page);
      if (source === navigation.getSelection().source) {
        choose();
        dialog.close();
      } else {
        navigation.setSource(source, false);
        pendingSelection = () => {
          root.removeEventListener("laboratorio:pages", pendingSelection);
          pendingSelection = null;
          choose();
          dialog.close();
        };
        root.addEventListener("laboratorio:pages", pendingSelection, { once: true });
        root.dispatchEvent(new CustomEvent("laboratorio:source", { detail: { source } }));
      }
    });
    if (item.type === "file") addPreviewHandlers(button, item, provider, manga);
    list.append(button);
  }
  function addPreviewHandlers(button, item, provider, manga) {
    const show = (event) => {
      if (event?.pointerType === "touch") return;
      const params = new URLSearchParams({ provider, manga, browse_image: "1", path: item.path });
      previewImage.src = `/api/textoff/laboratorio/pages/image?${params}`;
      preview.hidden = false;
      if (event?.clientX !== undefined) positionPreview(preview, event.clientX, event.clientY);
      else previewNearElement(preview, button);
    };
    button.addEventListener("pointerenter", show);
    button.addEventListener("pointermove", (event) => {
      if (!preview.hidden && event.pointerType !== "touch") positionPreview(preview, event.clientX, event.clientY);
    });
    button.addEventListener("focus", show);
    button.addEventListener("pointerleave", hidePreview);
    button.addEventListener("blur", hidePreview);
  }

  explorerButton.addEventListener("click", () => { dialog.showModal(); browse(""); });
  root.querySelector("[data-lab-explorer-close]").addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => { controller?.abort(); hidePreview(); });
  return {
    dispose() {
      serial++;
      controller?.abort();
      if (pendingSelection) root.removeEventListener("laboratorio:pages", pendingSelection);
      hidePreview();
      preview.remove();
      dialog.close();
    },
  };
}
