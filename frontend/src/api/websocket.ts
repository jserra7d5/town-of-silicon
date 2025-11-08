/**
 * WebSocket client for real-time game communication
 */

export interface GameStateUpdate {
  type: 'game_state_update';
  game_state: any;
}

export interface ChatMessage {
  type: 'chat_message';
  message: {
    player_id: number;
    player_name: string;
    message: string;
    phase: string;
    day_number: number;
  };
}

export interface PhaseChange {
  type: 'phase_change';
  phase: string;
  duration: number;
  phase_number: number;
}

export type WSMessage = GameStateUpdate | ChatMessage | PhaseChange;

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;

  // Event handlers
  public onGameStateUpdate?: (gameState: any) => void;
  public onChatMessage?: (message: any) => void;
  public onPhaseChange?: (phase: string, duration: number) => void;
  public onConnect?: () => void;
  public onDisconnect?: () => void;

  constructor(url: string) {
    this.url = url;
  }

  async connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
          console.log('[WebSocket] Connected');
          this.reconnectAttempts = 0;

          if (this.onConnect) {
            this.onConnect();
          }

          resolve();
        };

        this.ws.onmessage = (event) => {
          this.handleMessage(event.data);
        };

        this.ws.onerror = (error) => {
          console.error('[WebSocket] Error:', error);
          reject(error);
        };

        this.ws.onclose = () => {
          console.log('[WebSocket] Disconnected');

          if (this.onDisconnect) {
            this.onDisconnect();
          }

          // Attempt reconnection
          this.attemptReconnect();
        };

      } catch (error) {
        reject(error);
      }
    });
  }

  private handleMessage(data: string) {
    try {
      const message: WSMessage = JSON.parse(data);

      switch (message.type) {
        case 'game_state_update':
          if (this.onGameStateUpdate) {
            this.onGameStateUpdate(message.game_state);
          }
          break;

        case 'chat_message':
          if (this.onChatMessage) {
            this.onChatMessage(message.message);
          }
          break;

        case 'phase_change':
          if (this.onPhaseChange) {
            this.onPhaseChange(message.phase, message.duration);
          }
          break;

        default:
          console.log('[WebSocket] Unknown message type:', message);
      }
    } catch (error) {
      console.error('[WebSocket] Error parsing message:', error);
    }
  }

  private attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WebSocket] Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * this.reconnectAttempts;

    console.log(`[WebSocket] Reconnecting in ${delay}ms... (attempt ${this.reconnectAttempts})`);

    setTimeout(() => {
      this.connect().catch((error) => {
        console.error('[WebSocket] Reconnection failed:', error);
      });
    }, delay);
  }

  send(message: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.error('[WebSocket] Cannot send message - not connected');
    }
  }

  sendChat(message: string) {
    this.send({
      type: 'chat',
      data: { message }
    });
  }

  sendNightAction(targetId: number | null) {
    this.send({
      type: 'night_action',
      data: { target_id: targetId }
    });
  }

  sendVote(targetId: number | null, guilty?: boolean) {
    this.send({
      type: 'vote',
      data: { target_id: targetId, guilty }
    });
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
