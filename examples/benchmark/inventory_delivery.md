# Inventory Delivery / 库存配送
Create an offline vanilla HTML/CSS/JavaScript DOM game with a visible board marked data-game-surface.
- Initial coins=5, cargo=0, stock=2, delivered=0, phase=Playing.
- #coins, #cargo, #stock, #delivered display bare integers. #status displays exactly Playing or Won.
- #buy buys one item for 2 coins only while Playing, stock>0, cargo=0, coins>=2. Reduce coins by 2, stock by 1, and set cargo=1.
- Carrying capacity is one item. A blocked purchase changes nothing.
- #deliver while Playing and cargo=1 consumes cargo and increments delivered by 1. No payment/reward.
- Empty delivery changes nothing. Two deliveries win immediately; after Won, buy/deliver do nothing.
- #restart restores all initial values in every phase. Show rules and counters clearly.
- Provide read-only window.__gameTest.getState() of the actual live fields. No test-only controls, automation, backend, timers, libraries or remote assets.
