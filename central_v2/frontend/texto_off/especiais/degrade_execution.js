import { createSpecialTreatmentExecution } from "/texto_off/especiais/special_treatment_execution.js";

export function createDegradeExecution(options) {
  return createSpecialTreatmentExecution({ ...options, treatment: "degrade",
    title: "tratamento Degradê", retryTitle: "o tratamento Degradê" });
}
