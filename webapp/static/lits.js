/**
 * Page « Tous les lits » — recherche et filtres en AJAX.
 */
(function () {
  "use strict";

  const DEBOUNCE_MS = 320;
  const API_URL = "/api/lits";

  const root = document.querySelector("[data-lits-page]");
  if (!root) return;

  const form = document.getElementById("lits-filters");
  const searchInput = form?.querySelector("[data-lits-search]");
  const filterSelects = form ? [...form.querySelectorAll("[data-lits-filter]")] : [];
  const pageInput = form?.querySelector("[data-lits-page-input]");
  const resetBtn = form?.querySelector("[data-lits-reset]");
  const tbody = root.querySelector("[data-lits-tbody]");
  const tableWrap = root.querySelector("[data-lits-table-wrap]");
  const loadingEl = root.querySelector("[data-lits-loading]");
  const metaEl = root.querySelector("#lits-results-meta");
  const pageInfoEl = root.querySelector("[data-lits-page-info]");
  const prevBtn = root.querySelector("[data-lits-prev]");
  const nextBtn = root.querySelector("[data-lits-next]");
  const errorEl = root.querySelector("[data-lits-error]");

  let debounceTimer = null;
  let abortController = null;
  let activeRequestId = 0;
  let currentPage = parseInt(pageInput?.value || "1", 10) || 1;

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatAge(age) {
    if (age === null || age === undefined || Number.isNaN(Number(age))) return "—";
    return String(Math.round(Number(age)));
  }

  function readFilters() {
    const etageRaw = form?.elements.namedItem("etage")?.value ?? "";
    return {
      q: (searchInput?.value ?? "").trim(),
      etage: etageRaw === "" ? null : Number(etageRaw),
      service: form?.elements.namedItem("service")?.value ?? "",
      sexe: form?.elements.namedItem("sexe")?.value ?? "",
      page: currentPage,
    };
  }

  function hasActiveFilters() {
    const f = readFilters();
    return Boolean(f.q || f.etage !== null || f.service || f.sexe);
  }

  function updateResetVisibility() {
    if (!resetBtn) return;
    resetBtn.hidden = !hasActiveFilters();
  }

  function buildQuery(params) {
    const qs = new URLSearchParams();
    if (params.q) qs.set("q", params.q);
    if (params.etage !== null && params.etage !== undefined && params.etage !== "") {
      qs.set("etage", String(params.etage));
    }
    if (params.service) qs.set("service", params.service);
    if (params.sexe) qs.set("sexe", params.sexe);
    if (params.page && params.page > 1) qs.set("page", String(params.page));
    return qs;
  }

  function syncUrl(params) {
    const qs = buildQuery(params);
    const query = qs.toString();
    const url = query ? `/soignant/lits?${query}` : "/soignant/lits";
    window.history.replaceState({ lits: params }, "", url);
  }

  function setLoading(isLoading) {
    if (tableWrap) tableWrap.setAttribute("aria-busy", isLoading ? "true" : "false");
    if (loadingEl) {
      loadingEl.hidden = !isLoading;
      loadingEl.setAttribute("aria-hidden", isLoading ? "false" : "true");
    }
    if (searchInput) searchInput.setAttribute("aria-busy", isLoading ? "true" : "false");
  }

  function showError(message) {
    if (!errorEl) return;
    if (message) {
      errorEl.textContent = message;
      errorEl.hidden = false;
    } else {
      errorEl.textContent = "";
      errorEl.hidden = true;
    }
  }

  function renderRow(row) {
    const lit = row.lit_complet || `${row.chambre || ""}${row.lit || ""}`;
    const sexe = (row.Sexe || "").toUpperCase();
    const sexeClass = sexe === "M" || sexe === "F" ? sexe.toLowerCase() : "x";
    return `
      <tr>
        <td data-label="Étage"><span class="lits-etage-tag">${escapeHtml(row.etage_libelle)}</span></td>
        <td class="mono" data-label="Chambre"><span class="lits-lit-tag">${escapeHtml(lit)}</span></td>
        <td data-label="Nom"><strong class="lits-nom">${escapeHtml(row.NomFamille)}</strong></td>
        <td data-label="Prénom"><span class="lits-prenom">${escapeHtml(row.Prenom || "—")}</span></td>
        <td data-label="Sexe"><span class="lits-sexe-badge lits-sexe-${sexeClass}">${escapeHtml(sexe || "—")}</span></td>
        <td data-label="Service"><span class="lits-service">${escapeHtml(row.service_libelle)}</span></td>
        <td class="num mono-value" data-label="Âge">${formatAge(row.age_admission)}</td>
        <td class="center" data-label="Fiche">
          <a class="table-link lits-open-link" href="/soignant/sejours/${encodeURIComponent(row.SejourID)}">Ouvrir</a>
        </td>
      </tr>`;
  }

  function renderTable(items) {
    if (!tbody) return;
    if (!items.length) {
      tbody.innerHTML =
        '<tr class="lits-empty-row"><td colspan="8">Aucun lit ne correspond à votre recherche.</td></tr>';
      return;
    }
    tbody.innerHTML = items.map(renderRow).join("");
  }

  function updateMeta(data) {
    if (metaEl) {
      metaEl.textContent = `${data.total} lit(s) — page ${data.page}`;
    }
    if (pageInfoEl) pageInfoEl.textContent = `Page ${data.page}`;
    if (pageInput) pageInput.value = String(data.page);
    currentPage = data.page;

    const hasPrev = data.page > 1;
    const hasNext = data.page * data.page_size < data.total;
    if (prevBtn) prevBtn.disabled = !hasPrev;
    if (nextBtn) nextBtn.disabled = !hasNext;
  }

  async function fetchLits(params) {
    const requestId = ++activeRequestId;
    if (abortController) abortController.abort();
    abortController = new AbortController();

    const qs = buildQuery(params);
    setLoading(true);
    showError("");

    try {
      const response = await fetch(`${API_URL}?${qs.toString()}`, {
        signal: abortController.signal,
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        throw new Error(`Erreur serveur (${response.status})`);
      }
      const data = await response.json();
      if (requestId !== activeRequestId) return;
      renderTable(data.items || []);
      updateMeta(data);
      syncUrl(params);
      updateResetVisibility();
    } catch (err) {
      if (err.name === "AbortError") return;
      if (requestId !== activeRequestId) return;
      showError("Impossible de charger les lits. Réessayez dans un instant.");
    } finally {
      if (requestId === activeRequestId) {
        setLoading(false);
      }
    }
  }

  function scheduleFetch(resetPage) {
    if (resetPage) currentPage = 1;
    if (pageInput) pageInput.value = String(currentPage);
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      fetchLits(readFilters());
    }, DEBOUNCE_MS);
  }

  function fetchNow(resetPage) {
    clearTimeout(debounceTimer);
    if (resetPage) currentPage = 1;
    if (pageInput) pageInput.value = String(currentPage);
    fetchLits(readFilters());
  }

  form?.addEventListener("submit", (event) => {
    event.preventDefault();
    fetchNow(true);
  });

  searchInput?.addEventListener("input", () => {
    scheduleFetch(true);
  });

  filterSelects.forEach((select) => {
    select.addEventListener("change", () => {
      fetchNow(true);
    });
  });

  resetBtn?.addEventListener("click", () => {
    if (searchInput) searchInput.value = "";
    filterSelects.forEach((select) => {
      select.value = "";
    });
    fetchNow(true);
  });

  prevBtn?.addEventListener("click", () => {
    if (currentPage <= 1) return;
    currentPage -= 1;
    fetchNow(false);
  });

  nextBtn?.addEventListener("click", () => {
    if (nextBtn.disabled) return;
    currentPage += 1;
    fetchNow(false);
  });

  window.addEventListener("popstate", (event) => {
    if (!event.state?.lits) return;
    const f = event.state.lits;
    if (searchInput) searchInput.value = f.q || "";
    const etageSelect = form?.elements.namedItem("etage");
    const serviceSelect = form?.elements.namedItem("service");
    const sexeSelect = form?.elements.namedItem("sexe");
    if (etageSelect) etageSelect.value = f.etage === null || f.etage === undefined ? "" : String(f.etage);
    if (serviceSelect) serviceSelect.value = f.service || "";
    if (sexeSelect) sexeSelect.value = f.sexe || "";
    currentPage = f.page || 1;
    fetchNow(false);
  });

  updateResetVisibility();
  setLoading(false);
})();
