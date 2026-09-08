/* Glavna logika sučelja - Školski raspored (web/PWA). */
"use strict";

const HR_WEEKDAYS = ["Ponedjeljak", "Utorak", "Srijeda", "Četvrtak", "Petak", "Subota", "Nedjelja"];

function formatDateShort(d) {
  return `${pad2(d.getDate())}.${pad2(d.getMonth() + 1)}.${d.getFullYear()}.`;
}

// ------------------------------------------------------------------
// Stanje
// ------------------------------------------------------------------
let appData = loadData();
let currentSingleTurnus = 0;

function currentChild() {
  return appData.getActive();
}

function persist() {
  saveData(appData);
}

// ------------------------------------------------------------------
// Elementi
// ------------------------------------------------------------------
const el = (id) => document.getElementById(id);

const childSelect = el("childSelect");
const addChildBtn = el("addChildBtn");
const menuBtn = el("menuBtn");

const dateLabel = el("dateLabel");
const weekLabel = el("weekLabel");
const turnusLabel = el("turnusLabel");

const emptyState = el("emptyState");
const dualView = el("dualView");
const singleView = el("singleView");

const titleA = el("titleA");
const titleB = el("titleB");
const tableA = el("tableA");
const tableB = el("tableB");
const cardA = el("cardA");
const cardB = el("cardB");

const titleSingle = el("titleSingle");
const tableSingle = el("tableSingle");
const backBtn = el("backBtn");

const sideMenu = el("sideMenu");
const sideMenuOverlay = el("sideMenuOverlay");

const childModal = el("childModal");
const childModalTitle = el("childModalTitle");
const childNameInput = el("childNameInput");
const turnus1Input = el("turnus1Input");
const turnus2Input = el("turnus2Input");
const periodsInput = el("periodsInput");
const startDateWrap = el("startDateWrap");
const startDateInput = el("startDateInput");
const startTurnusSelect = el("startTurnusSelect");
const childModalHint = el("childModalHint");

const scheduleModal = el("scheduleModal");
const editPeriodsInput = el("editPeriodsInput");
const editTable0 = el("editTable0");
const editTable1 = el("editTable1");
const tabBtn0 = el("tabBtn0");
const tabBtn1 = el("tabBtn1");
const timeSettings0 = el("timeSettings0");
const timeSettings1 = el("timeSettings1");

const correctionModal = el("correctionModal");
const correctionModalTitle = el("correctionModalTitle");
const correctionList = el("correctionList");
const correctionDateInput = el("correctionDateInput");
const correctionTurnusSelect = el("correctionTurnusSelect");

const aboutModal = el("aboutModal");

const backupReminder = el("backupReminder");

const timeSettingsInputs = {
  0: {
    startTime: el("startTime0"),
    periodMinutes: el("periodMinutes0"),
    shortBreakMinutes: el("shortBreak0"),
    longBreakMinutes: el("longBreak0"),
    longBreakAfterPeriod: el("longBreakAfter0"),
    hasPrePeriod: el("hasPrePeriod0"),
    prePeriodStartTime: el("prePeriodStart0"),
    prePeriodMinutes: el("prePeriodMinutes0"),
  },
  1: {
    startTime: el("startTime1"),
    periodMinutes: el("periodMinutes1"),
    shortBreakMinutes: el("shortBreak1"),
    longBreakMinutes: el("longBreak1"),
    longBreakAfterPeriod: el("longBreakAfter1"),
    hasPrePeriod: el("hasPrePeriod1"),
    prePeriodStartTime: el("prePeriodStart1"),
    prePeriodMinutes: el("prePeriodMinutes1"),
  },
};

// ------------------------------------------------------------------
// Render: statusna traka
// ------------------------------------------------------------------
function refreshStatusHeader() {
  const today = new Date();
  const weekdayName = HR_WEEKDAYS[(today.getDay() + 6) % 7];
  dateLabel.textContent = `${weekdayName}, ${formatDateShort(today)}`;

  const { monday, sunday, weekNum } = weekStatus(today);
  weekLabel.textContent = `${weekNum}. tjedan u godini  (${formatDateShort(monday)} – ${formatDateShort(sunday)})`;

  const child = currentChild();
  if (!child) {
    turnusLabel.textContent = "";
    return;
  }
  // Zaštita: loš/nepotpun zapis turnusa ne smije srušiti cijeli prikaz
  // (ostatak renderAll() bi se inače prekinuo prije crtanja tablica).
  try {
    turnusLabel.textContent = `Aktivni turnus danas: ${child.turnusNameForDate(today)}`;
  } catch (e) {
    console.error("Greška pri izračunu turnusa:", e);
    turnusLabel.textContent = "Aktivni turnus danas: (nije moguće izračunati)";
  }
}

// ------------------------------------------------------------------
// Render: tablice - zajedničke pomoćne funkcije (vrijeme sati/odmora)
// ------------------------------------------------------------------
const TOTAL_TABLE_COLS = 1 + DAY_KEYS.length; // stupac sa satom/vremenom + 7 dana

function buildPeriodHeaderCell(p) {
  const th = document.createElement("th");
  th.className = "period-col";
  const num = document.createElement("div");
  num.textContent = p.isPre ? "Predsat" : `${p.period}.`;
  const time = document.createElement("div");
  time.className = "period-time";
  time.textContent = `${p.start}–${p.end}`;
  th.appendChild(num);
  th.appendChild(time);
  return th;
}

function appendBreakRow(tbody, breakInfo) {
  const tr = document.createElement("tr");
  tr.className = `break-row break-row-${breakInfo.kind}`;
  const td = document.createElement("td");
  td.colSpan = TOTAL_TABLE_COLS;
  const label =
    breakInfo.kind === "long" ? "Veliki odmor" : breakInfo.kind === "gap" ? "Razmak do redovne nastave" : "Mali odmor";
  td.textContent = `${label} (${breakInfo.minutes} min) · ${breakInfo.start}–${breakInfo.end}`;
  tr.appendChild(td);
  tbody.appendChild(tr);
}

function appendEndOfDayRow(tbody, child, turnusIndex) {
  const tr = document.createElement("tr");
  tr.className = "end-of-day-row";
  const th = document.createElement("th");
  th.className = "period-col";
  th.textContent = "Kraj";
  tr.appendChild(th);
  for (const dayKey of DAY_KEYS) {
    const td = document.createElement("td");
    if (WEEKEND_KEYS.has(dayKey)) td.classList.add("weekend");
    td.dataset.endOfDayFor = dayKey;
    const label = child.dayEndTime(turnusIndex, dayKey);
    td.textContent = label || "–";
    tr.appendChild(td);
  }
  tbody.appendChild(tr);
  return tr;
}

// ------------------------------------------------------------------
// Render: tablice (read-only)
// ------------------------------------------------------------------
function buildScheduleTable(tableEl, child, turnusIndex) {
  tableEl.innerHTML = "";
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  const corner = document.createElement("th");
  corner.className = "period-col";
  headRow.appendChild(corner);
  for (const dayKey of DAY_KEYS) {
    const th = document.createElement("th");
    th.textContent = DAY_LABELS_SHORT_HR[dayKey];
    if (WEEKEND_KEYS.has(dayKey)) th.classList.add("weekend");
    headRow.appendChild(th);
  }
  thead.appendChild(headRow);
  tableEl.appendChild(thead);

  const periods = child.periodSchedule(turnusIndex);
  const tbody = document.createElement("tbody");
  for (const p of periods) {
    const tr = document.createElement("tr");
    if (p.isPre) tr.classList.add("pre-row");
    tr.appendChild(buildPeriodHeaderCell(p));
    for (const dayKey of DAY_KEYS) {
      const td = document.createElement("td");
      if (WEEKEND_KEYS.has(dayKey)) td.classList.add("weekend");
      td.textContent = p.isPre ? child.getPreSubject(turnusIndex, dayKey) : child.getSubject(turnusIndex, dayKey, p.period - 1);
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
    if (p.breakAfter) appendBreakRow(tbody, p.breakAfter);
  }
  appendEndOfDayRow(tbody, child, turnusIndex);
  tableEl.appendChild(tbody);
}

function turnusTitle(child, turnusIndex) {
  const name = child.turnusNames[turnusIndex] !== undefined ? child.turnusNames[turnusIndex] : String(turnusIndex);
  return `Tjedan — turnus ${name}`;
}

// ------------------------------------------------------------------
// Prikaz: prazno / dual / single
// ------------------------------------------------------------------
function showView(name) {
  emptyState.hidden = name !== "empty";
  dualView.hidden = name !== "dual";
  singleView.hidden = name !== "single";
}

function renderDual(child) {
  titleA.textContent = turnusTitle(child, 0);
  titleB.textContent = turnusTitle(child, 1);
  buildScheduleTable(tableA, child, 0);
  buildScheduleTable(tableB, child, 1);
  showView("dual");
}

function renderSingle(child, turnusIndex) {
  currentSingleTurnus = turnusIndex;
  titleSingle.textContent = turnusTitle(child, turnusIndex);
  buildScheduleTable(tableSingle, child, turnusIndex);
  showView("single");
}

function renderAll(preferredView) {
  populateChildSelect();
  refreshStatusHeader();
  const child = currentChild();
  if (!child) {
    showView("empty");
    maybeShowBackupReminder();
    return;
  }
  const view = preferredView || (singleView.hidden ? "dual" : "single");
  if (view === "single") {
    renderSingle(child, currentSingleTurnus);
  } else {
    renderDual(child);
  }
  maybeShowBackupReminder();
}

function populateChildSelect() {
  childSelect.innerHTML = "";
  for (const c of appData.children) {
    const opt = document.createElement("option");
    opt.value = c.name;
    opt.textContent = c.name;
    childSelect.appendChild(opt);
  }
  const active = currentChild();
  if (active) childSelect.value = active.name;
}

cardA.addEventListener("click", () => {
  const child = currentChild();
  if (child) renderSingle(child, 0);
});
cardB.addEventListener("click", () => {
  const child = currentChild();
  if (child) renderSingle(child, 1);
});
backBtn.addEventListener("click", () => {
  const child = currentChild();
  if (child) renderDual(child);
});

childSelect.addEventListener("change", () => {
  appData.activeChild = childSelect.value;
  persist();
  renderAll("dual");
});

// ------------------------------------------------------------------
// Bočni izbornik
// ------------------------------------------------------------------
function openMenu() {
  sideMenu.hidden = false;
  sideMenuOverlay.hidden = false;
}
function closeMenu() {
  sideMenu.hidden = true;
  sideMenuOverlay.hidden = true;
}
menuBtn.addEventListener("click", openMenu);
sideMenuOverlay.addEventListener("click", closeMenu);

el("menuEditSchedule").addEventListener("click", () => {
  closeMenu();
  openScheduleModal();
});
el("menuEditChild").addEventListener("click", () => {
  closeMenu();
  openChildModal(currentChild());
});
el("menuTurnusCorrection").addEventListener("click", () => {
  closeMenu();
  openCorrectionModal();
});
el("menuDeleteChild").addEventListener("click", () => {
  closeMenu();
  deleteCurrentChild();
});
el("menuPrint").addEventListener("click", () => {
  closeMenu();
  window.print();
});
el("menuExportData").addEventListener("click", () => {
  closeMenu();
  exportDataBackup();
});
el("menuImportData").addEventListener("click", () => {
  closeMenu();
  el("importFileInput").click();
});
el("importFileInput").addEventListener("change", (event) => {
  const file = event.target.files && event.target.files[0];
  if (file) importDataBackup(file);
  event.target.value = ""; // omogući ponovni odabir iste datoteke kasnije
});
el("menuAbout").addEventListener("click", () => {
  closeMenu();
  aboutModal.hidden = false;
});
el("aboutModalClose").addEventListener("click", () => {
  aboutModal.hidden = true;
});

addChildBtn.addEventListener("click", () => openChildModal(null));

// ------------------------------------------------------------------
// Modal: dijete (novo / uredi)
// ------------------------------------------------------------------
let editingChildName = null; // null = novo dijete

function openChildModal(child) {
  editingChildName = child ? child.name : null;
  childModalTitle.textContent = child ? "Uredi dijete" : "Novo dijete";
  childNameInput.value = child ? child.name : "";
  turnus1Input.value = child ? child.turnusNames[0] : DEFAULT_TURNUS_NAMES[0];
  turnus2Input.value = child ? child.turnusNames[1] : DEFAULT_TURNUS_NAMES[1];
  periodsInput.value = child ? child.periodsCount : DEFAULT_PERIODS;

  if (!child) {
    startDateWrap.hidden = false;
    childModalHint.hidden = true;
    startDateInput.value = toISODate(new Date());
    refreshStartTurnusOptions();
  } else {
    startDateWrap.hidden = true;
    childModalHint.hidden = false;
  }
  childModal.hidden = false;
  childNameInput.focus();
}

function refreshStartTurnusOptions() {
  startTurnusSelect.innerHTML = "";
  [turnus1Input.value || "A", turnus2Input.value || "B"].forEach((name, idx) => {
    const opt = document.createElement("option");
    opt.value = String(idx);
    opt.textContent = name;
    startTurnusSelect.appendChild(opt);
  });
}
turnus1Input.addEventListener("input", () => {
  if (!startDateWrap.hidden) refreshStartTurnusOptions();
});
turnus2Input.addEventListener("input", () => {
  if (!startDateWrap.hidden) refreshStartTurnusOptions();
});

el("childModalCancel").addEventListener("click", () => {
  childModal.hidden = true;
});

el("childModalSave").addEventListener("click", () => {
  const name = childNameInput.value.trim();
  if (!name) {
    alert("Ime djeteta je obavezno.");
    return;
  }
  const t1 = turnus1Input.value.trim() || "A";
  const t2 = turnus2Input.value.trim() || "B";
  const periods = Math.max(1, Math.min(12, parseInt(periodsInput.value, 10) || DEFAULT_PERIODS));

  const isNew = editingChildName === null;
  const existing = appData.getChild(name);
  if (isNew) {
    if (existing) {
      alert("Dijete s tim imenom već postoji.");
      return;
    }
    const startDate = startDateInput.value ? fromISODate(startDateInput.value) : new Date();
    const startTurnusIdx = parseInt(startTurnusSelect.value, 10) || 0;
    const child = new Child({ name, turnusNames: [t1, t2], periodsCount: periods });
    child.addOrReplaceReset(startDate, startTurnusIdx);
    appData.children.push(child);
    appData.activeChild = name;
  } else {
    if (name !== editingChildName && existing) {
      alert("Dijete s tim imenom već postoji.");
      return;
    }
    const child = appData.getChild(editingChildName);
    const wasActive = appData.activeChild === editingChildName;
    child.name = name;
    child.turnusNames = [t1, t2];
    child.periodsCount = periods;
    if (wasActive) appData.activeChild = name;
  }
  persist();
  childModal.hidden = true;
  renderAll("dual");
});

function deleteCurrentChild() {
  const child = currentChild();
  if (!child) return;
  if (!confirm(`Sigurno želiš obrisati dijete „${child.name}” i njegov raspored?`)) return;
  appData.children = appData.children.filter((c) => c.name !== child.name);
  appData.activeChild = appData.children.length ? appData.children[0].name : null;
  persist();
  renderAll("dual");
}

// ------------------------------------------------------------------
// Modal: uredi raspored
// ------------------------------------------------------------------
function buildEditableTable(tableEl, child, turnusIndex) {
  tableEl.innerHTML = "";
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  const corner = document.createElement("th");
  corner.className = "period-col";
  headRow.appendChild(corner);
  for (const dayKey of DAY_KEYS) {
    const th = document.createElement("th");
    th.textContent = DAY_LABELS_SHORT_HR[dayKey];
    if (WEEKEND_KEYS.has(dayKey)) th.classList.add("weekend");
    headRow.appendChild(th);
  }
  thead.appendChild(headRow);
  tableEl.appendChild(thead);

  const periods = child.periodSchedule(turnusIndex);
  const tbody = document.createElement("tbody");
  for (const p of periods) {
    const tr = document.createElement("tr");
    if (p.isPre) tr.classList.add("pre-row");
    tr.appendChild(buildPeriodHeaderCell(p));
    for (const dayKey of DAY_KEYS) {
      const td = document.createElement("td");
      const isWeekend = WEEKEND_KEYS.has(dayKey);
      if (isWeekend) td.classList.add("weekend");
      const input = document.createElement("input");
      input.type = "text";
      input.dataset.day = dayKey;
      if (p.isPre) {
        input.dataset.pre = "1";
        input.value = child.getPreSubject(turnusIndex, dayKey);
      } else {
        input.dataset.period = String(p.period - 1);
        input.value = child.getSubject(turnusIndex, dayKey, p.period - 1);
      }
      td.appendChild(input);
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
    if (p.breakAfter) appendBreakRow(tbody, p.breakAfter);
  }
  appendEndOfDayRow(tbody, child, turnusIndex);
  tableEl.appendChild(tbody);
}

function readEditableTable(tableEl) {
  const result = {};
  for (const dayKey of DAY_KEYS) result[dayKey] = [];
  tableEl.querySelectorAll("input").forEach((inp) => {
    if (inp.dataset.pre) return; // predsat se čita zasebno, vidi readPreRow
    const day = inp.dataset.day;
    const period = parseInt(inp.dataset.period, 10);
    result[day][period] = inp.value;
  });
  return result;
}

/** Pročita upisani "predsat" po danu iz editabilne tablice (dani bez teksta
 * se jednostavno izostave - to je normalno, predsat nije svaki dan). */
function readPreRow(tableEl) {
  const result = {};
  tableEl.querySelectorAll('input[data-pre="1"]').forEach((inp) => {
    if (inp.value) result[inp.dataset.day] = inp.value;
  });
  return result;
}

/** Osvježi samo redak "Kraj nastave" u editabilnoj tablici, na temelju trenutno
 * upisanih predmeta - bez ponovne izgradnje cijele tablice (da unos ne izgubi fokus). */
function liveUpdateEndOfDayRow(tableEl, timeSettingsRaw) {
  for (const dayKey of DAY_KEYS) {
    const inputs = Array.from(tableEl.querySelectorAll(`input[data-day="${dayKey}"]:not([data-pre])`)).sort(
      (a, b) => parseInt(a.dataset.period, 10) - parseInt(b.dataset.period, 10)
    );
    const row = inputs.map((inp) => inp.value);
    const label = dayEndTimeLabel(timeSettingsRaw, row);
    const td = tableEl.querySelector(`td[data-end-of-day-for="${dayKey}"]`);
    if (td) td.textContent = label || "–";
  }
}

function readTimeSettingsInputs(turnusIndex) {
  const inputs = timeSettingsInputs[turnusIndex];
  return {
    startTime: inputs.startTime.value || DEFAULT_TIME_SETTINGS.startTime,
    periodMinutes: parseInt(inputs.periodMinutes.value, 10),
    shortBreakMinutes: parseInt(inputs.shortBreakMinutes.value, 10),
    longBreakMinutes: parseInt(inputs.longBreakMinutes.value, 10),
    longBreakAfterPeriod: parseInt(inputs.longBreakAfterPeriod.value, 10),
    hasPrePeriod: inputs.hasPrePeriod.checked,
    prePeriodStartTime: inputs.prePeriodStartTime.value || DEFAULT_TIME_SETTINGS.prePeriodStartTime,
    prePeriodMinutes: parseInt(inputs.prePeriodMinutes.value, 10),
  };
}

function writeTimeSettingsInputs(turnusIndex, settings) {
  const inputs = timeSettingsInputs[turnusIndex];
  inputs.startTime.value = settings.startTime;
  inputs.periodMinutes.value = settings.periodMinutes;
  inputs.shortBreakMinutes.value = settings.shortBreakMinutes;
  inputs.longBreakMinutes.value = settings.longBreakMinutes;
  inputs.longBreakAfterPeriod.value = settings.longBreakAfterPeriod;
  inputs.hasPrePeriod.checked = Boolean(settings.hasPrePeriod);
  inputs.prePeriodStartTime.value = settings.prePeriodStartTime;
  inputs.prePeriodMinutes.value = settings.prePeriodMinutes;
  updatePrePeriodFieldsEnabled(turnusIndex);
}

/** Polja za predsat su siva/onemogućena dok "Ima predsat" nije uključeno. */
function updatePrePeriodFieldsEnabled(turnusIndex) {
  const inputs = timeSettingsInputs[turnusIndex];
  const enabled = inputs.hasPrePeriod.checked;
  inputs.prePeriodStartTime.disabled = !enabled;
  inputs.prePeriodMinutes.disabled = !enabled;
}

/** Nakon promjene vremena/trajanja/odmora za jedan turnus, ponovno izgradi samo
 * tu tablicu (satovi i redak odmora ovise o tim postavkama), zadrži upisano. */
function rebuildEditableTableTime(turnusIndex) {
  const child = currentChild();
  if (!child) return;
  const tableEl = turnusIndex === 0 ? editTable0 : editTable1;
  const data = readEditableTable(tableEl);
  const preData = readPreRow(tableEl);
  const tmp = new Child({
    name: child.name,
    turnusNames: child.turnusNames,
    periodsCount: parseInt(editPeriodsInput.value, 10) || child.periodsCount,
  });
  tmp.setScheduleForTurnus(turnusIndex, data);
  tmp.setPreScheduleForTurnus(turnusIndex, preData);
  tmp.setTimeSettings(turnusIndex, readTimeSettingsInputs(turnusIndex));
  buildEditableTable(tableEl, tmp, turnusIndex);
}

for (const turnusIndex of [0, 1]) {
  const inputs = timeSettingsInputs[turnusIndex];
  Object.values(inputs).forEach((input) => {
    input.addEventListener("change", () => {
      updatePrePeriodFieldsEnabled(turnusIndex);
      rebuildEditableTableTime(turnusIndex);
    });
  });
}

// Upis predmeta ne smije ponovno graditi tablicu (fokus bi se izgubio) - samo
// osvježi redak "Kraj nastave" uživo dok korisnik tipka.
editTable0.addEventListener("input", () => liveUpdateEndOfDayRow(editTable0, readTimeSettingsInputs(0)));
editTable1.addEventListener("input", () => liveUpdateEndOfDayRow(editTable1, readTimeSettingsInputs(1)));

function openScheduleModal() {
  const child = currentChild();
  if (!child) {
    alert("Prvo dodaj dijete.");
    return;
  }
  editPeriodsInput.value = child.periodsCount;
  tabBtn0.textContent = `Turnus ${child.turnusNames[0]}`;
  tabBtn1.textContent = `Turnus ${child.turnusNames[1]}`;
  writeTimeSettingsInputs(0, child.getTimeSettings(0));
  writeTimeSettingsInputs(1, child.getTimeSettings(1));
  buildEditableTable(editTable0, child, 0);
  buildEditableTable(editTable1, child, 1);
  editTable0.hidden = false;
  editTable1.hidden = true;
  timeSettings0.hidden = false;
  timeSettings1.hidden = true;
  tabBtn0.classList.add("active");
  tabBtn1.classList.remove("active");
  scheduleModal.hidden = false;
}

function setPeriodsCountLive(count) {
  const child = currentChild();
  if (!child) return;
  // sačuvaj trenutno upisano, pa ponovno izgradi s novim brojem redaka
  const data0 = readEditableTable(editTable0);
  const data1 = readEditableTable(editTable1);
  const pre0 = readPreRow(editTable0);
  const pre1 = readPreRow(editTable1);
  const tmp = new Child({
    name: child.name,
    turnusNames: child.turnusNames,
    periodsCount: count,
  });
  tmp.setTimeSettings(0, readTimeSettingsInputs(0));
  tmp.setTimeSettings(1, readTimeSettingsInputs(1));
  tmp.setScheduleForTurnus(0, data0);
  tmp.setScheduleForTurnus(1, data1);
  tmp.setPreScheduleForTurnus(0, pre0);
  tmp.setPreScheduleForTurnus(1, pre1);
  buildEditableTable(editTable0, tmp, 0);
  buildEditableTable(editTable1, tmp, 1);
}

editPeriodsInput.addEventListener("change", () => {
  const count = Math.max(1, Math.min(12, parseInt(editPeriodsInput.value, 10) || DEFAULT_PERIODS));
  editPeriodsInput.value = count;
  setPeriodsCountLive(count);
});

tabBtn0.addEventListener("click", () => {
  tabBtn0.classList.add("active");
  tabBtn1.classList.remove("active");
  editTable0.hidden = false;
  editTable1.hidden = true;
  timeSettings0.hidden = false;
  timeSettings1.hidden = true;
});
tabBtn1.addEventListener("click", () => {
  tabBtn1.classList.add("active");
  tabBtn0.classList.remove("active");
  editTable1.hidden = false;
  editTable0.hidden = true;
  timeSettings1.hidden = false;
  timeSettings0.hidden = true;
});

el("scheduleModalCancel").addEventListener("click", () => {
  scheduleModal.hidden = true;
});

el("scheduleModalSave").addEventListener("click", () => {
  const child = currentChild();
  if (!child) return;
  child.periodsCount = Math.max(1, Math.min(12, parseInt(editPeriodsInput.value, 10) || DEFAULT_PERIODS));
  child.setScheduleForTurnus(0, readEditableTable(editTable0));
  child.setScheduleForTurnus(1, readEditableTable(editTable1));
  child.setPreScheduleForTurnus(0, readPreRow(editTable0));
  child.setPreScheduleForTurnus(1, readPreRow(editTable1));
  child.setTimeSettings(0, readTimeSettingsInputs(0));
  child.setTimeSettings(1, readTimeSettingsInputs(1));
  persist();
  scheduleModal.hidden = true;
  renderAll();
});

// ------------------------------------------------------------------
// Modal: korekcija turnusa
// ------------------------------------------------------------------
function openCorrectionModal() {
  const child = currentChild();
  if (!child) {
    alert("Prvo dodaj dijete.");
    return;
  }
  correctionModalTitle.textContent = `Promjena turnusa — ${child.name}`;
  correctionTurnusSelect.innerHTML = "";
  child.turnusNames.forEach((name, idx) => {
    const opt = document.createElement("option");
    opt.value = String(idx);
    opt.textContent = name;
    correctionTurnusSelect.appendChild(opt);
  });
  correctionDateInput.value = toISODate(new Date());
  renderCorrectionList(child);
  correctionModal.hidden = false;
}

function renderCorrectionList(child) {
  correctionList.innerHTML = "";
  const sorted = child.sortedResets();
  sorted.forEach((r, i) => {
    const li = document.createElement("li");
    const turnusName = child.turnusNames[r.turnusIndex] !== undefined ? child.turnusNames[r.turnusIndex] : r.turnusIndex;
    const prefix = i === 0 ? "Početak" : "Korekcija";
    const span = document.createElement("span");
    span.textContent = `${prefix}: od ${formatDateShort(fromISODate(r.dateFrom))} → turnus ${turnusName}`;
    li.appendChild(span);
    if (i > 0) {
      const btn = document.createElement("button");
      btn.textContent = "Ukloni";
      btn.addEventListener("click", () => {
        child.removeReset(r.dateFrom);
        persist();
        renderCorrectionList(child);
        refreshStatusHeader();
        renderAll();
      });
      li.appendChild(btn);
    }
    correctionList.appendChild(li);
  });
}

el("correctionAddBtn").addEventListener("click", () => {
  const child = currentChild();
  if (!child) return;
  const date = correctionDateInput.value ? fromISODate(correctionDateInput.value) : new Date();
  const idx = parseInt(correctionTurnusSelect.value, 10) || 0;
  child.addOrReplaceReset(date, idx);
  persist();
  renderCorrectionList(child);
  refreshStatusHeader();
  renderAll();
});

el("correctionModalClose").addEventListener("click", () => {
  correctionModal.hidden = true;
});

// ------------------------------------------------------------------
// Sigurnosna kopija (izvoz/uvoz podataka kao .json datoteka)
// ------------------------------------------------------------------
function backupFileName() {
  const d = new Date();
  return `skolski-raspored-backup-${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}.json`;
}

function exportDataBackup() {
  const json = JSON.stringify(appData.toJSON(), null, 2);
  const blob = new Blob([json], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = backupFileName();
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // malo kašnjenje prije oslobađanja URL-a - neki mobilni preglednici
  // trebaju taj trenutak da pokrenu preuzimanje
  setTimeout(() => URL.revokeObjectURL(url), 2000);
  markBackupDone();
}

function importDataBackup(file) {
  const reader = new FileReader();
  reader.onload = () => {
    let parsed;
    try {
      parsed = JSON.parse(reader.result);
    } catch (e) {
      alert("Datoteka nije ispravan JSON backup.");
      return;
    }
    if (!parsed || !Array.isArray(parsed.children)) {
      alert("Datoteka ne izgleda kao backup Školskog rasporeda.");
      return;
    }
    const brojDjece = parsed.children.length;
    const poruka =
      `Backup sadrži ${brojDjece} ${brojDjece === 1 ? "dijete" : "djece"}.\n\n` +
      "Uvozom ćeš PREBRISATI trenutne podatke na ovom uređaju. Nastaviti?";
    if (!confirm(poruka)) return;
    appData = AppData.fromJSON(parsed);
    persist();
    renderAll("dual");
    markBackupDone(); // uvoz znači da korisnik već ima kopiju negdje izvan preglednika
    alert("Podaci su uspješno vraćeni iz backupa.");
  };
  reader.onerror = () => alert("Greška pri čitanju datoteke.");
  reader.readAsText(file, "utf-8");
}

// ------------------------------------------------------------------
// Podsjetnik za sigurnosnu kopiju
// ------------------------------------------------------------------
// Podaci žive samo u localStorage ovog preglednika/uređaja - ako korisnik
// počisti podatke/predmemoriju preglednika, raspored nestaje bez traga.
// Podsjetimo ga na to čim prvi put upiše nešto u raspored.
const BACKUP_FLAG_KEY = "skolskiRaspored_hasBackup";
const BACKUP_DISMISS_KEY = "skolskiRaspored_backupReminderDismissedAt";
const BACKUP_DISMISS_COOLDOWN_DAYS = 7;

function hasAnyScheduleData() {
  return appData.children.some((c) =>
    ["0", "1"].some(
      (k) =>
        DAY_KEYS.some((dayKey) => (c.getDayRow(Number(k), dayKey) || []).some((s) => s && String(s).trim() !== "")) ||
        DAY_KEYS.some((dayKey) => {
          const v = c.getPreSubject(Number(k), dayKey);
          return v && String(v).trim() !== "";
        })
    )
  );
}

function maybeShowBackupReminder() {
  try {
    if (localStorage.getItem(BACKUP_FLAG_KEY) === "1") {
      backupReminder.hidden = true;
      return;
    }
    if (!hasAnyScheduleData()) {
      backupReminder.hidden = true;
      return;
    }
    const dismissedAt = parseInt(localStorage.getItem(BACKUP_DISMISS_KEY) || "0", 10);
    const cooldownMs = BACKUP_DISMISS_COOLDOWN_DAYS * 24 * 60 * 60 * 1000;
    if (dismissedAt && Date.now() - dismissedAt < cooldownMs) {
      backupReminder.hidden = true;
      return;
    }
    backupReminder.hidden = false;
  } catch (e) {
    /* localStorage može biti nedostupan (npr. privatni način) - jednostavno preskoči podsjetnik */
  }
}

function markBackupDone() {
  try {
    localStorage.setItem(BACKUP_FLAG_KEY, "1");
  } catch (e) {
    /* ignoriraj - podsjetnik će se u najgorem slučaju pojaviti opet */
  }
  backupReminder.hidden = true;
}

el("backupReminderExport").addEventListener("click", () => {
  exportDataBackup();
});
el("backupReminderDismiss").addEventListener("click", () => {
  try {
    localStorage.setItem(BACKUP_DISMISS_KEY, String(Date.now()));
  } catch (e) {
    /* ignoriraj */
  }
  backupReminder.hidden = true;
});

// ------------------------------------------------------------------
// Init
// ------------------------------------------------------------------
function init() {
  if (!appData.children.length) {
    showView("empty");
    refreshStatusHeader();
    setTimeout(() => openChildModal(null), 300);
  } else {
    renderAll("dual");
  }
  setInterval(refreshStatusHeader, 60000);

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(() => {
      /* offline cache je opcionalan - ne prekidaj rad ako ne uspije */
    });
  }

  // Zatraži "persistent storage" - preglednik onda manje voljno automatski
  // briše podatke stranice pod pritiskom prostora (ne štiti od ručnog
  // "Obriši podatke pregledavanja", ali smanjuje šansu za slučajni gubitak).
  if (navigator.storage && navigator.storage.persist) {
    navigator.storage.persist().catch(() => {
      /* best-effort - nije kritično ako preglednik ovo ne podržava/odobri */
    });
  }
}

init();
