# Minimal Brick Breaker / 打砖块
Create a vanilla offline HTML/CSS/JS game with a visible 480x360 2D Canvas.
Prioritize correct continuous movement, collision and reset logic over visual effects.

- Paddle starts centered at x=240, near y=330, width 90. Left/right arrows move it continuously, clamped inside the canvas.
- Ball starts at (240,250), radius 6, initial velocity (0,-180) pixels/second.
- Three non-overlapping bricks at x=160,210,260, each width 40 height 18, top y=60.
- Ball bounces from side/top walls and paddle; on hitting a brick, remove that brick once and add 10 points.
- Paddle rebounds may change horizontal velocity according to hit offset, so all bricks are reachable in ordinary play.
- Missing the paddle loses one of 3 lives and resets the ball/paddle; no duplicate timers.
- Win when all bricks are removed; lose when no lives remain. Terminal states stop physics.
- #start starts/resumes play, #pause pauses it, #restart restores initial ready state, score and lives.
- #status is exactly Ready/Playing/Paused/Won/Lost. #score and #lives display bare integers.
- Pause freezes ball position and rule updates. Restart also works while paused or terminal.
- Provide a read-only window.__gameTest.getState() snapshot of real state with at least phase, score, lives, paddle.x and ball.y; no setters or test-only behavior.
- Clear instructions, simple colored shapes, no audio or external assets.
