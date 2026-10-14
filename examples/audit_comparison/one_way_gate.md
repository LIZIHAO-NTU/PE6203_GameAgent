# One-way Gate / 单向门
Create an offline vanilla HTML/CSS/JS grid game from scratch. No libraries, backend or remote assets.
Fixed ordinary level (x increases right, y down, zero-based):
#####
#PGE#
#..##
#####
P=(1,1), G=(2,1), E=(3,1), # is wall and . is floor.
- Arrow keys move one cell per distinct press; ignore held-key repeat. Walls/out-of-bounds block movement.
- Entering G is allowed ONLY when moving upward from (2,2). Entering G from the left/right/downward is blocked. Once on G, normal exits from the tile are allowed.
- Each legal step increments moves once. Blocked inputs do not change moves.
- Enter E to win; all later movement is ignored until restart.
- #pos displays exactly "x,y"; #moves is a bare integer; #status exactly Playing or Won.
- #restart restores player=(1,1), moves=0, phase=Playing without reload.
- Render distinct walls/gate/player/exit on Canvas or a visible board marked data-game-surface, and explain gate direction.
- Read-only window.__gameTest.getState() returns actual player.x, player.y, moves and phase. No solver or state setter.
