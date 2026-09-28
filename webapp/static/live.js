function fmt(v, digits) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return Number(v).toFixed(digits);
}

function vitalLine(c) {
  if (!c || Object.keys(c).length === 0) {
    return "<p class='muted'>Pas de capteur</p>";
  }
  return (
    "<div class='vital-mini'>" +
    "<span>♥ " + fmt(c.FrequenceCardiaque, 0) + "</span>" +
    "<span>O₂ " + fmt(c.SpO2, 0) + "%</span>" +
    "<span>" + fmt(c.TensionSystolique, 0) + "/" + fmt(c.TensionDiastolique, 0) + "</span>" +
    "<span>" + fmt(c.Temperature, 1) + "°C</span>" +
    "</div>"
  );
}

/** Clés des notifications d’urgence déjà marquées comme lues. */
const urgencesLues = new Set();

function loadLues() {
  try {
    const raw = sessionStorage.getItem("cisia_urgences_lues");
    if (!raw) return;
    JSON.parse(raw).forEach((k) => urgencesLues.add(k));
  } catch (e) {
    /* ignore */
  }
}

function saveLues() {
  try {
    sessionStorage.setItem("cisia_urgences_lues", JSON.stringify([...urgencesLues]));
  } catch (e) {
    /* ignore */
  }
}

function urgentList(data) {
  return (data.fil_alertes || []).filter((a) => a.niveau === "urgent");
}

function urgentKey(a) {
  if (!a) return null;
  return a.href || null;
}

function assistantLabel(data) {
  if (data.assistant) return data.assistant;
  if (data.assistant_en_cours) return "Analyse IA du dossier en cours…";
  return "";
}

function fillLlm(el, data) {
  if (!el) return;
  const text = assistantLabel(data);
  if (text) {
    el.hidden = false;
    el.textContent = "Assistant IA : " + text;
  } else if (data.assistant_actif) {
    el.hidden = false;
    el.textContent = "Assistant IA : en attente…";
  } else {
    el.hidden = true;
  }
}

function premiereNonLue(urgents) {
  return urgents.find((a) => !urgencesLues.has(urgentKey(a))) || null;
}

function marquerCommeLue(key) {
  if (!key) return;
  urgencesLues.add(key);
  saveLues();
  hideToast();
}

function showToast(a, data) {
  const toast = document.getElementById("alerte-toast");
  if (!toast || !a) return;
  const titre = document.getElementById("alerte-toast-titre");
  const detail = document.getElementById("alerte-toast-detail");
  const ouvrir = document.getElementById("alerte-toast-ouvrir");
  if (titre) {
    titre.textContent =
      (a.NomFamille || "Patient") +
      " · ch. " +
      a.chambre +
      (a.lit || "") +
      " · " +
      (a.service || "");
  }
  if (detail) detail.textContent = a.texte || "";
  if (ouvrir) ouvrir.href = a.href || "/";
  fillLlm(document.getElementById("alerte-toast-llm"), data);
  toast.dataset.urgentKey = urgentKey(a) || "";
  toast.hidden = false;
  toast.classList.add("is-visible");
}

function hideToast() {
  const toast = document.getElementById("alerte-toast");
  if (!toast) return;
  toast.hidden = true;
  toast.classList.remove("is-visible");
  delete toast.dataset.urgentKey;
}

function syncUrgentUi(data) {
  const urgents = urgentList(data);
  // Nettoie les clés lues qui ne sont plus urgentes
  const actives = new Set(urgents.map(urgentKey));
  [...urgencesLues].forEach((k) => {
    if (!actives.has(k)) urgencesLues.delete(k);
  });
  saveLues();

  const top = premiereNonLue(urgents);
  if (!top) {
    hideToast();
    return;
  }
  showToast(top, data);
}

function wireToastOnce() {
  const markRead = () => {
    const toast = document.getElementById("alerte-toast");
    marquerCommeLue(toast?.dataset.urgentKey || null);
  };
  ["alerte-toast-fermer", "alerte-toast-lu"].forEach((id) => {
    const btn = document.getElementById(id);
    if (btn && !btn.dataset.wired) {
      btn.dataset.wired = "1";
      btn.addEventListener("click", markRead);
    }
  });
  if (!document.body.dataset.toastEsc) {
    document.body.dataset.toastEsc = "1";
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") markRead();
    });
  }
}

function render(data) {
  const horloge = document.getElementById("horloge");
  if (horloge) horloge.textContent = data.horloge;
  const hop = document.getElementById("hopital-live");
  if (hop && data.hopital) hop.textContent = data.hopital;

  const fil = document.getElementById("fil-principal");
  if (fil) {
    const urgents = urgentList(data);
    const nonLue = premiereNonLue(urgents);
    if (nonLue) {
      fil.innerHTML =
        "<strong class='urgent-inline'>URGENCE</strong> — <a href='" +
        nonLue.href +
        "'>" +
        nonLue.NomFamille +
        " · ch. " +
        nonLue.chambre +
        (nonLue.lit ? nonLue.lit : "") +
        "</a> — " +
        nonLue.texte;
    } else if (urgents.length) {
      fil.textContent =
        urgents.length +
        " urgence(s) déjà lue(s). Les chambres restent en rouge sur le plan.";
    } else if (data.fil_alertes && data.fil_alertes.length) {
      const a = data.fil_alertes[0];
      fil.innerHTML =
        "<a href='" +
        a.href +
        "'>" +
        a.NomFamille +
        " · ch. " +
        a.chambre +
        (a.lit ? a.lit : "") +
        "</a> — " +
        a.texte;
    } else {
      fil.textContent = "Aucune alerte machine pour le moment. Continuez la ronde habituelle.";
    }
  }

  const assistant = document.getElementById("assistant");
  if (assistant) {
    const text = assistantLabel(data);
    if (text && premiereNonLue(urgentList(data))) {
      assistant.hidden = false;
      assistant.textContent = "Assistant IA : " + text;
    } else {
      assistant.hidden = true;
    }
  }

  syncUrgentUi(data);

  const root = document.getElementById("etages");
  if (!root) return;
  saveOpenFloors();
  root.innerHTML = "";
  root.setAttribute("aria-busy", "false");

  const plan = data.plan_etages || [];
  const legacy = data.etages || {};

  if (!plan.length) {
    Object.entries(legacy).forEach(([etageLib, rooms], index) => {
      root.appendChild(renderEtageLegacy(etageLib, rooms, urgencesLues, index));
    });
    wireLitActions();
    return;
  }

  plan.forEach((floor, index) => {
    root.appendChild(renderFloor(floor, urgencesLues, index));
  });
  wireLitActions();
}

/** Étages ouverts dans le plan (conservé entre les ticks live). */
const openFloors = new Set();

function saveOpenFloors() {
  document.querySelectorAll(".plan-etage[open]").forEach((el) => {
    const key = el.dataset.etageKey;
    if (key) openFloors.add(key);
  });
}

function shouldFloorOpen(floorKey, index) {
  if (openFloors.size === 0 && index === 0) return true;
  return openFloors.has(floorKey);
}

function floorStats(floorOrRooms) {
  const stats = { urgent: 0, total: 0, occupe: 0 };
  const lits = [];
  if (Array.isArray(floorOrRooms)) {
    lits.push(...floorOrRooms);
  } else {
    (floorOrRooms.services || []).forEach((svc) => {
      lits.push(...(svc.lits || []));
    });
  }
  lits.forEach((lit) => {
    stats.total += 1;
    if (!lit.vide && lit.niveau !== "disponible" && lit.niveau !== "a_nettoyer") {
      stats.occupe += 1;
    }
    if (lit.niveau === "urgent") stats.urgent += 1;
  });
  return stats;
}

function renderEtageSummary(title, stats, metaHtml) {
  const urgentBadge =
    stats.urgent > 0
      ? "<span class='plan-etage-badge plan-etage-badge--urgent'>" +
        stats.urgent +
        " urgent</span>"
      : "";
  return (
    "<summary class='plan-etage-head'>" +
    "<span class='plan-etage-head-inner'>" +
    "<span class='material-symbols-outlined plan-etage-chevron' aria-hidden='true'>expand_more</span>" +
    "<span class='plan-etage-title-wrap'>" +
    "<h2 class='plan-etage-title'>" +
    title +
    "</h2>" +
    (metaHtml || "") +
    "</span>" +
    "<span class='plan-etage-badges' aria-hidden='true'>" +
    urgentBadge +
    "<span class='plan-etage-badge'>" +
    stats.occupe +
    "/" +
    stats.total +
    " lits</span>" +
    "</span></span></summary>"
  );
}

function wireFloorToggle(details, floorKey) {
  details.addEventListener("toggle", () => {
    if (details.open) openFloors.add(floorKey);
    else openFloors.delete(floorKey);
  });
}

function statutLabel(r, lue) {
  if (r.niveau === "urgent") return lue ? "Urgent · lu" : "Urgent";
  if (r.niveau === "a_surveiller") return "À surveiller";
  if (r.niveau === "a_nettoyer") return "À nettoyer";
  if (r.vide || r.niveau === "disponible") return "Libre";
  return "Calme";
}

function statutClass(r) {
  if (r.niveau === "urgent") return "lit-card-pill--urgent";
  if (r.niveau === "a_surveiller") return "lit-card-pill--watch";
  if (r.niveau === "a_nettoyer") return "lit-card-pill--clean";
  if (r.vide || r.niveau === "disponible") return "lit-card-pill--free";
  return "lit-card-pill--calm";
}

function formatPerson(person) {
  if (!person) return "—";
  if (typeof person === "string") return person.trim() || "—";
  const prenom = (person.prenom || "").trim();
  const nom = (person.nom || "").trim();
  return (prenom + " " + nom).trim() || "—";
}

function renderEquipeHtml(equipe) {
  const eq = equipe || {};
  const roles = [
    { icon: "stethoscope", label: "Médecin", value: formatPerson(eq.medecin) },
    { icon: "vaccines", label: "Infirmier·e", value: formatPerson(eq.infirmier) },
    { icon: "health_and_safety", label: "Aide-soignant·e", value: formatPerson(eq.aide_soignante) },
  ];
  return (
    "<ul class='plan-equipe-list' aria-label='Équipe du service'>" +
    roles
      .map(
        (role) =>
          "<li class='plan-equipe-item'>" +
          "<span class='material-symbols-outlined plan-equipe-icon' aria-hidden='true'>" +
          role.icon +
          "</span>" +
          "<div class='plan-equipe-body'>" +
          "<span class='plan-equipe-role'>" +
          role.label +
          "</span>" +
          "<span class='plan-equipe-name'>" +
          role.value +
          "</span></div></li>"
      )
      .join("") +
    "</ul>"
  );
}

function renderEquipeInline(equipe) {
  const eq = equipe || {};
  return (
    "<dl class='plan-equipe-inline' aria-label='Équipe du service'>" +
    "<div><dt>Médecin</dt><dd>" + formatPerson(eq.medecin) + "</dd></div>" +
    "<div><dt>Infirmier·e</dt><dd>" + formatPerson(eq.infirmier) + "</dd></div>" +
    "<div><dt>Aide-soignant·e</dt><dd>" + formatPerson(eq.aide_soignante) + "</dd></div>" +
    "</dl>"
  );
}

function litCardHead(r, lue) {
  const pillClass = statutClass(r);
  const label = statutLabel(r, lue);
  return (
    "<header class='lit-card-top'>" +
    "<p class='lit-card-room'>Ch. " + r.chambre + " <span class='lit-card-bed'>· Lit " + r.lit + "</span></p>" +
    "<span class='lit-card-pill " + pillClass + "' role='img' aria-label='Statut : " + label +
    "'><span class='lit-card-dot' aria-hidden='true'></span></span></header>"
  );
}

function renderLitCard(r, urgencesLues) {
  if (r.niveau === "a_nettoyer") {
    const div = document.createElement("div");
    div.className = "lit-card a_nettoyer";
    div.innerHTML =
      litCardHead(r) +
      "<p class='lit-card-patient'><span class='lit-card-name'>" + (r.NomFamille || "—") +
      "</span><span class='lit-card-demo'>Décès · à nettoyer</span></p>" +
      "<button type='button' class='btn-clean lit-card-action' data-service='" +
      (r.service_code || r.service) + "' data-chambre='" + r.chambre + "' data-lit='" + r.lit +
      "'>Nettoyer</button>";
    return div;
  }

  if (r.vide || r.niveau === "disponible") {
    const div = document.createElement("div");
    div.className = "lit-card disponible";
    div.innerHTML =
      litCardHead(r) +
      "<p class='lit-card-patient'><span class='lit-card-name'>Lit libre</span></p>" +
      "<button type='button' class='btn-plus lit-card-action' data-service='" +
      (r.service_code || r.service) + "' data-chambre='" + r.chambre + "' data-lit='" + r.lit +
      "' aria-label='Admettre un patient chambre " + r.chambre + " lit " + r.lit + "'>+</button>";
    return div;
  }

  const sejHref = "/soignant/sejours/" + r.SejourID;
  const lue = r.niveau === "urgent" && urgencesLues.has(sejHref);
  const a = document.createElement("a");
  a.className = "lit-card " + r.niveau + (lue ? " lue" : "");
  a.href = sejHref;
  const pct = Math.round((r.proba || 0) * 100);
  const vitals = r.constantes || {};
  const demo = (r.Sexe ? r.Sexe : "") + (r.age ? (r.Sexe ? " · " : "") + r.age + " ans" : "");
  a.innerHTML =
    litCardHead(r, lue) +
    "<p class='lit-card-patient'><span class='lit-card-name'>" + r.NomFamille + "</span>" +
    (demo ? "<span class='lit-card-demo'>" + demo + "</span>" : "") + "</p>" +
    "<div class='lit-card-vitals'>" +
    "<span class='lit-card-vital'><span class='material-symbols-outlined' aria-hidden='true'>favorite</span> " +
    "<span class='lit-card-vital-val'>" + fmt(vitals.FrequenceCardiaque, 0) + "</span></span>" +
    "<span class='lit-card-vital'><span class='lit-card-o2'>O₂</span> " +
    "<span class='lit-card-vital-val'>" + fmt(vitals.SpO2, 0) + "%</span></span></div>" +
    "<footer class='lit-card-foot muted'>NEWS " +
    (r.score_news === null || r.score_news === undefined ? "—" : r.score_news) +
    " · " + pct + "% réadm.</footer>";
  a.addEventListener("click", (ev) => {
    if (ev.metaKey || ev.ctrlKey) return;
    ev.preventDefault();
    window.location.href = sejHref;
  });
  return a;
}

function groupLitsParChambre(lits) {
  const parChambre = new Map();
  (lits || []).forEach((lit) => {
    const ch = String(lit.chambre || "");
    if (!parChambre.has(ch)) parChambre.set(ch, []);
    parChambre.get(ch).push(lit);
  });
  parChambre.forEach((items) => {
    items.sort((a, b) => String(a.lit).localeCompare(String(b.lit)));
  });
  return [...parChambre.keys()]
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
    .map((chambre) => ({
      chambre,
      lits: parChambre.get(chambre) || [],
    }));
}

function renderServiceBlock(service, urgencesLues, slotIndex) {
  const letter = slotIndex === 0 ? "A" : "B";
  const sec = document.createElement("section");
  sec.className = "plan-service";
  sec.dataset.serviceSlot = String(slotIndex);
  sec.dataset.serviceLetter = letter;
  sec.setAttribute("aria-label", "Service " + letter + " — " + service.nom);
  if (service.code) sec.dataset.serviceCode = service.code;
  sec.innerHTML =
    "<header class='plan-service-head'>" +
    "<span class='plan-service-tag'>Service " + letter + "</span>" +
    "<h3 class='plan-service-title'>" + service.nom + "</h3>" +
    "<p class='plan-service-meta muted'>" + service.aile + " · " + service.uf +
    " · " + (service.lits || []).length + "/" + (service.lits_total || 12) + " lits</p>" +
    renderEquipeInline(service.equipe) +
    "</header>" +
    "<div class='plan-chambres'></div>";
  const chambresWrap = sec.querySelector(".plan-chambres");
  groupLitsParChambre(service.lits).forEach((bloc) => {
    const row = document.createElement("div");
    row.className = "plan-chambre-row";
    row.setAttribute("aria-label", "Chambre " + bloc.chambre);
    row.innerHTML = "<div class='plan-chambre-tag' aria-hidden='true'>" + bloc.chambre + "</div>";
    const litsWrap = document.createElement("div");
    litsWrap.className = "plan-chambre-lits";
    bloc.lits.forEach((r) => litsWrap.appendChild(renderLitCard(r, urgencesLues)));
    row.appendChild(litsWrap);
    chambresWrap.appendChild(row);
  });
  return sec;
}

function renderFloor(floor, urgencesLues, index) {
  const floorKey = String(floor.etage ?? floor.etage_libelle);
  const stats = floorStats(floor);
  const meta =
    floor.medecin
      ? "<span class='plan-etage-meta muted'>Médecin · " + floor.medecin + "</span>"
      : "";
  const details = document.createElement("details");
  details.className = "plan-etage";
  details.dataset.etageKey = floorKey;
  details.open = shouldFloorOpen(floorKey, index);
  details.innerHTML =
    renderEtageSummary(floor.etage_libelle, stats, meta) +
    "<div class='plan-etage-panel'><div class='plan-services-row'></div></div>";
  wireFloorToggle(details, floorKey);
  const row = details.querySelector(".plan-services-row");
  (floor.services || []).forEach((svc, svcIndex) => {
    row.appendChild(renderServiceBlock(svc, urgencesLues, svcIndex));
  });
  return details;
}

function renderEtageLegacy(etageLib, rooms, urgencesLues, index) {
  const floorKey = etageLib;
  const stats = floorStats(rooms);
  const details = document.createElement("details");
  details.className = "plan-etage";
  details.dataset.etageKey = floorKey;
  details.open = shouldFloorOpen(floorKey, index);
  details.innerHTML =
    renderEtageSummary(etageLib, stats, "") +
    "<div class='plan-etage-panel'><div class='plan-lits-grid'></div></div>";
  wireFloorToggle(details, floorKey);
  const grid = details.querySelector(".plan-lits-grid");
  rooms.forEach((r) => grid.appendChild(renderLitCard(r, urgencesLues)));
  return details;
}

async function postLit(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "action lit");
  }
  return res.json();
}

function wireLitActions() {
  document.querySelectorAll(".btn-clean").forEach((btn) => {
    if (btn.dataset.wired) return;
    btn.dataset.wired = "1";
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        await postLit("/api/lits/nettoyer", {
          service: btn.dataset.service,
          chambre: btn.dataset.chambre,
          lit: btn.dataset.lit,
        });
        await tick();
      } catch (e) {
        btn.disabled = false;
        alert("Impossible de nettoyer ce lit pour la démo.");
      }
    });
  });
  document.querySelectorAll(".btn-plus").forEach((btn) => {
    if (btn.dataset.wired) return;
    btn.dataset.wired = "1";
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      btn.textContent = "…";
      try {
        const out = await postLit("/api/lits/admettre", {
          service: btn.dataset.service,
          chambre: btn.dataset.chambre,
          lit: btn.dataset.lit,
        });
        await tick();
        if (out.href) {
          // Option : rester sur le plan pour voir le lit rempli
        }
      } catch (e) {
        btn.disabled = false;
        btn.textContent = "+";
        alert("Impossible d’admettre un patient sur ce lit.");
      }
    });
  });
}

async function tick() {
  if (tickInFlight) return;
  tickInFlight = true;
  try {
    const res = await fetch("/api/live", {
      cache: "no-store",
      credentials: "same-origin",
    });
    if (res.status === 401) {
      const fil = document.getElementById("fil-principal");
      if (fil) fil.textContent = "Session expirée — reconnectez-vous.";
      return;
    }
    if (!res.ok) throw new Error("live");
    render(await res.json());
  } catch (e) {
    const fil = document.getElementById("fil-principal");
    if (fil)
      fil.textContent =
        "Les constantes ne répondent pas. Vérifiez que l’application tourne en local.";
  } finally {
    tickInFlight = false;
  }
}

let tickInFlight = false;
loadLues();
wireToastOnce();
tick();
setInterval(tick, 5000);
