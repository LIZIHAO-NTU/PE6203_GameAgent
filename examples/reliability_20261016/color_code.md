# Color Code
Build an offline button puzzle. The visible target sequence is Red, Blue, Green. Click the color buttons in that order to win. A correct click advances progress; any incorrect click resets progress to zero and adds one mistake (it does not also start a new sequence). After winning ignore color clicks. Restart resets progress and mistakes. Show the target, short rules and counters. No randomness, timer or hidden information.

Use buttons #red, #blue, #green, #restart; #progress and #mistakes display bare integers. Mark the game surface data-game-surface. Read-only window.__gameTest.getState() reports real progress, mistakes and phase (Playing/Won). Use vanilla local HTML/CSS/JS.
