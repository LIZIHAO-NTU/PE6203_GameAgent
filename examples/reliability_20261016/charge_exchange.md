# Crystal Workshop
Build an offline browser game: start with 7 energy and no crystals. Charge adds 2 energy, capped at 9. Craft costs 3 energy and gives one crystal, but has no effect if energy is insufficient. Three crystals wins; after winning both actions are ignored. Restart restores the initial state. Show the rules and counters. No timer, movement, levels or extra rules.

Use #charge, #craft and #restart buttons; #energy and #crystals show bare integers. Mark the game surface data-game-surface. The read-only window.__gameTest.getState() reports real energy, crystals and phase (Playing/Won). Use vanilla local HTML/CSS/JS.
