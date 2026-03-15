"use client";

import { usePnlAnalytics } from "@/hooks/use-api";

export default function AnalyticsPage() {
  const { data: analytics, isLoading, error } = usePnlAnalytics();

  if (isLoading) {
    return <div className="text-gray-400">Loading...</div>;
  }

  if (error || !analytics) {
    return (
      <div className="text-red-400">
        Failed to load analytics: {error?.message || "Unknown error"}
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-8">Analytics</h1>

      {/* Strategy Performance */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 mb-6">
        <h2 className="text-xl font-semibold mb-4">Performance by Strategy</h2>
        {analytics.by_strategy.length === 0 ? (
          <div className="text-gray-400">No strategy data yet.</div>
        ) : (
          <div className="space-y-4">
            {analytics.by_strategy.map((item) => (
              <div
                key={item.strategy}
                className="flex items-center justify-between"
              >
                <div>
                  <div className="font-medium text-white">{item.strategy}</div>
                  <div className="text-sm text-gray-400">
                    {item.worker_count} workers
                  </div>
                </div>
                <div
                  className={`text-xl font-bold ${
                    item.total_pnl >= 0 ? "text-green-400" : "text-red-400"
                  }`}
                >
                  {item.total_pnl >= 0 ? "+" : ""}${item.total_pnl.toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent Trades */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold mb-4">Recent Trades</h2>
        {analytics.recent_trades.length === 0 ? (
          <div className="text-gray-400">No trades recorded yet.</div>
        ) : (
          <div className="space-y-2">
            {analytics.recent_trades.map((trade, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between py-2 border-b border-gray-700 last:border-0"
              >
                <div className="flex items-center gap-4">
                  <div className="font-medium text-white">{trade.symbol}</div>
                  <div className="text-sm text-gray-400">
                    {new Date(trade.timestamp).toLocaleString()}
                  </div>
                </div>
                <div
                  className={`font-medium ${
                    trade.profit >= 0 ? "text-green-400" : "text-red-400"
                  }`}
                >
                  {trade.profit >= 0 ? "+" : ""}${trade.profit.toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
