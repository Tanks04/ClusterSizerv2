# DartsBro — Game Manual

🇭🇷 **Hrvatski:** [MANUAL.md](MANUAL.md)

## X01

Choose **301, 501, 701, 901, or 1001** and either Double Out or Master Out. After each visit, enter the total score of the three darts. A bust restores the score to its value before that visit.

When the remaining score is **60 or lower**, PikadoBro automatically treats the visit as a checkout phase. From **61 to 170**, you can mark **CHECKOUT ATTEMPT** when you are actually throwing for an out. When the leg is finished, the app asks which dart completed the checkout.

Maximum visits are: 301 = 10, 501 = 15, 701 = 18, 901 = 21, 1001 = 24.

## High Score

Choose **7, 8, or 15 rounds**. Enter the total score of all three darts after every round. The goal is simply to score as many points as possible.

## Split Score

Start on **40 points**. Targets are:

`15 → 16 → Double → 17 → 18 → Triple → 19 → 20 → Bull`

For number rounds, enter the result made on the requested target. For Double and Triple rounds, enter the actual points scored on that ring type. If all three darts miss the required target, the current score is halved. Odd scores are rounded in the player's favour, for example **75 → 38**.

**Split Score Back** uses the same rules in reverse order.

## Round the World

Choose **Singles, Doubles, or Triples** and work through targets 1 to 20. The session is limited to **40 visits**.

Enter how many of the three darts hit the exact requested ring. Entering **0** keeps you on the same target. Entering 1, 2, or 3 advances exactly one target.

The optional final Bull depends on the mode:

- Singles: **Bull 25**
- Doubles: **DB 50**
- Triples: **Bull 25 or DB 50**

## Checkout Trainer

Checkout Trainer is a repeated finishing drill; a miss does not end the session. Training can be limited by number of rounds or by time.

- **PDC** — rotates through 40, 32, 36, 50, 20, 8, 4, 16, and 24.
- **Random** — generates random targets from 2 to 40.
- **Manual** — enter one or more targets and PikadoBro rotates through them.
- **Crazy** — uses even checkout targets and changes the target automatically after a random 5–15 second interval with a beep/flash cue.

For each round, record **HIT** or **MISS**. PikadoBro tracks rounds, hits, misses, and checkout percentage.

## Checkout Challenge

Checkout Challenge is progressive route training with recommended finishing paths.

### 2 Dart Finishes

Work upward through finishable scores from 2 to 100. You must check out the current target before advancing. Scores that cannot be finished in two darts are skipped.

### 3 Dart Finishes

Work through valid three-dart finishes from 99 to 170. Score 100 belongs to the 2 Dart discipline, and standard bogey numbers are skipped.

PikadoBro shows a preferred practical route and, where useful, a sensible alternative. It intentionally avoids exotic routes that are mathematically possible but poor training choices.

Record only **HIT** or **MISS**. A miss keeps you on the same target. Progress is saved automatically. **New Cycle** starts again from the beginning while preserving previous cycle history for comparison. History can be deleted separately.

## Bob's 27

Start on **27 points** and throw at D1, D2 ... D20, then Bull. You get three darts at each target.

Each successful double adds its double value for every hit. If all three darts miss the target, that double's value is subtracted once. If the score reaches **0 or below**, the game ends.

## Speed Game

Speed Game is target scoring under time pressure. The complete training session lasts up to **5 minutes**. Each target also has its own timer:

- **Easy:** 60 seconds, targets 1–60
- **Normal:** 40 seconds, targets 1–100
- **Pro:** 30 seconds, targets 1–180
- **King:** 25 seconds, always 150 as **DB · DB · DB**

Press GO to start. Record **HIT** or **MISS**. If the per-target timer expires, PikadoBro records a timeout miss and immediately starts a new target while the overall five-minute session continues.

PikadoBro tracks attempts, hit rate, misses, timeout rate, best streak, and time needed for successful hits.

## FixTheThing

FixTheThing is focused practice for one specific number or ring.

### Ručno

Choose a target from **1–20, D1–D20, T1–T20, B, or DB** and throw **10 rounds / 30 darts**.

Enter every dart exactly as it landed. `0` means a complete miss. Tap **D** or **T** before a number to enter a double or triple. **B** and **DB** are direct buttons.

If the target is a plain number, any ring on that number counts as one hit. For target 20, **S20, D20, and T20** all count as hits. If the target is **D20** or **T20**, only that exact ring counts.

To reduce tapping, PikadoBro shows large direct shortcuts for the selected target and smaller shortcuts for the two physical neighbouring numbers on a standard dartboard. The full keypad remains available for every other result.

During the session, live hit totals and percentages are deliberately hidden. The screen says **CONCENTRATE!** and the full statistics appear only after the 30th dart.

End-of-session statistics include hit rate, perfect rounds (3/3 hits), blank rounds (0/3 hits), and best hit streak.

### Automatski

PikadoBro looks for weak targets in compatible training statistics and suggests something worth practising.

Automatski unlocks after at least **10 relevant sessions** and requires at least **15 recorded darts** on a candidate target. PikadoBro only uses sufficiently precise training data. It does not infer individual dart misses from X01 visit totals because those totals do not reveal where each dart landed.

## Statistics and Backup / Restore

Open **Statistics** from the home screen to view stored results by discipline.

**Backup / Restore** exports PikadoBro's local data to a JSON file or restores a previous JSON backup. Restore replaces the current local PikadoBro data with the contents of the selected backup.

## Undo and hidden game menu

**Undo can only undo the most recently entered visit once.** It is not a history navigator. After using Undo, it remains disabled until a new score/result is entered.

During active play, double-click or double-tap an empty part of the game screen to open the hidden menu with Resume, Undo, Restart, End, and Home controls.

### Moj trening / AI Mode beta

This lives inside FixTheThing. Choose 10, 15, 20, 30 or 45 minutes. A workout can combine FixTheThing targets with complete training disciplines. Example: FixTheThing 20 → X01 301 Double Out → FixTheThing Bull → Split Score Back. Every block can be changed, removed or added before the workout starts, and nothing begins until you confirm the plan. When enough reliable statistics exist, DartsBro gives priority to weaker targets; without enough data it offers a ready-made balanced mix. The maximum planned workout length is 45 minutes.

## Data / Backup

Alongside JSON backup and restore, **Clear all local data** removes all DartsBro data stored on the device. The action requires confirmation and cannot be undone.
