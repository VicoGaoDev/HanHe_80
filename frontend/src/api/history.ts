import client from "./client";
import type { HistoryFilter, UserHistoryResponse } from "@/types";

export function fetchHistory(
  page: number = 1,
  pageSize: number = 20,
  filters: Pick<HistoryFilter, "mode" | "source" | "model" | "prompt" | "status" | "start_date" | "end_date"> = {},
): Promise<UserHistoryResponse> {
  return client.get("/history", {
    params: {
      page,
      page_size: pageSize,
      mode: filters.mode,
      source: filters.source,
      model: filters.model,
      prompt: filters.prompt?.trim() || undefined,
      status: filters.status,
      start_date: filters.start_date,
      end_date: filters.end_date,
    },
  });
}
