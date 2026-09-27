import { connectLevel1 } from "/_app/auto_merge/controller.js";
import { createLevel1Store } from "/_app/state/auto_merge.js";
import { createLevel1View } from "/processamento/auto_merge/consulta.js";
import { createLevel1Execution } from "/processamento/auto_merge/execution.js";

export function render(container) {
  const store = createLevel1Store();
  let execution;
  const view = createLevel1View({ onExecute: (chapters) => execution.execute(chapters) });
  container.replaceChildren(view.element);
  const unsubscribe = store.subscribe(view.update);
  const controller = connectLevel1(store);
  execution = createLevel1Execution({
    onStatus: view.setExecution,
    onComplete: async () => {
      view.clearSelection();
      await controller.refresh();
    },
  });
  return () => {
    execution.dispose();
    controller.dispose();
    unsubscribe();
    view.dispose();
  };
}
