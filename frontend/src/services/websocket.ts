/**
 * Thin WebSocket client for the /ws ingestion-event stream, with capped
 * exponential-backoff reconnection. Consumed via the useWebSocket hook —
 * components should not instantiate this directly.
 */

import { config } from "../config";
import type { IngestionEvent } from "../types/dashboard";

const RECONNECT_DELAYS_MS = [1000, 2000, 4000, 8000, 15000];

export type WsStatus = "connecting" | "open" | "closed";

interface Listeners {
  onEvent: (event: IngestionEvent) => void;
  onStatusChange: (status: WsStatus) => void;
}

export class IngestionSocket {
  private socket: WebSocket | null = null;
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private closedByCaller = false;

  constructor(private listeners: Listeners) {}

  connect(): void {
    this.closedByCaller = false;
    this.open();
  }

  disconnect(): void {
    this.closedByCaller = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.socket?.close();
    this.socket = null;
  }

  private open(): void {
    this.listeners.onStatusChange("connecting");

    let socket: WebSocket;
    try {
      socket = new WebSocket(config.wsUrl);
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.socket = socket;

    socket.onopen = () => {
      this.reconnectAttempt = 0;
      this.listeners.onStatusChange("open");
    };

    socket.onmessage = (message) => {
      try {
        const data = JSON.parse(message.data) as IngestionEvent;
        this.listeners.onEvent(data);
      } catch {
        // Ignore malformed frames rather than crashing the dashboard.
      }
    };

    socket.onclose = () => {
      this.listeners.onStatusChange("closed");
      if (!this.closedByCaller) this.scheduleReconnect();
    };

    socket.onerror = () => {
      socket.close();
    };
  }

  private scheduleReconnect(): void {
    const delay =
      RECONNECT_DELAYS_MS[
        Math.min(this.reconnectAttempt, RECONNECT_DELAYS_MS.length - 1)
      ];
    this.reconnectAttempt += 1;
    this.reconnectTimer = setTimeout(() => {
      if (!this.closedByCaller) this.open();
    }, delay);
  }
}
