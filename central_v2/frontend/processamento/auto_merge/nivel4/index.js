import { connectLevel4 } from "/_app/auto_merge/level4_controller.js";
import { createLevel4Store } from "/_app/state/auto_merge_level4.js";
import { createLevel4View } from "/processamento/auto_merge/nivel4/view.js";
import { createLevel4Execution } from "/processamento/auto_merge/nivel4/execution.js";

export function render(container) {
  const store = createLevel4Store();
  let execution;
  const view = createLevel4View({ onExecute: (chapters) => execution.execute(chapters) });
  container.replaceChildren(view.element);
  const unsubscribe = store.subscribe(view.update);
  const controller = connectLevel4(store);
  execution = createLevel4Execution({ onStatus: view.setExecution, onComplete: async () => {
    view.clearSelection(); await controller.refresh();
  } });
  return () => { execution.dispose(); controller.dispose(); unsubscribe(); view.dispose(); };
}
