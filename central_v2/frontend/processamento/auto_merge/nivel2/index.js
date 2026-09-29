import { connectLevel2 } from "/_app/auto_merge/level2_controller.js";
import { createLevel2Store } from "/_app/state/auto_merge_level2.js";
import { createLevel2View } from "/processamento/auto_merge/nivel2/view.js";
import { createLevel2Execution } from "/processamento/auto_merge/nivel2/execution.js";

export function render(container) {
  const store = createLevel2Store();
  let execution;
  const view = createLevel2View({ onExecute: (chapters) => execution.execute(chapters) });
  container.replaceChildren(view.element);
  const unsubscribe = store.subscribe(view.update);
  const controller = connectLevel2(store);
  execution = createLevel2Execution({
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
