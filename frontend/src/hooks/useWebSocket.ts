import { useEffect, useRef, useState, useCallback } from "react";
import { IngestionSocket, type WsStatus } from "../services/websocket";
import type { ActivityItem, IngestionEvent } from "../types/dashboard";

const MAX_ACTIVITY_ITEMS = 12;

function describeEvent(event: IngestionEvent): ActivityItem {
  const base = {
    id: `${event.run_id}-${event.event}-${event.source ?? "all"}-${event.timestamp}`,
    timestamp: event.timestamp,
  };

  switch (event.event) {
    case "INGESTION_STARTED":
      return { ...base, message: `Run #${event.run_id} started`, tone: "info" };
    case "SOURCE_STARTED":
      return { ...base, message: `${event.source} started`, tone: "info" };
    case "SOURCE_COMPLETED":
      return {
        ...base,
        message: `${event.source} completed — ${event.records ?? 0} records`,
        tone: "success",
      };
    case "SOURCE_FAILED":
      return {
        ...base,
        message: `${event.source} failed${event.error ? ` — ${event.error}` : ""}`,
        tone: "error",
      };
    case "INGESTION_COMPLETED":
      return {
        ...base,
        message: `Run #${event.run_id} finished — ${event.status ?? "unknown"}`,
        tone: event.status === "FAILED" ? "error" : "success",
      };
    default:
      return { ...base, message: "Ingestion event received", tone: "info" };
  }
}

interface UseWebSocketResult {
  status: WsStatus;
  lastEvent: IngestionEvent | null;
  activity: ActivityItem[];
}

/** Connects once on mount and tears the socket down on unmount. */
export function useWebSocket(onEvent?: (event: IngestionEvent) => void): UseWebSocketResult {
  const [status, setStatus] = useState<WsStatus>("connecting");
  const [lastEvent, setLastEvent] = useState<IngestionEvent | null>(null);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const handleEvent = useCallback((event: IngestionEvent) => {
    setLastEvent(event);
    setActivity((prev) => [describeEvent(event), ...prev].slice(0, MAX_ACTIVITY_ITEMS));
    onEventRef.current?.(event);
  }, []);

  useEffect(() => {
    const socket = new IngestionSocket({
      onEvent: handleEvent,
      onStatusChange: setStatus,
    });
    socket.connect();
    return () => socket.disconnect();
  }, [handleEvent]);

  return { status, lastEvent, activity };
}
