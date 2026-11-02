const LOAD_TIMEOUT_MS = 4000;

function waitForStylesheet(link) {
  if (link.sheet) return Promise.resolve(true);
  return new Promise((resolve) => {
    let timer;
    const finish = () => {
      clearTimeout(timer);
      link.removeEventListener("load", finish);
      link.removeEventListener("error", finish);
      resolve(Boolean(link.sheet));
    };
    link.addEventListener("load", finish);
    link.addEventListener("error", finish);
    timer = setTimeout(finish, LOAD_TIMEOUT_MS);
    if (link.sheet) finish();
  });
}

export async function ensureStylesheets() {
  const links = [...document.querySelectorAll('head link[rel="stylesheet"]')];
  const loaded = await Promise.all(links.map(waitForStylesheet));
  const failed = links.filter((_link, index) => !loaded[index]);
  if (!failed.length) return;

  const replacements = failed.map((link) => {
    const replacement = link.cloneNode();
    const pending = waitForStylesheet(replacement);
    link.replaceWith(replacement);
    return { replacement, pending };
  });
  const retried = await Promise.all(replacements.map(({ pending }) => pending));
  if (retried.some((ok) => !ok)) {
    throw new Error("Não foi possível carregar os estilos da Central. Tente novamente.");
  }
}
