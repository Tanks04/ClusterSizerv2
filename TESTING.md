# PikadoBro — Testing Notes

Thanks for testing PikadoBro / DartsBro! 🎯

Please use it as a real darts training app, not only by clicking through screens. Useful bug reports include:

- incorrect scoring or game rules
- Undo behaving unexpectedly
- Speed Game timers freezing, skipping, or counting incorrectly
- Checkout Trainer / Challenge offering or recording the wrong result
- a session disappearing after refresh/restart
- Backup / Restore failing to restore statistics
- controls that are difficult to use on a phone or tablet
- Croatian/English text appearing in the wrong language

For a bug report, please include: **game + what you did + what happened + what you expected**. A screenshot is very helpful.

PikadoBro data is stored locally in the browser/device. Clearing site/browser data can delete training history unless a JSON backup was created first.

## FixTheThing checks

- Ručno target 20 + `T1, 20, 5` must result in 1/3 hits.
- Target 20: S20, D20, and T20 must all count as hits.
- Target D20/T20: only the exact requested ring counts.
- Target 20 must offer shortcuts for S20/D20/T20 and neighbouring numbers 5 and 1.
- During the session, there must be no live hit total or percentage.
- Shortcut buttons must enter exactly one dart and the full keypad must still work.
- Finish all 10 rounds and verify that FixTheThing appears in Statistics.
- Automatski must stay locked until enough relevant training data exists; compatible Round the World / Bob's 27 / FixTheThing data may contribute.

## Data reset test

Create some statistics, make a JSON backup, use **Clear all local data**, verify the app returns empty, then restore the backup and verify the statistics return.

## Responsive gameplay test

On a phone and a tablet, open X01 and High Score. Verify all 9 quick-score buttons are visible, the keypad and UNDO are reachable without page scrolling, and rotating/resizing the screen does not leave controls outside the viewport.

## v0.32 regression checks

- X01 Master Out: leaving exactly 1 must be a bust.
- Start Speed Game, return Home through the game menu, wait longer than the target timer: Home must remain visible; Resume must show `Speed Game · <mode>`.
- Start Checkout Challenge, return Home: Resume must show the current target, not `undefined`.
- In timed/Crazy Checkout, return Home: no timer/modal may pull the app back into the game.
- Export backup in HR and EN: filename should start with PikadoBro / DartsBro respectively, and JSON `version` must match the visible app version.
- Restore a backup containing an active game: the restored active game should open.
