/**
 * Graphiques moniteur live — Chart.js, axes, légendes, polling 5 s.
 */
(function () {
  "use strict";

  const root = document.querySelector("[data-fiche-moniteur]");
  if (!root || typeof Chart === "undefined") return;

  const sejourId = root.getAttribute("data-sejour-id");
  const monitoringContinu = root.getAttribute("data-monitoring-continu") === "1";
  const refreshSec = Math.max(3, Number(root.getAttribute("data-refresh-sec") || 5));
  const charts = new Map();
  const COLOR = "#2d6765";
  const COLOR_ALERT = "#ba1a1a";
  const GRID = "rgba(45, 103, 101, 0.18)";

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function fmtVal(key, v) {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
    return key === "Temperature" ? Number(v).toFixed(1) : String(Math.round(Number(v)));
  }

  function bootSeries() {
    const boot = document.getElementById("moniteur-series-boot");
    if (!boot) return [];
    try {
      const data = JSON.parse(boot.textContent || "[]");
      boot.remove();
      return Array.isArray(data) ? data : [];
    } catch (e) {
      return [];
    }
  }

  function buildConfig(series) {
    const datasets = [
      {
        label: series.label + " (" + series.unit + ")",
        data: series.values,
        borderColor: COLOR,
        backgroundColor: "rgba(45, 103, 101, 0.18)",
        borderWidth: 2,
        pointRadius: 2,
        pointHoverRadius: 5,
        pointHitRadius: 12,
        tension: 0.25,
        fill: true,
        spanGaps: true,
      },
    ];
    if (series.seuil != null) {
      datasets.push({
        label: "Seuil " + series.seuil + " " + series.unit,
        data: series.labels.map(() => series.seuil),
        borderColor: COLOR_ALERT,
        borderWidth: 1.5,
        borderDash: [5, 4],
        pointRadius: 0,
        pointHoverRadius: 0,
        fill: false,
        tension: 0,
      });
    }
    return {
      type: "line",
      data: { labels: series.labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: reduceMotion ? false : { duration: 350 },
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            display: true,
            position: "bottom",
            labels: { boxWidth: 12, font: { size: 11 } },
          },
          tooltip: {
            callbacks: {
              label(ctx) {
                const v = ctx.parsed.y;
                if (v == null || Number.isNaN(v)) return ctx.dataset.label + " : —";
                const digits = series.key === "Temperature" ? 1 : 0;
                return ctx.dataset.label + " : " + Number(v).toFixed(digits);
              },
            },
          },
        },
        scales: {
          x: {
            title: { display: true, text: "Temps (relatif)", font: { size: 11 } },
            ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8, font: { size: 10 } },
            grid: { color: GRID },
          },
          y: {
            title: {
              display: true,
              text: series.label + " (" + series.unit + ")",
              font: { size: 11 },
            },
            ticks: { font: { size: 10 } },
            grid: { color: GRID },
          },
        },
      },
    };
  }

  function ensureChart(canvas, series) {
    const key = series.key;
    let chart = charts.get(key);
    if (chart) {
      chart.data.labels = series.labels;
      chart.data.datasets[0].data = series.values;
      if (series.seuil != null && chart.data.datasets[1]) {
        chart.data.datasets[1].data = series.labels.map(() => series.seuil);
      }
      chart.update(reduceMotion ? "none" : "active");
      return chart;
    }
    chart = new Chart(canvas, buildConfig(series));
    charts.set(key, chart);
    return chart;
  }

  function updateCards(payload) {
    const vitals = payload.constantes || {};
    const alerts = payload.constantes_alerte || {};
    root.querySelectorAll("[data-vital-key]").forEach((card) => {
      const key = card.getAttribute("data-vital-key");
      const flag = card.querySelector("[data-vital-flag]");
      const isAlert = Boolean(alerts[key]);
      card.classList.toggle("is-alert", isAlert);
      if (flag) flag.hidden = !isAlert;
      if (key === "TensionSystolique") {
        const bp = card.querySelector("[data-vital-bp]");
        if (bp) {
          const sys = vitals.TensionSystolique;
          const dia = vitals.TensionDiastolique;
          bp.textContent =
            sys == null ? "—" : Math.round(sys) + "/" + Math.round(dia == null ? 0 : dia);
        }
        return;
      }
      const valEl = card.querySelector("[data-vital-value]");
      if (valEl) valEl.textContent = fmtVal(key, vitals[key]);
    });
    const news = root.querySelector("[data-news-value]");
    if (news && payload.score_news != null) news.textContent = String(payload.score_news);
    const tendance = root.querySelector("[data-moniteur-tendance]");
    if (tendance && payload.tendance_constantes) {
      tendance.textContent = payload.tendance_constantes;
    }
    const urg = root.querySelector("[data-moniteur-urgence]");
    if (urg) {
      if (payload.urgence_pedagogique) {
        urg.hidden = false;
        urg.className = "vitals-status vitals-status-bad";
        urg.textContent =
          "Alerte machine active (" + (payload.urgence_restant_s || 0) + " s)";
      } else {
        urg.hidden = true;
      }
    }
    const clock = root.querySelector("[data-moniteur-horloge]");
    if (clock) {
      const now = new Date();
      const hh = String(now.getHours()).padStart(2, "0");
      const mm = String(now.getMinutes()).padStart(2, "0");
      const ss = String(now.getSeconds()).padStart(2, "0");
      clock.textContent = "Live " + hh + ":" + mm + ":" + ss + " · " + refreshSec + " s";
    }
  }

  function applySeries(seriesList) {
    (seriesList || []).forEach((series) => {
      const figure = root.querySelector('[data-chart-key="' + series.key + '"]');
      if (!figure) return;
      const canvas = figure.querySelector("[data-chart-canvas]");
      const last = figure.querySelector("[data-chart-last]");
      if (last) last.textContent = fmtVal(series.key, series.dernier) + " " + series.unit;
      if (canvas) ensureChart(canvas, series);
    });
  }

  // Boot depuis le JSON embarqué
  applySeries(bootSeries());

  if (!monitoringContinu) {
    return; // Pas de polling live hors soins continus
  }

  let timer = null;
  let inFlight = false;

  async function poll() {
    if (inFlight || document.hidden) return;
    inFlight = true;
    try {
      const res = await fetch("/api/sejours/" + encodeURIComponent(sejourId) + "/moniteur", {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      updateCards(data);
      applySeries(data.series || []);
    } catch (e) {
      const clock = root.querySelector("[data-moniteur-horloge]");
      if (clock) clock.textContent = "Live · reconnexion…";
    } finally {
      inFlight = false;
    }
  }

  function start() {
    stop();
    timer = window.setInterval(poll, refreshSec * 1000);
  }

  function stop() {
    if (timer) {
      window.clearInterval(timer);
      timer = null;
    }
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stop();
    else {
      poll();
      start();
    }
  });

  start();
})();
