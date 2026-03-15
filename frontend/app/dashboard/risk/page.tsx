"use client";

import { useHiveStatus, useWorkers } from "@/hooks/use-api";

export default function RiskPage() {
  const { data: hive, isLoading: hiveLoading } = useHiveStatus();
  const { data: workers = [], isLoading: workersLoading } = useWorkers();

  const isLoading = hiveLoading || workersLoading;

  if (isLoading) {
    return <div className="text-gray-400">Loading...</div>;
  }

  // Compute risk metrics from real data
  const totalCapital = hive?.total_capital || 0;
  const usedCapital = hive?.used_capital || 0;
  const capitalExposure =
    totalCapital > 0 ? (usedCapital / totalCapital) * 100 : 0;
  const capitalExposureLimit = 60;

  const totalPnl = hive?.total_pnl || 0;
  const drawdownPercent =
    totalCapital > 0 && totalPnl < 0
      ? (totalPnl / totalCapital) * 100
      : 0;
  const drawdownLimit = -20;

  const errorWorkers = workers.filter((w) => w.status === "error");
  const runningWorkers = workers.filter((w) => w.status === "running");

  // Worst performing worker
  const worstWorker = workers.length > 0
    ? workers.reduce((worst, w) => (w.pnl < worst.pnl ? w : worst), workers[0])
    : null;

  // Circuit breaker status
  let circuitStatus = "Normal";
  let circuitColor = "text-green-400";
  if (drawdownPercent <= drawdownLimit) {
    circuitStatus = "TRIGGERED";
    circuitColor = "text-red-400";
  } else if (capitalExposure >= capitalExposureLimit) {
    circuitStatus = "Warning";
    circuitColor = "text-yellow-400";
  } else if (errorWorkers.length > 0) {
    circuitStatus = "Warning";
    circuitColor = "text-yellow-400";
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-8">Risk Management</h1>

      {/* Risk Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="text-sm text-gray-400 mb-2">Max Drawdown</div>
          <div
            className={`text-2xl font-bold ${
              drawdownPercent <= drawdownLimit / 2
                ? "text-red-400"
                : drawdownPercent < 0
                  ? "text-yellow-400"
                  : "text-green-400"
            }`}
          >
            {drawdownPercent.toFixed(2)}%
          </div>
          <div className="text-xs text-gray-500 mt-1">
            Limit: {drawdownLimit}%
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="text-sm text-gray-400 mb-2">Capital Exposure</div>
          <div
            className={`text-2xl font-bold ${
              capitalExposure >= capitalExposureLimit
                ? "text-red-400"
                : capitalExposure >= capitalExposureLimit * 0.8
                  ? "text-yellow-400"
                  : "text-green-400"
            }`}
          >
            {capitalExposure.toFixed(1)}%
          </div>
          <div className="text-xs text-gray-500 mt-1">
            Limit: {capitalExposureLimit}%
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="text-sm text-gray-400 mb-2">Circuit Breaker</div>
          <div className={`text-2xl font-bold ${circuitColor}`}>
            {circuitStatus}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {errorWorkers.length > 0
              ? `${errorWorkers.length} worker(s) in error state`
              : "All systems operational"}
          </div>
        </div>
      </div>

      {/* Worker Risk Details */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-xl font-semibold mb-4">Worker Overview</h2>
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-gray-400">Running</span>
              <span className="text-green-400 font-medium">
                {runningWorkers.length}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Error</span>
              <span
                className={`font-medium ${errorWorkers.length > 0 ? "text-red-400" : "text-gray-500"}`}
              >
                {errorWorkers.length}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Total</span>
              <span className="text-white font-medium">{workers.length}</span>
            </div>
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-xl font-semibold mb-4">Worst Performer</h2>
          {worstWorker && worstWorker.pnl < 0 ? (
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-400">Worker</span>
                <span className="text-white font-medium">
                  #{worstWorker.id} ({worstWorker.symbol})
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">PnL</span>
                <span className="text-red-400 font-medium">
                  ${worstWorker.pnl.toFixed(2)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">PnL %</span>
                <span className="text-red-400 font-medium">
                  {worstWorker.capital > 0
                    ? ((worstWorker.pnl / worstWorker.capital) * 100).toFixed(2)
                    : "0.00"}
                  %
                </span>
              </div>
            </div>
          ) : (
            <div className="text-gray-400">No losing workers.</div>
          )}
        </div>
      </div>

      {/* Error Workers */}
      {errorWorkers.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-6 border border-red-700/50">
          <h2 className="text-xl font-semibold mb-4 text-red-400">
            Workers in Error State
          </h2>
          <div className="space-y-2">
            {errorWorkers.map((w) => (
              <div
                key={w.id}
                className="flex items-center justify-between py-2 border-b border-gray-700 last:border-0"
              >
                <div>
                  <span className="font-medium text-white">
                    #{w.id} {w.symbol}
                  </span>
                  <span className="text-gray-400 ml-2">({w.strategy})</span>
                </div>
                <div className="text-red-400 font-medium">
                  PnL: ${w.pnl.toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
