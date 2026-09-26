import { mountShell } from "/_shell/shell.js";

const root = document.querySelector("#app");

if (!root) {
  throw new Error("Elemento raiz #app não encontrado.");
}

mountShell(root);
