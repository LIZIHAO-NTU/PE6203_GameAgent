# Tiny Sokoban / 推箱子
Build a vanilla offline HTML/CSS/JS game; simple DOM or Canvas rendering is fine.
Use a 5x5 grid with x increasing right and y increasing down, zero-based coordinates.
Every outer cell (x=0/4 or y=0/4) is a wall. All nine inner cells are floor.
Initial player=(1,2), crate=(2,2), goal=(3,2). Draw the player, crate, goal and walls distinctly.

- Arrow keys move one cell per key press, never continuous coordinate movement.
- Walls block the player. The player can push the crate only if its next cell is free floor.
- No pulling, wall crossing or pushing a crate into a wall. Blocked actions do not increase moves.
- Each legal walk or push increments the move count by one.
- A crate reaching the goal wins; after winning, arrows cannot change state.
- #restart restores the exact initial state.
- Public visible text labels: #player-pos is "x,y", #crate-pos is "x,y", #moves is a bare integer, #status is exactly "Playing" or "Won".
- A visible surface marked data-game-surface or a drawn canvas, plus short controls instructions.
Correct grid transitions and pushing rules matter more than decoration. No solver, teleport or test-only controls.
