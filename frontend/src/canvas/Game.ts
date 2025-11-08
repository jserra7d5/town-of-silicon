/**
 * Main Game class - Canvas-based chatbot-centric UI
 */

import { WebSocketClient } from '../api/websocket';

interface ChatMessage {
  player_id: number;
  player_name: string;
  message: string;
  phase: string;
  day_number: number;
}

interface GameState {
  players: any[];
  current_phase: {
    phase_type: string;
    remaining_time: number;
    duration: number;
  };
  current_day: number;
  all_chat_messages: ChatMessage[];
}

export class Game {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private ws: WebSocketClient;

  private gameState: GameState | null = null;
  private chatMessages: ChatMessage[] = [];
  private currentPhase: string = 'PREGAME';
  private phaseTimeRemaining: number = 0;

  private running = false;
  private lastFrameTime = 0;

  // Layout constants
  private readonly CHAT_WIDTH = 600;
  private readonly CHAT_PADDING = 20;
  private readonly MESSAGE_HEIGHT = 60;
  private readonly PHASE_BAR_HEIGHT = 60;

  constructor(canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D, ws: WebSocketClient) {
    this.canvas = canvas;
    this.ctx = ctx;
    this.ws = ws;

    // Set up WebSocket handlers
    this.setupWebSocketHandlers();
  }

  private setupWebSocketHandlers() {
    this.ws.onGameStateUpdate = (gameState: GameState) => {
      this.gameState = gameState;
      this.chatMessages = gameState.all_chat_messages || [];
      this.currentPhase = gameState.current_phase?.phase_type || 'PREGAME';
      this.phaseTimeRemaining = gameState.current_phase?.remaining_time || 0;
    };

    this.ws.onChatMessage = (message: ChatMessage) => {
      this.chatMessages.push(message);
      // Keep only last 50 messages for display
      if (this.chatMessages.length > 50) {
        this.chatMessages = this.chatMessages.slice(-50);
      }
    };

    this.ws.onPhaseChange = (phase: string, duration: number) => {
      this.currentPhase = phase;
      this.phaseTimeRemaining = duration;
      console.log(`Phase changed to ${phase} (${duration}s)`);
    };
  }

  async initialize() {
    // Request initial game state
    this.ws.send({ type: 'request_game_state', data: {} });

    console.log('Game initialized');
  }

  start() {
    this.running = true;
    this.lastFrameTime = performance.now();
    this.gameLoop();
  }

  stop() {
    this.running = false;
  }

  private gameLoop = () => {
    if (!this.running) return;

    const now = performance.now();
    const deltaTime = (now - this.lastFrameTime) / 1000; // Convert to seconds
    this.lastFrameTime = now;

    // Update
    this.update(deltaTime);

    // Render
    this.render();

    // Next frame
    requestAnimationFrame(this.gameLoop);
  };

  private update(deltaTime: number) {
    // Update phase timer
    if (this.phaseTimeRemaining > 0) {
      this.phaseTimeRemaining -= deltaTime;
      if (this.phaseTimeRemaining < 0) {
        this.phaseTimeRemaining = 0;
      }
    }
  }

  private render() {
    const { canvas, ctx } = this;

    // Clear canvas
    ctx.fillStyle = '#2a2a2a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Render phase bar at top
    this.renderPhaseBar();

    // Render chat in center
    this.renderChat();

    // Render player list on right
    this.renderPlayerList();
  }

  private renderPhaseBar() {
    const { ctx, canvas } = this;
    const barHeight = this.PHASE_BAR_HEIGHT;

    // Background
    ctx.fillStyle = '#1a1a1a';
    ctx.fillRect(0, 0, canvas.width, barHeight);

    // Phase name
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 24px sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';

    const phaseText = this.currentPhase.replace(/_/g, ' ');
    ctx.fillText(phaseText, 20, barHeight / 2);

    // Timer
    if (this.phaseTimeRemaining > 0) {
      ctx.fillStyle = '#4CAF50';
      ctx.font = '20px monospace';
      ctx.textAlign = 'right';

      const minutes = Math.floor(this.phaseTimeRemaining / 60);
      const seconds = Math.floor(this.phaseTimeRemaining % 60);
      const timeText = `${minutes}:${seconds.toString().padStart(2, '0')}`;

      ctx.fillText(timeText, canvas.width - 20, barHeight / 2);
    }

    // Day number
    if (this.gameState) {
      ctx.fillStyle = '#888';
      ctx.font = '18px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(`Day ${this.gameState.current_day}`, canvas.width / 2, barHeight / 2);
    }

    // Border
    ctx.strokeStyle = '#444';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, barHeight);
    ctx.lineTo(canvas.width, barHeight);
    ctx.stroke();
  }

  private renderChat() {
    const { ctx, canvas } = this;
    const startY = this.PHASE_BAR_HEIGHT + this.CHAT_PADDING;
    const chatWidth = this.CHAT_WIDTH;
    const chatX = (canvas.width - chatWidth) / 2;

    // Chat background
    ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
    ctx.fillRect(
      chatX - this.CHAT_PADDING,
      startY - this.CHAT_PADDING,
      chatWidth + this.CHAT_PADDING * 2,
      canvas.height - startY
    );

    // Render messages (newest at bottom)
    const maxMessages = Math.floor((canvas.height - startY - this.CHAT_PADDING * 2) / this.MESSAGE_HEIGHT);
    const messagesToShow = this.chatMessages.slice(-maxMessages);

    let y = startY;

    for (const message of messagesToShow) {
      this.renderChatMessage(message, chatX, y, chatWidth);
      y += this.MESSAGE_HEIGHT;
    }

    // No messages indicator
    if (messagesToShow.length === 0) {
      ctx.fillStyle = '#666';
      ctx.font = '16px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillText('No messages yet...', canvas.width / 2, startY + 100);
    }
  }

  private renderChatMessage(message: ChatMessage, x: number, y: number, width: number) {
    const { ctx } = this;

    // Player name
    ctx.fillStyle = '#4CAF50';
    ctx.font = 'bold 14px sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText(`${message.player_name}:`, x, y);

    // Message text
    ctx.fillStyle = '#ffffff';
    ctx.font = '14px sans-serif';

    // Word wrap
    const words = message.message.split(' ');
    let line = '';
    let lineY = y + 20;

    for (const word of words) {
      const testLine = line + word + ' ';
      const metrics = ctx.measureText(testLine);

      if (metrics.width > width - 20 && line !== '') {
        ctx.fillText(line, x, lineY);
        line = word + ' ';
        lineY += 18;
      } else {
        line = testLine;
      }
    }

    if (line !== '') {
      ctx.fillText(line, x, lineY);
    }

    // Separator
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, y + this.MESSAGE_HEIGHT - 5);
    ctx.lineTo(x + width, y + this.MESSAGE_HEIGHT - 5);
    ctx.stroke();
  }

  private renderPlayerList() {
    const { ctx, canvas } = this;
    const listWidth = 250;
    const listX = canvas.width - listWidth - 20;
    const startY = this.PHASE_BAR_HEIGHT + 20;

    if (!this.gameState || !this.gameState.players) {
      return;
    }

    // Background
    ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
    ctx.fillRect(listX - 10, startY - 10, listWidth + 20, canvas.height - startY);

    // Title
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 18px sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText('Players', listX, startY);

    // Player list
    let y = startY + 40;

    for (const player of this.gameState.players) {
      const playerName = player.name;
      const isAlive = player.is_alive;
      const isHuman = player.is_human;

      // Status indicator
      ctx.fillStyle = isAlive ? '#4CAF50' : '#f44336';
      ctx.beginPath();
      ctx.arc(listX, y + 8, 5, 0, Math.PI * 2);
      ctx.fill();

      // Player name
      ctx.fillStyle = isAlive ? '#ffffff' : '#666';
      ctx.font = isHuman ? 'bold 14px sans-serif' : '14px sans-serif';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      ctx.fillText(playerName + (isHuman ? ' (You)' : ''), listX + 15, y);

      y += 25;
    }
  }
}
