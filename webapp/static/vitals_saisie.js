/**
 * Modale de saisie infirmière des constantes (services hors monitoring continu).
 */
(function () {
  "use strict";

  const root = document.querySelector("[data-fiche-moniteur]");
  if (!root || root.getAttribute("data-monitoring-continu") === "1") return;

  const dialog = document.querySelector("[data-vitals-saisie-dialog]");
  const form = document.querySelector("[data-vitals-saisie-form]");
  const openBtn = document.querySelector("[data-open-saisie-vitals]");
  const submitBtn = document.querySelector("[data-saisie-submit]");
  const errEl = document.querySelector("[data-saisie-error]");
  const sejourId = root.getAttribute("data-sejour-id");
  if (!dialog || !form || !openBtn || !sejourId) return;

  function setError(msg) {
    if (!errEl) return;
    if (!msg) {
      errEl.hidden = true;
      errEl.textContent = "";
      return;
    }
    errEl.hidden = false;
    errEl.textContent = msg;
  }

  function defaultHorodatage() {
    const input = form.querySelector("[data-saisie-horodatage]");
    if (!input) return;
    const d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    input.value = d.toISOString().slice(0, 16);
  }

  function openDialog() {
    setError("");
    defaultHorodatage();
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
    const first = form.querySelector("input:not([type=hidden])");
    first?.focus();
  }

  function closeDialog() {
    if (typeof dialog.close === "function") dialog.close();
    else dialog.removeAttribute("open");
  }

  openBtn.addEventListener("click", openDialog);

  form.addEventListener("submit", (ev) => {
    /* method=dialog : Annuler / Fermer */
    if (ev.submitter && ev.submitter.value === "cancel") {
      setError("");
    }
  });

  submitBtn?.addEventListener("click", async () => {
    setError("");
    const fd = new FormData(form);
    const payload = {};
    fd.forEach((v, k) => {
      if (v !== "" && v != null) payload[k] = v;
    });
    if (payload.Horodatage) {
      payload.Horodatage = String(payload.Horodatage).replace("T", " ");
    }
    submitBtn.disabled = true;
    try {
      const res = await fetch(
        "/api/sejours/" + encodeURIComponent(sejourId) + "/constantes/saisie",
        {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          credentials: "same-origin",
          body: JSON.stringify(payload),
        }
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || "Enregistrement impossible");
      }
      closeDialog();
      window.location.reload();
    } catch (e) {
      setError(e.message || "Erreur réseau");
    } finally {
      submitBtn.disabled = false;
    }
  });

  dialog.addEventListener("cancel", () => setError(""));
})();
