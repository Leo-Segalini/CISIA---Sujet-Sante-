/**
 * Historique constantes — afficher / masquer les mesures exclues.
 */
(function () {
  "use strict";

  const root = document.querySelector("[data-vitals-history]");
  if (!root) return;

  const toggle = root.querySelector("[data-vitals-show-excluded]");
  const excludedRows = root.querySelectorAll('[data-excluded="true"]');

  function apply() {
    const show = Boolean(toggle?.checked);
    excludedRows.forEach((row) => {
      row.hidden = !show;
    });
  }

  toggle?.addEventListener("change", apply);
  apply();
})();
