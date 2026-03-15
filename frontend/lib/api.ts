const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
    ...options?.headers,
  };

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body || `HTTP ${res.status}`);
  }

  return res.json();
}

// --- Types ---

export interface HiveStatus {
  hive_id: number;
  name: string;
  exchange: string;
  total_capital: number;
  used_capital: number;
  free_capital: number;
  max_workers: number;
  total_workers: number;
  running_workers: number;
  total_pnl: number;
}

export interface Worker {
  id: number;
  strategy: string;
  symbol: string;
  capital: number;
  status: string;
  pnl: number;
  total_trades: number;
  created_at: string;
}

export interface WorkerDetail extends Worker {
  config: Record<string, unknown>;
  state: Record<string, unknown>;
}

export interface PriceData {
  symbol: string;
  price: number;
  bid: number;
  ask: number;
  timestamp: number;
}

export interface PnlAnalytics {
  by_strategy: Array<{
    strategy: string;
    total_pnl: number;
    worker_count: number;
  }>;
  recent_trades: Array<{
    symbol: string;
    profit: number;
    timestamp: string;
  }>;
}

export interface QueenDecision {
  symbol: string;
  decision: string;
  confidence: number | null;
  reasoning: string;
  timestamp: string;
}

// --- API Functions ---

export const api = {
  getHiveStatus: () => request<HiveStatus>("/hive/status"),

  getWorkers: () => request<Worker[]>("/workers"),

  getWorker: (id: number) => request<WorkerDetail>(`/workers/${id}`),

  createWorker: (data: {
    strategy_name: string;
    symbol: string;
    capital: number;
    config: Record<string, unknown>;
  }) =>
    request<{ worker_id: number; status: string }>("/workers", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  sendCommand: (workerId: number, command: "pause" | "resume" | "stop") =>
    request<{ status: string; command: string }>(
      `/workers/${workerId}/command`,
      {
        method: "PUT",
        body: JSON.stringify({ command }),
      },
    ),

  getMarketPrices: () => request<PriceData[]>("/market/prices"),

  getPnlAnalytics: () => request<PnlAnalytics>("/analytics/pnl"),

  getQueenDecisions: () => request<QueenDecision[]>("/queen/decisions"),
};

export function getWebSocketUrl(): string {
  const wsBase = API_BASE_URL.replace(/^http/, "ws");
  const params = API_KEY ? `?api_key=${encodeURIComponent(API_KEY)}` : "";
  return `${wsBase}/ws${params}`;
}
