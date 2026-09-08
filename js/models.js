/* Podatkovni model i logika za izračun tjedna/turnusa - JS port app/models.py */
"use strict";

const DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
const DAY_LABELS_HR = {
  mon: "Ponedjeljak",
  tue: "Utorak",
  wed: "Srijeda",
  thu: "Četvrtak",
  fri: "Petak",
  sat: "Subota",
  sun: "Nedjelja",
};
const DAY_LABELS_SHORT_HR = {
  mon: "Pon",
  tue: "Uto",
  wed: "Sri",
  thu: "Čet",
  fri: "Pet",
  sat: "Sub",
  sun: "Ned",
};
const WEEKEND_KEYS = new Set(["sat", "sun"]);
const DEFAULT_PERIODS = 7;
const DEFAULT_TURNUS_NAMES = ["A", "B"];

// Zadane vrijednosti za izračun vremena sati/odmora - "sat" (nastavni sat)
// traje 45 min (hrvatski standard), nakon svakog sata mali odmor od 5 min,
// a nakon "longBreakAfterPeriod"-tog sata veliki odmor od 15 min.
const DEFAULT_TIME_SETTINGS = {
  startTime: "08:00",
  periodMinutes: 45,
  shortBreakMinutes: 5,
  longBreakMinutes: 15,
  longBreakAfterPeriod: 3,
  // "Predsat" - opcionalni dodatni sat prije redovnog početka nastave (npr.
  // izborni predmeti koji nisu svaki dan) - ima svoje vrijeme i trajanje,
  // neovisno o redovnom rasporedu.
  hasPrePeriod: false,
  prePeriodStartTime: "07:10",
  prePeriodMinutes: 45,
};

function pad2(n) {
  return n < 10 ? "0" + n : "" + n;
}

/** Parsira "HH:MM" u broj minuta od ponoći. */
function parseTimeToMinutes(str) {
  const parts = String(str || "").split(":");
  const h = Number(parts[0]);
  const m = Number(parts[1]);
  return (Number.isFinite(h) ? h : 0) * 60 + (Number.isFinite(m) ? m : 0);
}

/** Broj minuta od ponoći natrag u "HH:MM" (omota se preko ponoći ako zatreba). */
function minutesToTimeStr(mins) {
  const m = ((Math.round(mins) % 1440) + 1440) % 1440;
  return `${pad2(Math.floor(m / 60))}:${pad2(m % 60)}`;
}

/**
 * Prihvati djelomične/kamelCase/snake_case postavke vremena i popuni sve
 * što nedostaje zadanim vrijednostima - isti obrazac kao kod resets/turnusNames
 * (backup iz jedne aplikacije/verzije mora raditi i u drugoj).
 */
function normalizeTimeSettings(raw) {
  raw = raw || {};
  const pickNum = (camel, snake, fallback) => {
    const v = raw[camel] !== undefined ? raw[camel] : raw[snake];
    const n = Number(v);
    return Number.isFinite(n) ? n : fallback;
  };
  const startTime =
    typeof raw.startTime === "string"
      ? raw.startTime
      : typeof raw.start_time === "string"
      ? raw.start_time
      : DEFAULT_TIME_SETTINGS.startTime;
  const hasPrePeriod =
    raw.hasPrePeriod !== undefined
      ? Boolean(raw.hasPrePeriod)
      : raw.has_pre_period !== undefined
      ? Boolean(raw.has_pre_period)
      : DEFAULT_TIME_SETTINGS.hasPrePeriod;
  const prePeriodStartTime =
    typeof raw.prePeriodStartTime === "string"
      ? raw.prePeriodStartTime
      : typeof raw.pre_period_start_time === "string"
      ? raw.pre_period_start_time
      : DEFAULT_TIME_SETTINGS.prePeriodStartTime;
  return {
    startTime,
    periodMinutes: Math.max(1, pickNum("periodMinutes", "period_minutes", DEFAULT_TIME_SETTINGS.periodMinutes)),
    shortBreakMinutes: Math.max(0, pickNum("shortBreakMinutes", "short_break_minutes", DEFAULT_TIME_SETTINGS.shortBreakMinutes)),
    longBreakMinutes: Math.max(0, pickNum("longBreakMinutes", "long_break_minutes", DEFAULT_TIME_SETTINGS.longBreakMinutes)),
    longBreakAfterPeriod: Math.max(
      1,
      pickNum("longBreakAfterPeriod", "long_break_after_period", DEFAULT_TIME_SETTINGS.longBreakAfterPeriod)
    ),
    hasPrePeriod,
    prePeriodStartTime,
    prePeriodMinutes: Math.max(1, pickNum("prePeriodMinutes", "pre_period_minutes", DEFAULT_TIME_SETTINGS.prePeriodMinutes)),
  };
}

/**
 * Izgradi raspored vremena za `periodsCount` sati počevši od postavki `timeSettingsRaw`.
 * Vraća niz { period (1-based), start, end, startMinutes, endMinutes, breakAfter? }.
 * breakAfter (na svim satima osim zadnjeg) = { kind: "short"|"long", minutes, start, end }.
 */
function buildPeriodSchedule(timeSettingsRaw, periodsCount) {
  const ts = normalizeTimeSettings(timeSettingsRaw);
  const periods = [];
  if (ts.hasPrePeriod) {
    const preStart = parseTimeToMinutes(ts.prePeriodStartTime);
    const preEnd = preStart + ts.prePeriodMinutes;
    const preEntry = {
      period: 0,
      isPre: true,
      startMinutes: preStart,
      endMinutes: preEnd,
      start: minutesToTimeStr(preStart),
      end: minutesToTimeStr(preEnd),
    };
    const regularStart = parseTimeToMinutes(ts.startTime);
    const gapMinutes = regularStart - preEnd;
    if (gapMinutes > 0) {
      preEntry.breakAfter = {
        kind: "gap",
        minutes: gapMinutes,
        start: minutesToTimeStr(preEnd),
        end: minutesToTimeStr(regularStart),
      };
    }
    periods.push(preEntry);
  }
  let t = parseTimeToMinutes(ts.startTime);
  for (let p = 1; p <= periodsCount; p++) {
    const startMinutes = t;
    const endMinutes = t + ts.periodMinutes;
    const entry = {
      period: p,
      startMinutes,
      endMinutes,
      start: minutesToTimeStr(startMinutes),
      end: minutesToTimeStr(endMinutes),
    };
    t = endMinutes;
    if (p < periodsCount) {
      const isLong = p === ts.longBreakAfterPeriod;
      const breakMinutes = isLong ? ts.longBreakMinutes : ts.shortBreakMinutes;
      const breakStart = t;
      t += breakMinutes;
      entry.breakAfter = {
        kind: isLong ? "long" : "short",
        minutes: breakMinutes,
        start: minutesToTimeStr(breakStart),
        end: minutesToTimeStr(t),
      };
    }
    periods.push(entry);
  }
  return periods;
}

/** Broj sati u danu do (uključivo) zadnjeg neispraznog predmeta - prazni satovi na
 * kraju (npr. dijete ide doma ranije taj dan) se ne broje. */
function lastFilledPeriodCount(dayRow) {
  let last = 0;
  for (let i = 0; i < dayRow.length; i++) {
    if (dayRow[i] && String(dayRow[i]).trim() !== "") last = i + 1;
  }
  return last;
}

/** Vrijeme završetka nastave za jedan dan (na temelju stvarno upisanih satova),
 * ili null ako dan nema nijedan upisan predmet. */
function dayEndTimeLabel(timeSettingsRaw, dayRow) {
  const count = lastFilledPeriodCount(dayRow);
  if (count === 0) return null;
  const periods = buildPeriodSchedule(timeSettingsRaw, count);
  return periods[periods.length - 1].end;
}

/** Vraća datum kao "YYYY-MM-DD" (lokalno, bez vremenske zone). */
function toISODate(d) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

/** Parsira "YYYY-MM-DD" u Date (lokalna ponoć). */
function fromISODate(s) {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function atMidnight(d) {
  const r = new Date(d);
  r.setHours(0, 0, 0, 0);
  return r;
}

function addDays(d, days) {
  const r = new Date(d);
  r.setDate(r.getDate() + days);
  return r;
}

/** Ponedjeljak tjedna kojem pripada dani datum. */
function isoWeekMonday(d) {
  const dm = atMidnight(d);
  const weekday = (dm.getDay() + 6) % 7; // 0=pon ... 6=ned
  return addDays(dm, -weekday);
}

/** Standardni ISO-8601 broj tjedna u godini. */
function isoWeekNumber(d) {
  const date = atMidnight(d);
  const dayNum = date.getDay() || 7; // 1..7, pon=1
  const thursday = addDays(date, 4 - dayNum);
  const yearStart = new Date(thursday.getFullYear(), 0, 1);
  return Math.ceil(((thursday - yearStart) / 86400000 + 1) / 7);
}

function mod(n, m) {
  return ((n % m) + m) % m;
}

function weeksBetweenMondays(a, b) {
  // a, b su ponedjeljci (midnight); razlika u punim tjednima
  return Math.round((a - b) / (7 * 86400000));
}

/**
 * TurnusReset: { dateFrom: "YYYY-MM-DD" (ponedjeljak), turnusIndex: 0|1 }
 */

class Child {
  constructor({
    name,
    turnusNames = [...DEFAULT_TURNUS_NAMES],
    resets = [],
    schedule = { 0: {}, 1: {} },
    periodsCount = DEFAULT_PERIODS,
    timeSettings = {},
    preSchedule = { 0: {}, 1: {} },
  } = {}) {
    this.name = name;
    this.turnusNames = turnusNames;
    this.resets = resets;
    this.schedule = schedule;
    this.periodsCount = periodsCount;
    // timeSettings[turnusIndex] = { startTime, periodMinutes, shortBreakMinutes,
    // longBreakMinutes, longBreakAfterPeriod, hasPrePeriod, prePeriodStartTime,
    // prePeriodMinutes } - može biti djelomično popunjeno, nedostajuće se popuni
    // zadanim vrijednostima pri čitanju (getTimeSettings).
    this.timeSettings = timeSettings || {};
    // preSchedule[turnusIndex] = { dayKey: "Predmet" } - predsat se upisuje po
    // danu (dani bez predsata se jednostavno ne upisuju).
    this.preSchedule = preSchedule || {};
  }

  sortedResets() {
    return [...this.resets].sort((a, b) => (a.dateFrom < b.dateFrom ? -1 : a.dateFrom > b.dateFrom ? 1 : 0));
  }

  turnusIndexForWeek(monday) {
    if (!this.resets.length) return 0;
    const sorted = this.sortedResets();
    const mondayStr = toISODate(monday);
    let applicable = null;
    for (const r of sorted) {
      if (r.dateFrom <= mondayStr) applicable = r;
      else break;
    }
    if (!applicable) applicable = sorted[0];
    const applicableMonday = fromISODate(applicable.dateFrom);
    const weeksDiff = weeksBetweenMondays(monday, applicableMonday);
    return mod(applicable.turnusIndex + weeksDiff, 2);
  }

  turnusIndexForDate(d) {
    return this.turnusIndexForWeek(isoWeekMonday(d));
  }

  turnusNameForWeek(monday) {
    const idx = this.turnusIndexForWeek(monday);
    return this.turnusNames[idx] !== undefined ? this.turnusNames[idx] : String(idx);
  }

  turnusNameForDate(d) {
    return this.turnusNameForWeek(isoWeekMonday(d));
  }

  addOrReplaceReset(date, turnusIndex) {
    const monday = isoWeekMonday(date);
    const ds = toISODate(monday);
    this.resets = this.resets.filter((r) => r.dateFrom !== ds);
    this.resets.push({ dateFrom: ds, turnusIndex });
    this.resets = this.sortedResets();
  }

  removeReset(dateFrom) {
    this.resets = this.resets.filter((r) => r.dateFrom !== dateFrom);
  }

  getSubject(turnusIndex, dayKey, period) {
    const table = this.schedule[turnusIndex] || {};
    const row = table[dayKey] || [];
    return period < row.length ? row[period] || "" : "";
  }

  getDayRow(turnusIndex, dayKey) {
    const table = this.schedule[turnusIndex] || {};
    let row = (table[dayKey] || []).slice();
    while (row.length < this.periodsCount) row.push("");
    return row.slice(0, this.periodsCount);
  }

  setScheduleForTurnus(turnusIndex, data) {
    this.schedule[turnusIndex] = data;
  }

  // ------------------------------------------------------------------
  // Predsat (izborni sat prije redovnog početka nastave)
  // ------------------------------------------------------------------
  getPreSubject(turnusIndex, dayKey) {
    const table = this.preSchedule[turnusIndex] || {};
    return table[dayKey] || "";
  }

  setPreScheduleForTurnus(turnusIndex, data) {
    this.preSchedule[turnusIndex] = data;
  }

  // ------------------------------------------------------------------
  // Vrijeme sati i odmora
  // ------------------------------------------------------------------
  getTimeSettings(turnusIndex) {
    return normalizeTimeSettings((this.timeSettings || {})[turnusIndex]);
  }

  setTimeSettings(turnusIndex, settings) {
    if (!this.timeSettings) this.timeSettings = {};
    this.timeSettings[turnusIndex] = normalizeTimeSettings(settings);
  }

  /** Niz { period, start, end, breakAfter? } za sve sate turnusa (vidi buildPeriodSchedule). */
  periodSchedule(turnusIndex) {
    return buildPeriodSchedule(this.getTimeSettings(turnusIndex), this.periodsCount);
  }

  /** Vrijeme završetka nastave za dani dan (na temelju upisanih predmeta), ili null. */
  dayEndTime(turnusIndex, dayKey) {
    const row = this.getDayRow(turnusIndex, dayKey);
    return dayEndTimeLabel(this.getTimeSettings(turnusIndex), row);
  }

  toJSON() {
    return {
      name: this.name,
      turnusNames: this.turnusNames,
      resets: this.resets,
      schedule: this.schedule,
      periodsCount: this.periodsCount,
      timeSettings: this.timeSettings,
      preSchedule: this.preSchedule,
    };
  }

  static fromJSON(d) {
    // Prihvati i "kamelCase" (web format) i "snake_case" (format desktop
    // Python aplikacije) - backup napravljen u jednoj aplikaciji mora se
    // moći uvesti u drugu.
    const rawResets = Array.isArray(d.resets) ? d.resets : [];
    const resets = rawResets
      .map((r) => ({
        dateFrom: r.dateFrom !== undefined ? r.dateFrom : r.date_from,
        turnusIndex: r.turnusIndex !== undefined ? r.turnusIndex : r.turnus_index,
      }))
      // odbaci zapise koji ni nakon toga nemaju ispravan oblik, umjesto da
      // kasnije sruše izračun turnusa za cijelo dijete
      .filter(
        (r) =>
          typeof r.dateFrom === "string" &&
          /^\d{4}-\d{2}-\d{2}$/.test(r.dateFrom) &&
          (r.turnusIndex === 0 || r.turnusIndex === 1)
      );
    return new Child({
      name: d.name,
      turnusNames: d.turnusNames || d.turnus_names || [...DEFAULT_TURNUS_NAMES],
      resets,
      schedule: d.schedule || { 0: {}, 1: {} },
      periodsCount: d.periodsCount || d.periods_count || DEFAULT_PERIODS,
      timeSettings: d.timeSettings || d.time_settings || {},
      preSchedule: d.preSchedule || d.pre_schedule || { 0: {}, 1: {} },
    });
  }
}

class AppData {
  constructor({ children = [], activeChild = null } = {}) {
    this.children = children;
    this.activeChild = activeChild;
  }

  getActive() {
    const found = this.children.find((c) => c.name === this.activeChild);
    if (found) return found;
    return this.children.length ? this.children[0] : null;
  }

  getChild(name) {
    return this.children.find((c) => c.name === name) || null;
  }

  toJSON() {
    return {
      children: this.children.map((c) => c.toJSON()),
      activeChild: this.activeChild,
    };
  }

  static fromJSON(d) {
    return new AppData({
      children: (d.children || []).map(Child.fromJSON),
      activeChild: d.activeChild || d.active_child || null,
    });
  }
}

function weekStatus(today) {
  const monday = isoWeekMonday(today);
  const sunday = addDays(monday, 6);
  const weekNum = isoWeekNumber(today);
  return { monday, sunday, weekNum };
}

// Izvoz za korištenje u drugim modulima (obični <script> - globalni scope)
