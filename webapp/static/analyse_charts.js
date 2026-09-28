/**
 * Graphiques qualité — page /cisia/analyse
 * Chart.js déjà chargé (vendor). Respecte prefers-reduced-motion.
 */
(function () {
  "use strict";

  function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function palette() {
    const style = getComputedStyle(document.documentElement);
    return {
      exclus: style.getPropertyValue("--color-secondary").trim() || "#515f74",
      hallucinations: style.getPropertyValue("--color-error").trim() || "#ba1a1a",
      aberrants: style.getPropertyValue("--color-tertiary").trim() || "#ba8c2e",
      incoherences: style.getPropertyValue("--color-primary").trim() || "#2d6765",
      text: style.getPropertyValue("--color-on-surface").trim() || "#1a1c1e",
      grid: "rgba(80, 90, 100, 0.2)",
    };
  }

  function boot() {
    const el = document.getElementById("analyse-stats-boot");
    if (!el || typeof Chart === "undefined") return;
    let data;
    try {
      data = JSON.parse(el.textContent || "{}");
    } catch (e) {
      return;
    }
    const cats = data.categories || [];
    const fichiers = data.par_fichier || [];
    const colors = palette();
    const anim = prefersReducedMotion() ? false : { duration: 450 };

    const catCanvas = document.getElementById("chart-qualite-categories");
    if (catCanvas && cats.length) {
      const colorMap = {
        exclus: colors.exclus,
        hallucinations: colors.hallucinations,
        aberrants: colors.aberrants,
        incoherences: colors.incoherences,
      };
      new Chart(catCanvas, {
        type: "bar",
        data: {
          labels: cats.map(function (c) {
            return c.label;
          }),
          datasets: [
            {
              label: "Nombre",
              data: cats.map(function (c) {
                return c.n;
              }),
              backgroundColor: cats.map(function (c) {
                return colorMap[c.id] || colors.exclus;
              }),
              borderWidth: 0,
            },
          ],
        },
        options: {
          responsive: true,
          animation: anim,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                afterLabel: function (ctx) {
                  const c = cats[ctx.dataIndex];
                  return c && c.detail ? c.detail : "";
                },
              },
            },
          },
          scales: {
            x: {
              ticks: { color: colors.text, maxRotation: 25, minRotation: 0 },
              grid: { display: false },
            },
            y: {
              beginAtZero: true,
              ticks: { color: colors.text, precision: 0 },
              grid: { color: colors.grid },
              title: { display: true, text: "Effectifs", color: colors.text },
            },
          },
        },
      });
    }

    const fileCanvas = document.getElementById("chart-qualite-fichiers");
    if (fileCanvas && fichiers.length) {
      const filtered = fichiers.filter(function (f) {
        return (f.n_mal_notes || 0) + (f.n_aberrants || 0) > 0;
      });
      new Chart(fileCanvas, {
        type: "bar",
        data: {
          labels: filtered.map(function (f) {
            return f.libelle || f.fichier;
          }),
          datasets: [
            {
              label: "Mal notés / hallucinations",
              data: filtered.map(function (f) {
                return f.n_mal_notes;
              }),
              backgroundColor: colors.hallucinations,
              borderWidth: 0,
            },
            {
              label: "Aberrants",
              data: filtered.map(function (f) {
                return f.n_aberrants;
              }),
              backgroundColor: colors.aberrants,
              borderWidth: 0,
            },
          ],
        },
        options: {
          indexAxis: "y",
          responsive: true,
          animation: anim,
          plugins: {
            legend: {
              position: "bottom",
              labels: { color: colors.text, boxWidth: 14 },
            },
          },
          scales: {
            x: {
              stacked: false,
              beginAtZero: true,
              ticks: { color: colors.text, precision: 0 },
              grid: { color: colors.grid },
            },
            y: {
              ticks: { color: colors.text },
              grid: { display: false },
            },
          },
        },
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
