/**
 * Main Game class - handles canvas rendering and game loop.
 *
 * Layout (chatbot-centric):
 * ┌─────────────────────────────────────────────────┐
 * │ [Phase Banner]          NIGHT 3                 │
 * ├──────┬─────────────────────────────┬────────────┤
 * │      │                             │            │
 * │ Left │      CHAT (Center)          │   Right    │
 * │Action│   ┌─────────────────┐       │  Actions   │
 * │Buttons│   │ Player 3: I am │       │  Buttons   │
 * │      │   │ the Sheriff!    │       │            │
 * │[Vote]│   │                 │       │  [Target]  │
 * │      │   │ Player 7: Vote  │       │  [Ability] │
 * │[Whis]│   │ Player 5        │       │            │
 * │      │   │                 │       │  [Submit]  │
 * │      │   │ > Type message_ │       │            │
 * │      │   └─────────────────┘       │            │
 * │      │                             │            │
 * └──────┴─────────────────────────────┴────────────┘
 */

import { ChatRenderer } from './ChatRenderer';
import { ButtonPanel } from './ButtonPanel';
import { PhaseIndicator } from './PhaseIndicator';
import { WebSocketClient } from '../api/websocket';

export interface GameState {
  phase: string;
  dayNumber: number;
  nightNumber: number;
  playerRole: string | null;
  chatMessages: ChatMessage[];
  players: Player[];
}

export interface ChatMessage {
  id: number;
  sender: string;
  content: string;
  timestamp: number;
  isWhisper?: boolean;
}

export interface Player {
  id: number;
  name: string;
  isAlive: boolean;
  role?: string;
}

export class Game {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private ws: WebSocketClient;
  private running = false;

  // UI Components
  private chatRenderer: ChatRenderer;
  private leftButtons: ButtonPanel;
  private rightButtons: ButtonPanel;
  private phaseIndicator: PhaseIndicator;

  // Game state
  private state: GameState = {
    phase: 'pregame',
    dayNumber: 0,
    nightNumber: 0,
    playerRole: null,
    chatMessages: [],
    players: []
  };

  // Layout dimensions
  private readonly BUTTON_PANEL_WIDTH = 180;
  private readonly PHASE_BANNER_HEIGHT = 60;

  constructor(canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D, ws: WebSocketClient) {
    this.canvas = canvas;
    this.ctx = ctx;
    this.ws = ws;

    // Initialize UI components
    this.phaseIndicator = new PhaseIndicator();

    this.chatRenderer = new ChatRenderer(
      this.getChatBounds(),
      this.onChatInput.bind(this)
    );

    this.leftButtons = new ButtonPanel(
      this.getLeftButtonsBounds(),
      'left'
    );

    this.rightButtons = new ButtonPanel(
      this.getRightButtonsBounds(),
      'right'
    );

    this.setupEventListeners();
    this.setupWebSocketHandlers();
  }

  async initialize(): Promise<void> {
    // Request initial game state from backend
    this.ws.send('init_game', {});

    // Wait for game state
    return new Promise((resolve) => {
      const handler = (data: any) => {
        this.state = data;
        resolve();
      };
      this.ws.on('game_state', handler);
    });
  }

  start(): void {
    this.running = true;
    this.gameLoop();
  }

  stop(): void {
    this.running = false;
  }

  private gameLoop(): void {
    if (!this.running) return;

    // Clear canvas
    this.ctx.fillStyle = '#2a2a2a';
    this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

    // Render UI components
    this.renderPhase();
    this.renderChat();
    this.renderButtons();

    // Continue loop
    requestAnimationFrame(() => this.gameLoop());
  }

  private renderPhase(): void {
    const bounds = {
      x: 0,
      y: 0,
      width: this.canvas.width,
      height: this.PHASE_BANNER_HEIGHT
    };

    this.phaseIndicator.render(this.ctx, bounds, this.state);
  }

  private renderChat(): void {
    const bounds = this.getChatBounds();
    this.chatRenderer.render(this.ctx, bounds, this.state.chatMessages);
  }

  private renderButtons(): void {
    // Left panel (vote, whisper, etc.)
    this.leftButtons.render(this.ctx, this.state);

    // Right panel (night actions, abilities)
    this.rightButtons.render(this.ctx, this.state);
  }

  private getChatBounds() {
    return {
      x: this.BUTTON_PANEL_WIDTH,
      y: this.PHASE_BANNER_HEIGHT,
      width: this.canvas.width - (this.BUTTON_PANEL_WIDTH * 2),
      height: this.canvas.height - this.PHASE_BANNER_HEIGHT
    };
  }

  private getLeftButtonsBounds() {
    return {
      x: 0,
      y: this.PHASE_BANNER_HEIGHT,
      width: this.BUTTON_PANEL_WIDTH,
      height: this.canvas.height - this.PHASE_BANNER_HEIGHT
    };
  }

  private getRightButtonsBounds() {
    return {
      x: this.canvas.width - this.BUTTON_PANEL_WIDTH,
      y: this.PHASE_BANNER_HEIGHT,
      width: this.BUTTON_PANEL_WIDTH,
      height: this.canvas.height - this.PHASE_BANNER_HEIGHT
    };
  }

  private setupEventListeners(): void {
    // Mouse clicks
    this.canvas.addEventListener('click', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      // Check button clicks
      this.leftButtons.handleClick(x, y);
      this.rightButtons.handleClick(x, y);
      this.chatRenderer.handleClick(x, y);
    });

    // Keyboard input
    window.addEventListener('keydown', (e) => {
      this.chatRenderer.handleKeyPress(e);
    });
  }

  private setupWebSocketHandlers(): void {
    // Chat messages
    this.ws.on('chat_message', (data) => {
      this.state.chatMessages.push(data);
    });

    // Game state updates
    this.ws.on('game_state_update', (data) => {
      this.state = { ...this.state, ...data };
    });

    // Phase changes
    this.ws.on('phase_change', (data) => {
      this.state.phase = data.phase;
      this.state.dayNumber = data.dayNumber;
      this.state.nightNumber = data.nightNumber;
    });
  }

  private onChatInput(message: string): void {
    // Send chat message to backend
    this.ws.send('send_message', {
      content: message
    });
  }
}
