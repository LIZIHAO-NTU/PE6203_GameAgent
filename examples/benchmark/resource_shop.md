# Resource Shop / 资源升级小游戏
Build an offline vanilla HTML/CSS/JS game with a visible DOM board marked data-game-surface.
- Initial coins=10, power=1, phase=Playing. #coins and #power show bare integers; #status shows Playing or Won exactly.
- #earn adds exactly 1 coin per click while Playing.
- #buy costs exactly 6 coins and adds exactly 1 power only if coins>=6 and phase=Playing.
- Insufficient coins: ignore the purchase without changing any value. Controls may remain enabled so ignored actions can be checked.
- Reach power=3 to win immediately. After Won, earn and buy clicks do nothing.
- #restart restores coins=10, power=1, phase=Playing and works in every phase.
- Display the price, winning goal and short instructions. No passive income, timers, networking, libraries or hidden helpers.
- Read-only window.__gameTest.getState() returns the real live coins, power and phase.
