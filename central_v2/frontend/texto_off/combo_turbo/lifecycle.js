import { getContext, subscribeContext } from "/_app/state/context.js";
import { subscribeCleanerInvalidation } from "/_app/state/cleaner_revision.js";
import { jobStorageKey } from "/texto_off/combo_turbo/jobs.js";

export function watchComboChanges(load) {
  const unsubscribeContext = subscribeContext(() => load(false));
  const unsubscribeInvalidation = subscribeCleanerInvalidation((provider, manga) => {
    const context = getContext();
    if (provider === context.provider && manga === context.manga) load(true);
  });
  const onStorage = (event) => {
    const context = getContext();
    if (event.key === jobStorageKey(context.provider, context.manga)) load(true);
  };
  window.addEventListener("storage", onStorage);
  return () => {
    unsubscribeContext(); unsubscribeInvalidation();
    window.removeEventListener("storage", onStorage);
  };
}
