# 🎯 DartsBro

**Current test version: v0.32 TEST**

🇭🇷 **Hrvatski:** [Otvori README.md](README.md)

**DartsBro** (Croatian UI: **PikadoBro**) is a simple single-player darts training app built for real practice at the board — without unnecessary menus, ads, accounts, or distractions.

It runs in the browser and can be installed as a PWA. The interface is designed primarily for phones and tablets, while desktop works well for statistics, backup/restore, and reference use. Training data stays local on the device.

## Games

- **X01** — 301 / 501 / 701 / 901 / 1001, Double Out or Master Out
- **High Score** — 7 / 8 / 15 rounds
- **Split Score** and **Split Score Back**
- **Round the World** — Singles / Doubles / Triples + optional Bull
- **Checkout Trainer** — PDC / Random / Manual / Crazy
- **Checkout Challenge** — 2 Dart / 3 Dart Finishes with recommended checkout routes
- **Speed Game** — Easy 60 s / Normal 40 s / Pro 30 s / King 25 s; sessions last up to 5 minutes
- **Bob's 27**
- **FixTheThing** — Ručno / Automatski focused target practice

## How it works

Choose a game, set up the training session, throw your darts, and enter the result manually. DartsBro handles game flow and statistics while keeping the active training screen intentionally minimal.

During most games, **double-click / double-tap an empty part of the game screen** to open the hidden game menu with Resume, Undo, Restart, End, and Home controls.

Detailed rules for every training mode are in [MANUAL_EN.md](MANUAL_EN.md). Testing notes are in [TESTING.md](TESTING.md).

## FixTheThing

**Ručno:** choose a target (1–20, D1–D20, T1–T20, B or DB) and throw 10 rounds / 30 darts. Enter every dart exactly as it landed. `0` is a complete miss. Tap D or T before a number to enter a double/triple. B and DB are direct buttons.

If the target is a plain number, any ring on that number counts as one hit: for target 20, S20, D20 and T20 are all hits. If the target is D20 or T20, only that exact ring counts.

For faster scoring, the active screen offers direct shortcuts for the selected target and its two physical neighbours on a standard dartboard. Live hit totals and percentages are hidden during the session so the player can stay focused on throwing; the full result appears at the end.

**Automatski:** DartsBro looks for weak targets in compatible training statistics. It unlocks after at least 10 relevant sessions and requires at least 15 recorded darts on a candidate target. It does not infer individual dart misses from X01 totals because those data are not precise enough.

**Moj trening (AI Mode beta):** choose a 10 / 15 / 20 / 30 / 45 minute workout. A workout is no longer limited to FixTheThing targets: each block can be a FixTheThing target or a complete training discipline such as X01 301 DO, High Score, Split Score / Back, Round the World, Bob's 27, Checkout Trainer or Speed Game. The full plan is always visible and editable, and the player must confirm it before starting. DartsBro can suggest a balanced starter mix and, once enough reliable statistics exist, give priority to weaker targets. The maximum planned workout length is 45 minutes.

## Statistics and backup

DartsBro stores discipline statistics locally in the browser. Built-in **JSON Backup / Restore** can be used to make a safety copy or move PikadoBro data to another browser/device.

Clearing browser/site data may remove local DartsBro history unless a backup was created first.

## Languages and devices

The app interface supports **Croatian and English**. DartsBro is touch-first, but works on desktop as well. On supported devices it can be installed as a PWA and opened like a normal app.

## Status

**Test build v0.29.** All games listed above are active. DartsBro is still being tested in real training sessions, so rules, statistics, and UX details may change between test builds.


## Support development

The code, app, and idea are offered for free. If you enjoy DartsBro and it helps your practice, you can send the author a few EUR for a beer or whisk(e)y ❤️ — it may provide extra motivation to turn another idea into a feature.

**Revolut:** https://revolut.me/@ivan50ba6

### Privacy and clearing data

DartsBro stores its data locally on the device. Under **Data / Backup**, **Clear all local data** permanently removes statistics, workouts, settings and the active game. The installed PWA remains installed until the user removes it.

### Responsive gameplay screen

v0.32 fits active gameplay to the actual visible viewport. On phones, quick-score buttons use a compact layout while the keypad and UNDO remain inside the visible screen to reduce accidental scrolling during practice.

### v0.32 verified bug fixes

Alongside the responsive gameplay work from v0.31, v0.32 fixes Master Out bust when leaving 1, Resume labels for Speed Game and Checkout Challenge, timers continuing after returning Home, backup version metadata, HR/EN backup filenames, restored active-game routing, and AudioContext cleanup after Crazy-mode beeps.
