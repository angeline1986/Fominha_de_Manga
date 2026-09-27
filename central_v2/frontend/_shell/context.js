import { changeManga, changeProvider } from "/_app/context/context_controller.js";
import { getContext, subscribeContext } from "/_app/state/context.js";
import { createContextSelector } from "/_shell/context_selector.js";

export function mountContext(container) {
  function render(context) {
    container.replaceChildren(createContextSelector(context, {
      onProviderChange: changeProvider,
      async onMangaChange(manga) {
        try {
          await changeManga(manga);
        } catch (error) {
          console.error("[Central V2] Falha ao carregar estado da obra.", error);
        }
      },
    }));
  }

  render(getContext());
  return subscribeContext(render);
}
