# Six-card Memory Pairs / 记忆配对
Build an offline vanilla browser game, using a visible DOM board marked data-game-surface.
Six card buttons #card-0 through #card-5 have fixed underlying values [A,B,A,C,B,C].
This fixed layout is part of the ordinary game specification, not a hidden test mode.

- Face-down cards display "?" and data-state="hidden". Revealed cards display their letter and data-state="revealed".
- A matching pair stays visible with data-state="matched" and adds one to #matches (bare integer).
- A mismatched pair stays visible for 500ms, then both hide. During this delay, ignore third-card clicks.
- Clicking an already revealed or matched card does nothing and cannot count the same pair twice.
- #status is exactly "Playing" initially, "Won" after all three pairs match.
- #restart cancels any pending hide timer and resets cards, selection, match count and status.
- Never show all hidden answers, add a solver or change deck values to pass tests.
- Short instructions and readable plain styling; no continuous movement, pause button or extra levels.
