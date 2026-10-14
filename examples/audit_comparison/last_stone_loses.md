# Last Stone Loses / 取走最后一颗者输
Create an offline vanilla HTML/CSS/JS game for TWO LOCAL players A and B, no AI or networking.
Initial stones=5, current player=A, winner unset, phase=Playing.
- #take1 / #take2 remove exactly 1 / 2 stones if that many remain and phase=Playing.
- Oversized takes do NOTHING, including not changing turns.
- If stones remain after a legal take, alternate the current player.
- The player taking the LAST stone LOSES; the OTHER player wins. Do NOT apply normal last-taker-wins rules.
- On finishing, retain the losing actor as current player. Further take buttons do nothing.
- #stones is a bare integer; #turn exactly A/B; #winner exactly "-" before finish and the winning A/B afterwards; #status exactly Playing/Finished.
- #restart resets all fields without reloading. Show rules and a visible board marked data-game-surface.
- Read-only window.__gameTest.getState() returns actual stones, currentPlayer, winner and phase. No hidden state setters, templates or libraries.
