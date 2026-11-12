import { SimulationTickEvent } from '../types';

type MessageHandler = (data: SimulationTickEvent) => void;
type StatusHandler = (connected: boolean) => void;

class TrafficWebSocketClient {
  private socket: WebSocket | null = null;
  private messageHandlers: Set<MessageHandler> = new Set();
  private statusHandlers: Set<StatusHandler> = new Set();
  private reconnectTimer: any = null;
  private isExplicitlyClosed: boolean = false;

  public connect() {
    this.isExplicitlyClosed = false;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/traffic`;

    try {
      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        console.log('[WS] Connected to traffic intelligence websocket.');
        this.notifyStatus(true);
      };

      this.socket.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          this.messageHandlers.forEach((handler) => handler(parsed));
        } catch (err) {
          console.warn('[WS] Failed to parse message JSON', err);
        }
      };

      this.socket.onclose = () => {
        this.notifyStatus(false);
        if (!this.isExplicitlyClosed) {
          console.log('[WS] Connection closed. Retrying in 2.5s...');
          this.reconnectTimer = setTimeout(() => this.connect(), 2500);
        }
      };

      this.socket.onerror = (err) => {
        console.warn('[WS] Error:', err);
        this.socket?.close();
      };
    } catch (err) {
      console.error('[WS] Connection attempt failed', err);
      this.reconnectTimer = setTimeout(() => this.connect(), 3000);
    }
  }

  public subscribe(handler: MessageHandler) {
    this.messageHandlers.add(handler);
    return () => {
      this.messageHandlers.delete(handler);
    };
  }

  public onStatus(handler: StatusHandler) {
    this.statusHandlers.add(handler);
    handler(this.socket?.readyState === WebSocket.OPEN);
    return () => {
      this.statusHandlers.delete(handler);
    };
  }

  public disconnect() {
    this.isExplicitlyClosed = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.notifyStatus(false);
  }

  private notifyStatus(connected: boolean) {
    this.statusHandlers.forEach((fn) => fn(connected));
  }
}

export const trafficWs = new TrafficWebSocketClient();
