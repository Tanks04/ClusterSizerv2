/* Perzistencija u localStorage (podaci ostaju na uređaju). */
"use strict";

const STORAGE_KEY = "skolskiRasporedData";

function loadData() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return new AppData();
    return AppData.fromJSON(JSON.parse(raw));
  } catch (e) {
    console.error("Greška pri učitavanju podataka:", e);
    return new AppData();
  }
}

function saveData(data) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data.toJSON()));
  } catch (e) {
    console.error("Greška pri spremanju podataka:", e);
  }
}
