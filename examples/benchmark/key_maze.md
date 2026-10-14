# Key and Door Maze / 钥匙门迷宫
Build an offline vanilla HTML/CSS/JS grid game, visibly rendered on Canvas or a DOM board marked data-game-surface.
The ordinary fixed level is 5 columns by 4 rows, coordinates x right/y down from zero:
#####
#PDE#
#.K##
#####
# is a wall, P starts at (1,1), D is a locked door at (2,1), E is the exit at (3,1), K is a key at (2,2), . is floor.
- Arrow keys move one cell per distinct keydown; held-key repeat must not cause repeated discrete turns.
- Walls and out-of-bounds moves are blocked. Door is blocked until the key is picked up.
- Walking onto K collects it once. With hasKey=true the door is passable; key remains held.
- Entering E after key pickup wins. #status is exactly Playing or Won.
- Terminal Won ignores movement. #restart resets position, key pickup, door and phase.
- Read-only window.__gameTest.getState() reports real live player.x, player.y, hasKey and phase (Playing/Won).
- Show walls, player, key, door, exit and brief instructions. No solver, state setters, timer, extra levels or external assets.
