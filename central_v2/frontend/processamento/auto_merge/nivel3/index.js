import { connectLevel3 } from "/_app/auto_merge/level3_controller.js";
import { createLevel3Store } from "/_app/state/auto_merge_level3.js";
import { createLevel3View } from "/processamento/auto_merge/nivel3/view.js";
import { createLevel3Execution } from "/processamento/auto_merge/nivel3/execution.js";

export function render(container) {
  const store = createLevel3Store();
  let execution;
  const view = createLevel3View({ onExecute: (chapters) => execution.execute(chapters) });
  container.replaceChildren(view.element);
  const unsubscribe = store.subscribe(view.update);
  const controller = connectLevel3(store);
  execution = createLevel3Execution({
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
