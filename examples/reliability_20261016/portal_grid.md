# Portal Shortcut
Build a small offline grid puzzle: a 4-column, 3-row board with coordinates starting at (0,0) in the top left. Start the player at (0,1). Arrow presses move one cell; boundaries block movement. Entering (1,1) immediately teleports the player to (3,0), consuming only one move. The exit is (3,2); reaching it wins and further movement is ignored. No walls or other rules. Restart resets position and move count.

Show rules, player, portal and exit. Mark the board data-game-surface. Use #restart, #moves (bare integer) and #status (Playing/Won). Read-only window.__gameTest.getState() reports real player.x, player.y, moves and phase. Use vanilla local HTML/CSS/JS.
