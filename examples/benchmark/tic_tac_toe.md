# Two-player Tic-Tac-Toe / 双人井字棋
Create a small offline browser game from an empty directory using vanilla HTML/CSS/JS.
Prioritize correct rules and reliable startup over artwork. No backend, dependencies or AI opponent.

- A 3x3 DOM board, marked data-game-surface, with buttons #cell-0 through #cell-8 in row-major order.
- Two local players alternate X then O. Empty cells display empty text; occupied cells show X/O.
- Clicking an occupied cell does nothing, including not changing turns.
- #status displays exactly "Turn: X" or "Turn: O" during play, "Winner: X"/"Winner: O" for a winning row, column or diagonal, and "Draw" for a full non-winning board.
- Check victory before draw. After victory/draw, further cell clicks cannot change the board.
- #restart resets all cells, current player and end state without reloading the page.
- Visible instructions. Simple readable layout is sufficient. Do not add pause or continuous movement.
