"use client";

import { useHiveStatus } from "@/hooks/use-api";

export default function HivePage() {
  const { data: status, isLoading, error } = useHiveStatus();

  if (isLoading) {
    return <div className="text-gray-400">Loading...</div>;
  }

  if (error || !status) {
    return (
      <div className="text-red-400">
        Failed to load hive status: {error?.message || "Unknown error"}
      </div>
    );
  }

  const capitalUsagePercent =
    status.total_capital > 0
      ? (status.used_capital / status.total_capital) * 100
      : 0;
  const pnlPercent =
    status.total_capital > 0
      ? (status.total_pnl / status.total_capital) * 100
      : 0;

  return (
    <div>
      <h1 className="text-3xl font-bold mb-8">{status.name}</h1>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="text-sm text-gray-400 mb-2">Total Capital</div>
          <div className="text-2xl font-bold text-white">
            ${status.total_capital.toLocaleString()}
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="text-sm text-gray-400 mb-2">Used Capital</div>
          <div className="text-2xl font-bold text-yellow-400">
            ${status.used_capital.toLocaleString()}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {capitalUsagePercent.toFixed(1)}% utilized
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="text-sm text-gray-400 mb-2">Free Capital</div>
          <div className="text-2xl font-bold text-green-400">
            ${status.free_capital.toLocaleString()}
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="text-sm text-gray-400 mb-2">Total PnL</div>
          <div
            className={`text-2xl font-bold ${
              status.total_pnl >= 0 ? "text-green-400" : "text-red-400"
            }`}
          >
            {status.total_pnl >= 0 ? "+" : ""}${status.total_pnl.toFixed(2)}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {pnlPercent >= 0 ? "+" : ""}
            {pnlPercent.toFixed(2)}%
          </div>
        </div>
      </div>

      {/* Workers Status */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold mb-4">Workers Status</h2>
        <div className="flex items-center gap-8">
          <div>
            <div className="text-3xl font-bold text-yellow-400">
              {status.running_workers}
            </div>
            <div className="text-sm text-gray-400">Running</div>
          </div>
          <div>
            <div className="text-3xl font-bold text-gray-400">
              {status.total_workers}
            </div>
            <div className="text-sm text-gray-400">Total</div>
          </div>
          <div>
            <div className="text-3xl font-bold text-gray-500">
              {status.max_workers}
            </div>
            <div className="text-sm text-gray-400">Max</div>
          </div>
        </div>
      </div>
    </div>
  );
}
