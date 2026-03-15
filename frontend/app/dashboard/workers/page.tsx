"use client";

import { useWorkers, useWorkerCommand } from "@/hooks/use-api";

const STATUS_COLORS: Record<string, string> = {
  running: "text-green-400",
  paused: "text-yellow-400",
  stopped: "text-gray-400",
  error: "text-red-400",
  init: "text-blue-400",
};

export default function WorkersPage() {
  const { data: workers = [], isLoading, error } = useWorkers();
  const command = useWorkerCommand();

  const sendCommand = (workerId: number, cmd: "pause" | "resume" | "stop") => {
    command.mutate({ workerId, command: cmd });
  };

  if (isLoading) {
    return <div className="text-gray-400">Loading...</div>;
  }

  if (error) {
    return (
      <div className="text-red-400">
        Failed to load workers: {error.message}
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Workers</h1>
        <div className="text-sm text-gray-400">
          {workers.filter((w) => w.status === "running").length} running /{" "}
          {workers.length} total
        </div>
      </div>

      {workers.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          No workers found. Queen will deploy workers automatically.
        </div>
      ) : (
        <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-900">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">
                  ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">
                  Symbol
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">
                  Strategy
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">
                  Capital
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">
                  PnL
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">
                  Trades
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {workers.map((worker) => (
                <tr key={worker.id} className="hover:bg-gray-700/50">
                  <td className="px-6 py-4 text-sm text-gray-300">
                    {worker.id}
                  </td>
                  <td className="px-6 py-4 text-sm font-medium text-white">
                    {worker.symbol}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-300">
                    {worker.strategy}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-300">
                    ${worker.capital.toLocaleString()}
                  </td>
                  <td
                    className={`px-6 py-4 text-sm font-medium ${
                      worker.pnl >= 0 ? "text-green-400" : "text-red-400"
                    }`}
                  >
                    {worker.pnl >= 0 ? "+" : ""}${worker.pnl.toFixed(2)}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-300">
                    {worker.total_trades}
                  </td>
                  <td className="px-6 py-4 text-sm">
                    <span
                      className={`font-medium ${STATUS_COLORS[worker.status] || "text-gray-400"}`}
                    >
                      {worker.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm">
                    <div className="flex gap-2">
                      {worker.status === "running" && (
                        <button
                          onClick={() => sendCommand(worker.id, "pause")}
                          disabled={command.isPending}
                          className="px-3 py-1 bg-yellow-600 hover:bg-yellow-700 disabled:opacity-50 rounded text-xs"
                        >
                          Pause
                        </button>
                      )}
                      {worker.status === "paused" && (
                        <button
                          onClick={() => sendCommand(worker.id, "resume")}
                          disabled={command.isPending}
                          className="px-3 py-1 bg-green-600 hover:bg-green-700 disabled:opacity-50 rounded text-xs"
                        >
                          Resume
                        </button>
                      )}
                      {(worker.status === "running" ||
                        worker.status === "paused") && (
                        <button
                          onClick={() => sendCommand(worker.id, "stop")}
                          disabled={command.isPending}
                          className="px-3 py-1 bg-red-600 hover:bg-red-700 disabled:opacity-50 rounded text-xs"
                        >
                          Stop
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
