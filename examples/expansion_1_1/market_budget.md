# Tiny Market
Build an offline resource game. Start with 5 credits and zero items. Earn adds 3 credits capped at 8. Buy costs 4 credits and adds one item, doing nothing when funds are insufficient. Two items wins; after winning earn/buy do nothing. Restart restores initial state. Show English rules and counters. No timer, movement or extra upgrades.
Use #earn, #buy, #restart, #credits and #items (bare integers), with data-game-surface. Read-only window.__gameTest.getState() returns real credits, items and phase (Playing/Won). Vanilla local HTML/CSS/JS only.
