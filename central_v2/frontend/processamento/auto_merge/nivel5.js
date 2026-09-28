import { connectLevel5 } from "/_app/auto_merge/level5_controller.js";
import { createLevel5Store } from "/_app/state/auto_merge_level5.js";
import { createLevel5View } from "/processamento/auto_merge/consulta_nivel5.js";
import { createLevel5Execution } from "/processamento/auto_merge/execucao_nivel5.js";

export function render(container) {
  const store = createLevel5Store();
  let execution;
  const view = createLevel5View({ onExecute: (chapters) => execution.execute(chapters) });
  container.replaceChildren(view.element);
  const unsubscribe = store.subscribe(view.update);
  const controller = connectLevel5(store);
  execution = createLevel5Execution({ onStatus: view.setExecution, onComplete: async () => {
    view.clearSelection(); await controller.refresh();
  } });
  return () => { execution.dispose(); controller.dispose(); unsubscribe(); view.dispose(); };
}
