/**
 * Town of Silicon - Main Entry Point
 *
 * Canvas-based, chatbot-centric UI for Town of Salem with AI agents.
 */

import { Game } from './canvas/Game';
import { WebSocketClient } from './api/websocket';

// Initialize canvas
const canvas = document.getElementById('game-canvas') as HTMLCanvasElement;
const ctx = canvas.getContext('2d');

if (!ctx) {
  throw new Error('Canvas 2D context not supported');
}

// Set canvas size to fill window
function resizeCanvas() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
}

resizeCanvas();
window.addEventListener('resize', resizeCanvas);

// Initialize WebSocket connection
const ws = new WebSocketClient('ws://localhost:8000/ws');

// Initialize game
const game = new Game(canvas, ctx, ws);

// Hide loading screen when ready
async function init() {
  const loadingEl = document.getElementById('loading');

  try {
    // Connect to backend
    await ws.connect();
    console.log('Connected to backend');

    // Initialize game
    await game.initialize();
    console.log('Game initialized');

    // Hide loading screen
    if (loadingEl) {
      loadingEl.classList.add('hidden');
    }

    // Start game loop
    game.start();
  } catch (error) {
    console.error('Initialization error:', error);
    if (loadingEl) {
      loadingEl.innerHTML = `
        <div class="loading-text" style="color: #f44336;">Connection Error</div>
        <div style="color: #888; margin-top: 20px;">
          Make sure the backend is running on port 8000
        </div>
        <div style="color: #888; margin-top: 10px; font-size: 12px;">
          Run: cd backend && python main.py
        </div>
      `;
    }
  }
}

// Debug toggle (` key)
window.addEventListener('keydown', (e) => {
  if (e.key === '`') {
    const debugEl = document.getElementById('debug-info');
    if (debugEl) {
      debugEl.classList.toggle('hidden');
    }
  }
});

// Start
init();

// Debug FPS counter
let lastFrame = performance.now();
let frames = 0;

function updateDebugInfo() {
  const now = performance.now();
  frames++;

  if (now - lastFrame >= 1000) {
    const fps = Math.round((frames * 1000) / (now - lastFrame));
    const fpsEl = document.getElementById('fps');
    if (fpsEl) {
      fpsEl.textContent = fps.toString();
    }

    const canvasSizeEl = document.getElementById('canvas-size');
    if (canvasSizeEl) {
      canvasSizeEl.textContent = `${canvas.width}x${canvas.height}`;
    }

    frames = 0;
    lastFrame = now;
  }

  requestAnimationFrame(updateDebugInfo);
}

updateDebugInfo();
