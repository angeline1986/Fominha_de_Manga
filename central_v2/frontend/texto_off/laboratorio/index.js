/** Ponto de entrada e composição dos módulos do Laboratório L3. */
import { connectLaboratorio } from "/texto_off/laboratorio/data_loader.js";
import { connectPageNavigation } from "/texto_off/laboratorio/page_navigation.js";
import { connectFileExplorer } from "/texto_off/laboratorio/file_explorer.js";
import { connectWorkspaceControls } from "/texto_off/laboratorio/workspace_controls.js";
import { connectTreatmentController } from "/texto_off/laboratorio/treatment_controller.js";
import { createLaboratorioView } from "/texto_off/laboratorio/view.js";
import { createJobProgress } from "/_shared/progress/progress.js";

export function render(container) {
  const view = createLaboratorioView(container);
  const { root } = view;
  const progress = createJobProgress("Laboratório");
  root.append(progress.element);
  const originalImage = document.createElement("img");
  const workspace = connectWorkspaceControls(root, originalImage);
  let treatments;
  const navigation = connectPageNavigation(root, {
    beforeDraw: () => treatments?.displayOriginal(),
    afterDraw: () => workspace.syncFocusNavigation(),
  });
  treatments = connectTreatmentController({ root, navigation, workspace, image: originalImage, progress });
  const explorer = connectFileExplorer(root, navigation);
  const disconnect = connectLaboratorio(root);
  navigation.draw();

  return () => {
    explorer.dispose();
    workspace.dispose();
    disconnect();
    treatments.dispose();
    progress.element.remove();
    navigation.dispose();
    view.dispose();
  };
}
