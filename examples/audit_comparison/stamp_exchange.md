# Stamp Exchange / 邮票兑换
Create an offline vanilla HTML/CSS/JS DOM game with a visible board marked data-game-surface.
Initial coins=7, stamps=0, delivered=0, phase=Playing.
- #earn adds exactly 2 coins per click while Playing.
- #buy costs 3 coins and adds 1 stamp only when coins>=3 and Playing. Otherwise do nothing.
- #deliver consumes exactly 2 stamps and adds 1 delivered only when stamps>=2 and Playing. Insufficient stamps: no change.
- One delivered parcel wins immediately. After Won all earn/buy/deliver clicks do nothing, even with remaining coins.
- #coins, #stamps, #delivered display bare integers; #status exactly Playing or Won.
- #restart restores ALL initial resources and phase in every state.
- Show costs, delivery goal and short instructions. No passive income, timers, solvers, external assets or libraries.
- Provide read-only window.__gameTest.getState() of actual coins, stamps, delivered and phase. No setters.
