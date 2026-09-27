import { connectLevel1 } from "/_app/auto_merge/controller.js";
import { createLevel1Store } from "/_app/state/auto_merge.js";
import { createLevel1View } from "/processamento/auto_merge/consulta.js";

export function render(container) {
  const store = createLevel1Store();
  const view = createLevel1View();
  container.replaceChildren(view.element);
  const unsubscribe = store.subscribe(view.update);
  const controller = connectLevel1(store);
  return () => {
    controller.dispose();
    unsubscribe();
    view.dispose();
  };
}
