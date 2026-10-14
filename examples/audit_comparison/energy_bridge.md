# Energy Bridge / 能量桥
Create a vanilla offline HTML/CSS/JS grid game. Zero-based x right/y down. Ordinary fixed level:
#####
#PBE#
#.S##
#####
P starts (1,1), bridge tile B=(2,1), exit E=(3,1), switch S=(2,2), # walls, . floor.
Initial energy=5, bridgeOpen=false, phase=Playing.
- Arrow keys move one cell per distinct press, ignore repeat. Legal movement costs exactly 1 energy. Walls/out-of-bounds/closed bridge block movement without cost.
- B is passable only when bridgeOpen=true.
- Space toggles bridgeOpen ONLY while standing on S and Playing, costs 1 energy. Space elsewhere does nothing without cost.
- After any successful energy-consuming action: entering E wins FIRST, even if energy just reached zero. Otherwise energy=0 loses. Never let energy become negative.
- Won/Lost ignore ALL arrow/Space input. No passive recharge or timer.
- #pos exactly "x,y"; #energy a bare integer; #bridge exactly Open/Closed; #status exactly Playing/Won/Lost.
- #restart restores player, energy, bridge and phase in every state.
- Draw walls/player/bridge/switch/exit distinctly on Canvas or a visible board marked data-game-surface; show instructions.
- Read-only window.__gameTest.getState() returns actual player.x/player.y, energy, bridgeOpen and phase. No solver or state setters.
