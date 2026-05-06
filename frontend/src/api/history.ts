import client from "./client";
import type { HistoryFilter, HistoryPinTogglePayload, HistoryPinToggleResponse, UserHistoryResponse } from "@/types";

export function fetchHistory(
  page: number = 1,
  pageSize: number = 20,
  filters: Pick<HistoryFilter, "mode" | "source" | "model" | "prompt" | "status" | "start_date" | "end_date" | "respect_pins"> = {},
): Promise<UserHistoryResponse> {
  return client.get("/history", {
    params: {
      page,
      page_size: pageSize,
      respect_pins: filters.respect_pins,
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

export function toggleHistoryPin(payload: HistoryPinTogglePayload): Promise<HistoryPinToggleResponse> {
  return client.post("/history/pins/toggle", payload);
}
