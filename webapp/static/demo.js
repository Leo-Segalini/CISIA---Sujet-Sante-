/**
 * Mode présentation CISIA — spotlight, pulse et navigation mobile.
 * Respecte prefers-reduced-motion.
 */
(function demoPresentation() {
  "use strict";

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ——— Sidebar repliable (rail icônes) ——— */
  function initSidebar() {
    const body = document.body;
    const sidebar = document.getElementById("sidebar");
    const toggleBtns = document.querySelectorAll("[data-sidebar-toggle]");
    const STORAGE_KEY = "cisia-sidebar-collapsed";

    if (!sidebar || !body.classList.contains("layout-app")) return;

    function isCollapsed() {
      return body.classList.contains("sidebar-is-collapsed");
    }

    function syncUi(collapsed) {
      body.classList.toggle("sidebar-is-expanded", !collapsed);
      body.classList.toggle("sidebar-is-collapsed", collapsed);
      toggleBtns.forEach((btn) => {
        btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
        btn.setAttribute(
          "aria-label",
          collapsed ? "Développer le menu" : "Réduire le menu"
        );
        const icon = btn.querySelector(".sidebar-toggle-icon");
        if (icon) {
          icon.textContent = collapsed ? "chevron_right" : "chevron_left";
        }
      });
    }

    function setCollapsed(collapsed, persist) {
      syncUi(collapsed);
      if (persist) {
        localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0");
      }
    }

    function toggleSidebar() {
      setCollapsed(!isCollapsed(), true);
    }

    const stored = localStorage.getItem(STORAGE_KEY);
    setCollapsed(stored === "1", false);

    toggleBtns.forEach((btn) => {
      btn.addEventListener("click", toggleSidebar);
    });
  }

  /* ——— Navigation mobile (legacy nav panel) ——— */
  function initMobileNav() {
    const nav = document.querySelector("[data-nav-panel]");
    const toggle = document.querySelector("[data-nav-toggle]");
    if (!nav || document.getElementById("sidebar")) return;

    toggle?.addEventListener("click", () => {
      const open = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  /* ——— Spotlight démo ——— */
  function initSpotlight() {
    const spotlightId = document.body.dataset.demoSpotlight;
    if (!spotlightId) return;

    const target = document.querySelector(`[data-demo-target="${spotlightId}"]`);
    if (!target) return;

    target.classList.add("demo-target-active");
    if (!reducedMotion) {
      target.classList.add("demo-pulse");
    }

    const overlay = document.createElement("div");
    overlay.className = "demo-spotlight-overlay";
    overlay.setAttribute("aria-hidden", "true");
    document.body.appendChild(overlay);
    document.body.classList.add("demo-spotlight-on");

    const hint = document.createElement("div");
    hint.className = "demo-spotlight-hint";
    hint.setAttribute("role", "status");
    const hintText = target.dataset.demoHint || "Continuer la démo";
    hint.innerHTML =
      `<span class="demo-spotlight-arrow" aria-hidden="true">↓</span>` +
      `<span>${hintText}</span>` +
      `<span class="demo-spotlight-enter"><kbd>Entrée</kbd></span>`;
    document.body.appendChild(hint);

    function positionHint() {
      const rect = target.getBoundingClientRect();
      const hintRect = hint.getBoundingClientRect();
      let top = rect.bottom + 12;
      let left = rect.left + rect.width / 2 - hintRect.width / 2;

      if (left < 8) left = 8;
      if (left + hintRect.width > window.innerWidth - 8) {
        left = window.innerWidth - hintRect.width - 8;
      }
      if (top + hintRect.height > window.innerHeight - 8) {
        top = rect.top - hintRect.height - 12;
        hint.querySelector(".demo-spotlight-arrow").textContent = "↑";
      } else {
        hint.querySelector(".demo-spotlight-arrow").textContent = "↓";
      }

      hint.style.top = `${Math.max(8, top)}px`;
      hint.style.left = `${left}px`;
    }

    function scrollToTarget() {
      target.scrollIntoView({
        behavior: reducedMotion ? "auto" : "smooth",
        block: "center",
        inline: "nearest",
      });
    }

    scrollToTarget();
    window.setTimeout(() => {
      positionHint();
      if (!reducedMotion) {
        window.setTimeout(positionHint, 400);
      }
    }, reducedMotion ? 0 : 350);

    window.addEventListener("resize", positionHint, { passive: true });
    window.addEventListener(
      "scroll",
      () => {
        window.requestAnimationFrame(positionHint);
      },
      { passive: true }
    );

    target.addEventListener(
      "focus",
      () => {
        target.classList.add("demo-target-focused");
      },
      { once: true }
    );
  }

  /* ——— Tables responsives (cartes mobile) ——— */
  function initResponsiveTables() {
    document.querySelectorAll("[data-table-cards]").forEach((table) => {
      const headers = Array.from(table.querySelectorAll("thead th")).map((th) =>
        th.textContent.trim()
      );
      table.querySelectorAll("tbody tr").forEach((row) => {
        row.querySelectorAll("td").forEach((cell, i) => {
          if (headers[i]) cell.setAttribute("data-label", headers[i]);
        });
      });
    });
  }

  /* ——— Avancement démo au clavier (Entrée) ——— */
  function isTypingField() {
    const el = document.activeElement;
    if (!el || el === document.body) return false;
    const tag = el.tagName;
    if (tag === "TEXTAREA") return true;
    if (tag === "SELECT") return true;
    if (tag === "INPUT") {
      const type = (el.type || "text").toLowerCase();
      return !["checkbox", "radio", "button", "submit", "reset"].includes(type);
    }
    return Boolean(el.isContentEditable);
  }

  function getSpotlightTarget() {
    const id = document.body.dataset.demoSpotlight;
    if (!id) return null;
    return document.querySelector(`[data-demo-target="${id}"]`);
  }

  function advanceDemo() {
    const bar = document.querySelector("[data-demo-nav]");
    if (!bar) return;

    const target = getSpotlightTarget();
    if (target) {
      const tag = target.tagName;
      if (tag === "A" && target.href) {
        window.location.assign(target.href);
        return;
      }
      if (tag === "FORM") {
        const origine = target.querySelector('[name="origine"]');
        if (origine && origine.value === "insee_ajoute") {
          /* Registre déjà filtré — passer à l'étape suivante */
        } else {
          if (origine && !origine.value) {
            origine.value = "insee_ajoute";
          }
          if (typeof target.requestSubmit === "function") {
            target.requestSubmit();
          } else {
            target.submit();
          }
          return;
        }
      }
      if (tag === "BUTTON" && !target.disabled) {
        target.click();
        return;
      }
    }

    const next = document.querySelector(".process-bar-next");
    if (next && next.href) {
      window.location.assign(next.href);
    }
  }

  function initEnterNavigation() {
    const bar = document.querySelector("[data-demo-nav]");
    if (!bar) return;

    document.body.classList.add("demo-enter-enabled");
    let locked = false;

    document.addEventListener("keydown", (ev) => {
      if (ev.key !== "Enter") return;
      if (ev.shiftKey || ev.ctrlKey || ev.altKey || ev.metaKey) return;
      if (isTypingField()) return;
      if (locked) return;

      ev.preventDefault();
      locked = true;
      advanceDemo();
      window.setTimeout(() => {
        locked = false;
      }, 700);
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    initSidebar();
    initMobileNav();
    initUserMenu();
    initKiosk();
    initBanner();
    initSpotlight();
    initEnterNavigation();
    initResponsiveTables();
  });

  /* ——— Menu utilisateur ——— */
  function initUserMenu() {
    const btn = document.querySelector("[data-user-toggle]");
    const panel = document.querySelector("[data-user-panel]");
    if (!btn || !panel) return;
    btn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const open = panel.hasAttribute("hidden");
      if (open) {
        panel.removeAttribute("hidden");
        btn.setAttribute("aria-expanded", "true");
      } else {
        panel.setAttribute("hidden", "");
        btn.setAttribute("aria-expanded", "false");
      }
    });
    panel.addEventListener("click", (ev) => ev.stopPropagation());
    document.addEventListener("click", () => {
      panel.setAttribute("hidden", "");
      btn.setAttribute("aria-expanded", "false");
    });
  }

  /* ——— Mode kiosk / présentation ——— */
  function initKiosk() {
    const btn = document.querySelector("[data-kiosk-toggle]");
    if (!btn) return;
    const key = "cisia-kiosk";
    if (sessionStorage.getItem(key) === "1") {
      document.body.classList.add("kiosk-mode");
      btn.setAttribute("aria-pressed", "true");
    }
    btn.addEventListener("click", () => {
      const on = document.body.classList.toggle("kiosk-mode");
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      sessionStorage.setItem(key, on ? "1" : "0");
      if (on && document.documentElement.requestFullscreen) {
        document.documentElement.requestFullscreen().catch(() => {});
      } else if (!on && document.fullscreenElement) {
        document.exitFullscreen().catch(() => {});
      }
    });
    document.addEventListener("fullscreenchange", () => {
      if (!document.fullscreenElement && document.body.classList.contains("kiosk-mode")) {
        /* conserve kiosk visuel même si l'utilisateur quitte le plein écran OS */
      }
    });
  }

  /* ——— Bandeau masquable ——— */
  function initBanner() {
    const banner = document.querySelector("[data-banner]");
    const close = document.querySelector("[data-banner-close]");
    if (!banner || !close) return;
    if (sessionStorage.getItem("cisia-banner-hidden") === "1") {
      banner.setAttribute("hidden", "");
    }
    close.addEventListener("click", () => {
      banner.setAttribute("hidden", "");
      sessionStorage.setItem("cisia-banner-hidden", "1");
    });
  }
})();
