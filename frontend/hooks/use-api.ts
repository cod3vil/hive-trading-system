"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

// --- Hive ---
export function useHiveStatus() {
  return useQuery({
    queryKey: ["hive-status"],
    queryFn: api.getHiveStatus,
    refetchInterval: 3000,
  });
}

// --- Workers ---
export function useWorkers() {
  return useQuery({
    queryKey: ["workers"],
    queryFn: api.getWorkers,
    refetchInterval: 3000,
  });
}

export function useWorker(id: number) {
  return useQuery({
    queryKey: ["worker", id],
    queryFn: () => api.getWorker(id),
    refetchInterval: 3000,
  });
}

export function useWorkerCommand() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      workerId,
      command,
    }: {
      workerId: number;
      command: "pause" | "resume" | "stop";
    }) => api.sendCommand(workerId, command),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workers"] });
      queryClient.invalidateQueries({ queryKey: ["hive-status"] });
    },
  });
}

export function useCreateWorker() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.createWorker,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workers"] });
      queryClient.invalidateQueries({ queryKey: ["hive-status"] });
    },
  });
}

// --- Market ---
export function useMarketPrices() {
  return useQuery({
    queryKey: ["market-prices"],
    queryFn: api.getMarketPrices,
    refetchInterval: 2000,
  });
}

// --- Analytics ---
export function usePnlAnalytics() {
  return useQuery({
    queryKey: ["pnl-analytics"],
    queryFn: api.getPnlAnalytics,
    refetchInterval: 5000,
  });
}

// --- Queen ---
export function useQueenDecisions() {
  return useQuery({
    queryKey: ["queen-decisions"],
    queryFn: api.getQueenDecisions,
    refetchInterval: 10000,
  });
}
