/**
 * Interactive Game class - Canvas-based UI with full player interaction
 */

import { WebSocketClient } from '../api/websocket';

interface ChatMessage {
  player_id: number;
  player_name: string;
  message: string;
  phase: string;
  day_number: number;
  is_whisper?: boolean;
}

interface Player {
  player_id: number;
  name: string;
  is_alive: boolean;
  is_human: boolean;
  role?: {
    name: string;
    abilities?: any[];
  };
}

interface GameState {
  players: Player[];
  current_phase: {
    phase_type: string;
    remaining_time: number;
    duration: number;
  };
  current_day: number;
  all_chat_messages: ChatMessage[];
  accused_player_id?: number;
}

interface Button {
  x: number;
  y: number;
  width: number;
  height: number;
  text: string;
  callback: () => void;
  enabled?: boolean;
}

export class InteractiveGame {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private ws: WebSocketClient;

  private gameState: GameState | null = null;
  private chatMessages: ChatMessage[] = [];
  private currentPhase: string = 'PREGAME';
  private phaseTimeRemaining: number = 0;

  private running = false;
  private lastFrameTime = 0;

  // UI State
  private chatInput = '';
  private chatInputActive = false;
  private selectedPlayer: number | null = null;
  private selectedAction: string | null = null;

  // Buttons
  private buttons: Button[] = [];

  // Layout constants
  private readonly CHAT_WIDTH = 600;
  private readonly CHAT_PADDING = 20;
  private readonly MESSAGE_HEIGHT = 50;
  private readonly PHASE_BAR_HEIGHT = 60;
  private readonly CHAT_INPUT_HEIGHT = 40;
  private readonly BUTTON_HEIGHT = 35;
  private readonly BUTTON_MARGIN = 10;

  constructor(canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D, ws: WebSocketClient) {
    this.canvas = canvas;
    this.ctx = ctx;
    this.ws = ws;

    this.setupWebSocketHandlers();
    this.setupEventListeners();
  }

  private setupWebSocketHandlers() {
    this.ws.onGameStateUpdate = (gameState: GameState) => {
      this.gameState = gameState;
      this.chatMessages = gameState.all_chat_messages || [];
      this.currentPhase = gameState.current_phase?.phase_type || 'PREGAME';
      this.phaseTimeRemaining = gameState.current_phase?.remaining_time || 0;
      this.updateButtons();
    };

    this.ws.onChatMessage = (message: ChatMessage) => {
      this.chatMessages.push(message);
      if (this.chatMessages.length > 50) {
        this.chatMessages = this.chatMessages.slice(-50);
      }
    };

    this.ws.onPhaseChange = (phase: string, duration: number) => {
      this.currentPhase = phase;
      this.phaseTimeRemaining = duration;
      this.updateButtons();
    };
  }

  private setupEventListeners() {
    // Mouse click
    this.canvas.addEventListener('click', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      // Check chat input click
      const inputY = this.canvas.height - this.CHAT_INPUT_HEIGHT - 10;
      if (y >= inputY && y <= inputY + this.CHAT_INPUT_HEIGHT) {
        this.chatInputActive = true;
        return;
      }

      // Check button clicks
      for (const button of this.buttons) {
        if (x >= button.x && x <= button.x + button.width &&
            y >= button.y && y <= button.y + button.height &&
            button.enabled !== false) {
          button.callback();
          return;
        }
      }

      // Check player list clicks
      this.handlePlayerListClick(x, y);
    });

    // Keyboard input
    window.addEventListener('keydown', (e) => {
      if (this.chatInputActive) {
        if (e.key === 'Enter') {
          this.sendChat();
          this.chatInputActive = false;
        } else if (e.key === 'Escape') {
          this.chatInputActive = false;
          this.chatInput = '';
        } else if (e.key === 'Backspace') {
          this.chatInput = this.chatInput.slice(0, -1);
        } else if (e.key.length === 1 && this.chatInput.length < 200) {
          this.chatInput += e.key;
        }
      } else {
        // Hotkeys
        if (e.key === 'Enter' || e.key === 'c') {
          this.chatInputActive = true;
        }
      }
    });
  }

  private handlePlayerListClick(x: number, y: number) {
    if (!this.gameState) return;

    const listWidth = 250;
    const listX = this.canvas.width - listWidth - 20;
    const startY = this.PHASE_BAR_HEIGHT + 40;

    let playerY = startY;
    for (const player of this.gameState.players) {
      if (x >= listX && x <= listX + listWidth &&
          y >= playerY && y <= playerY + 25) {
        this.selectedPlayer = player.player_id;
        console.log(`Selected player: ${player.name} (${player.player_id})`);
        return;
      }
      playerY += 25;
    }
  }

  private updateButtons() {
    this.buttons = [];

    if (!this.gameState) return;

    const buttonX = 20;
    let buttonY = this.PHASE_BAR_HEIGHT + 20;

    // Phase-specific buttons
    if (this.currentPhase === 'DAY_DISCUSSION') {
      // Vote to accuse button
      this.buttons.push({
        x: buttonX,
        y: buttonY,
        width: 150,
        height: this.BUTTON_HEIGHT,
        text: 'Vote for Trial',
        callback: () => this.voteForTrial(),
        enabled: this.selectedPlayer !== null
      });
      buttonY += this.BUTTON_HEIGHT + this.BUTTON_MARGIN;

      // Whisper button
      this.buttons.push({
        x: buttonX,
        y: buttonY,
        width: 150,
        height: this.BUTTON_HEIGHT,
        text: 'Whisper',
        callback: () => this.whisperToSelected(),
        enabled: this.selectedPlayer !== null
      });
      buttonY += this.BUTTON_HEIGHT + this.BUTTON_MARGIN;
    }

    if (this.currentPhase === 'NIGHT') {
      const humanPlayer = this.gameState.players.find(p => p.is_human);
      if (humanPlayer?.role?.abilities && humanPlayer.role.abilities.length > 0) {
        this.buttons.push({
          x: buttonX,
          y: buttonY,
          width: 150,
          height: this.BUTTON_HEIGHT,
          text: 'Use Ability',
          callback: () => this.useNightAbility(),
          enabled: this.selectedPlayer !== null
        });
      }
    }

    if (this.currentPhase === 'JUDGMENT') {
      this.buttons.push({
        x: buttonX,
        y: buttonY,
        width: 150,
        height: this.BUTTON_HEIGHT,
        text: 'Vote GUILTY',
        callback: () => this.voteGuilty()
      });
      buttonY += this.BUTTON_HEIGHT + this.BUTTON_MARGIN;

      this.buttons.push({
        x: buttonX,
        y: buttonY,
        width: 150,
        height: this.BUTTON_HEIGHT,
        text: 'Vote INNOCENT',
        callback: () => this.voteInnocent()
      });
    }

    // Will editor button (always available)
    buttonY = this.canvas.height - 100;
    this.buttons.push({
      x: buttonX,
      y: buttonY,
      width: 150,
      height: this.BUTTON_HEIGHT,
      text: 'Edit Will',
      callback: () => this.editWill()
    });
  }

  // Action methods
  private sendChat() {
    if (!this.chatInput.trim()) return;

    this.ws.send({
      type: 'chat',
      data: { message: this.chatInput }
    });

    this.chatInput = '';
  }

  private voteForTrial() {
    if (this.selectedPlayer === null) return;

    this.ws.send({
      type: 'vote',
      data: { target_id: this.selectedPlayer }
    });

    console.log(`Voted for player ${this.selectedPlayer}`);
  }

  private voteGuilty() {
    if (!this.gameState?.accused_player_id) return;

    this.ws.send({
      type: 'vote',
      data: {
        target_id: this.gameState.accused_player_id,
        guilty: true
      }
    });

    console.log('Voted GUILTY');
  }

  private voteInnocent() {
    if (!this.gameState?.accused_player_id) return;

    this.ws.send({
      type: 'vote',
      data: {
        target_id: this.gameState.accused_player_id,
        guilty: false
      }
    });

    console.log('Voted INNOCENT');
  }

  private useNightAbility() {
    if (this.selectedPlayer === null) return;

    this.ws.send({
      type: 'night_action',
      data: { target_id: this.selectedPlayer }
    });

    console.log(`Used ability on player ${this.selectedPlayer}`);
  }

  private whisperToSelected() {
    if (this.selectedPlayer === null || !this.chatInput.trim()) return;

    this.ws.send({
      type: 'whisper',
      data: {
        to_player_id: this.selectedPlayer,
        message: this.chatInput
      }
    });

    this.chatInput = '';
  }

  private editWill() {
    // For now, just prompt for will text
    // In a full implementation, would open a modal
    const will = prompt('Enter your last will (max 200 chars):');
    if (will !== null) {
      this.ws.send({
        type: 'update_will',
        data: { will: will.substring(0, 200) }
      });
    }
  }

  async initialize() {
    this.ws.send({ type: 'request_game_state', data: {} });
    console.log('Interactive game initialized');
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
    const deltaTime = (now - this.lastFrameTime) / 1000;
    this.lastFrameTime = now;

    this.update(deltaTime);
    this.render();

    requestAnimationFrame(this.gameLoop);
  };

  private update(deltaTime: number) {
    if (this.phaseTimeRemaining > 0) {
      this.phaseTimeRemaining -= deltaTime;
      if (this.phaseTimeRemaining < 0) {
        this.phaseTimeRemaining = 0;
      }
    }
  }

  private render() {
    const { canvas, ctx } = this;

    // Clear
    ctx.fillStyle = '#2a2a2a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Render components
    this.renderPhaseBar();
    this.renderChat();
    this.renderChatInput();
    this.renderPlayerList();
    this.renderButtons();
  }

  private renderPhaseBar() {
    const { ctx, canvas } = this;
    const barHeight = this.PHASE_BAR_HEIGHT;

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
    const endY = canvas.height - this.CHAT_INPUT_HEIGHT - 20;
    const chatWidth = this.CHAT_WIDTH;
    const chatX = (canvas.width - chatWidth) / 2;

    // Background
    ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
    ctx.fillRect(
      chatX - this.CHAT_PADDING,
      startY - this.CHAT_PADDING,
      chatWidth + this.CHAT_PADDING * 2,
      endY - startY + this.CHAT_PADDING
    );

    // Messages
    const maxMessages = Math.floor((endY - startY) / this.MESSAGE_HEIGHT);
    const messagesToShow = this.chatMessages.slice(-maxMessages);

    let y = startY;
    for (const message of messagesToShow) {
      this.renderChatMessage(message, chatX, y, chatWidth);
      y += this.MESSAGE_HEIGHT;
    }

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
    ctx.fillStyle = message.is_whisper ? '#9C27B0' : '#4CAF50';
    ctx.font = 'bold 14px sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';

    const prefix = message.is_whisper ? '[WHISPER] ' : '';
    ctx.fillText(`${prefix}${message.player_name}:`, x, y);

    // Message
    ctx.fillStyle = '#ffffff';
    ctx.font = '14px sans-serif';

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

  private renderChatInput() {
    const { ctx, canvas } = this;
    const inputY = canvas.height - this.CHAT_INPUT_HEIGHT - 10;
    const inputWidth = this.CHAT_WIDTH;
    const inputX = (canvas.width - inputWidth) / 2;

    // Background
    ctx.fillStyle = this.chatInputActive ? '#333' : '#222';
    ctx.fillRect(inputX, inputY, inputWidth, this.CHAT_INPUT_HEIGHT);

    // Border
    ctx.strokeStyle = this.chatInputActive ? '#4CAF50' : '#444';
    ctx.lineWidth = 2;
    ctx.strokeRect(inputX, inputY, inputWidth, this.CHAT_INPUT_HEIGHT);

    // Text
    ctx.fillStyle = '#fff';
    ctx.font = '16px sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';

    const displayText = this.chatInput || (this.chatInputActive ? '|' : 'Press Enter to chat...');
    ctx.fillText(displayText, inputX + 10, inputY + this.CHAT_INPUT_HEIGHT / 2);
  }

  private renderPlayerList() {
    const { ctx, canvas } = this;
    const listWidth = 250;
    const listX = canvas.width - listWidth - 20;
    const startY = this.PHASE_BAR_HEIGHT + 20;

    if (!this.gameState) return;

    // Background
    ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
    ctx.fillRect(listX - 10, startY - 10, listWidth + 20, canvas.height - startY);

    // Title
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 18px sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText('Players', listX, startY);

    // Players
    let y = startY + 40;

    for (const player of this.gameState.players) {
      const isSelected = player.player_id === this.selectedPlayer;

      // Highlight selected
      if (isSelected) {
        ctx.fillStyle = 'rgba(76, 175, 80, 0.3)';
        ctx.fillRect(listX - 5, y - 2, listWidth, 25);
      }

      // Status dot
      ctx.fillStyle = player.is_alive ? '#4CAF50' : '#f44336';
      ctx.beginPath();
      ctx.arc(listX, y + 8, 5, 0, Math.PI * 2);
      ctx.fill();

      // Name
      ctx.fillStyle = player.is_alive ? '#ffffff' : '#666';
      ctx.font = player.is_human ? 'bold 14px sans-serif' : '14px sans-serif';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      ctx.fillText(player.name + (player.is_human ? ' (You)' : ''), listX + 15, y);

      y += 25;
    }
  }

  private renderButtons() {
    const { ctx } = this;

    for (const button of this.buttons) {
      const enabled = button.enabled !== false;

      // Background
      ctx.fillStyle = enabled ? '#4CAF50' : '#555';
      ctx.fillRect(button.x, button.y, button.width, button.height);

      // Border
      ctx.strokeStyle = enabled ? '#66BB6A' : '#666';
      ctx.lineWidth = 2;
      ctx.strokeRect(button.x, button.y, button.width, button.height);

      // Text
      ctx.fillStyle = enabled ? '#fff' : '#999';
      ctx.font = 'bold 14px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(
        button.text,
        button.x + button.width / 2,
        button.y + button.height / 2
      );
    }
  }
}
