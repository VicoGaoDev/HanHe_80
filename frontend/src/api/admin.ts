import client from "./client";
import type {
  AdminStats,
  AdminAnalyticsBreakdown,
  AdminAnalyticsQuery,
  AdminAnalyticsSummary,
  AdminAnalyticsTimeseries,
  AdminConfig,
  CosConfig,
  AdminUser,
  CreditLog,
  ExternalApiConfig,
  ExternalApiConfigPayload,
  ExternalApiSecretConfig,
  ExternalApiSceneBinding,
  ExternalApiSceneBindingCreatePayload,
  ExternalApiSceneBindingMetaPayload,
  ExternalApiConfigStatus,
  ExternalApiConfigTestResult,
  HistoryFilter,
  HistoryResponse,
} from "@/types";

function buildAnalyticsParams(query: AdminAnalyticsQuery): Record<string, unknown> {
  const params: Record<string, unknown> = {
    granularity: query.granularity,
  };
  if (query.start_date) params.start_date = query.start_date;
  if (query.end_date) params.end_date = query.end_date;
  if (query.user_id) params.user_id = query.user_id;
  if (query.source) params.source = query.source;
  if (query.model) params.model = query.model;
  if (query.mode) params.mode = query.mode;
  if (query.status) params.status = query.status;
  return params;
}

export function listUsers(): Promise<AdminUser[]> {
  return client.get("/admin/users");
}

export function createUser(data: { username: string; password: string; role?: string }): Promise<AdminUser> {
  return client.post("/admin/users", data);
}

export function updateUserStatus(userId: string, status: string): Promise<AdminUser> {
  return client.put(`/admin/users/${userId}/status`, { status });
}

export function updateUserRole(userId: string, role: string): Promise<AdminUser> {
  return client.put(`/admin/users/${userId}/role`, { role });
}

export function updateUserWhitelist(userId: string, isWhitelisted: boolean): Promise<AdminUser> {
  return client.put(`/admin/users/${userId}/whitelist`, { is_whitelisted: isWhitelisted });
}

export function resetUserPassword(userId: string, newPassword: string): Promise<AdminUser> {
  return client.put(`/admin/users/${userId}/reset-password`, { new_password: newPassword });
}

export function allocateCredits(userId: string, amount: number, description?: string): Promise<AdminUser> {
  return client.post(`/admin/users/${userId}/credits`, { amount, description: description || "" });
}

export function resetUserCredits(userId: string, description?: string): Promise<AdminUser> {
  return client.post(`/admin/users/${userId}/credits/reset`, { description: description || "" });
}

export function getCreditLogs(
  page = 1,
  pageSize = 20,
  userId?: string,
  direction?: "increase" | "decrease",
  mode?: "generate" | "inpaint" | "promptReverse" | "manual",
): Promise<{ total: number; items: CreditLog[] }> {
  const params: Record<string, unknown> = { page, page_size: pageSize };
  if (userId) params.user_id = userId;
  if (direction) params.direction = direction;
  if (mode) params.mode = mode;
  return client.get("/admin/credit-logs", { params });
}

export function getStats(): Promise<AdminStats> {
  return client.get("/admin/stats");
}

export function getAdminHistory(
  page: number = 1,
  pageSize: number = 20,
  filter?: HistoryFilter,
): Promise<HistoryResponse> {
  const params: Record<string, unknown> = { page, page_size: pageSize };
  if (filter?.status) params.status = filter.status;
  if (filter?.user_id) params.user_id = filter.user_id;
  if (filter?.source) params.source = filter.source;
  if (filter?.model) params.model = filter.model;
  if (filter?.mode) params.mode = filter.mode;
  if (filter?.start_date) params.start_date = filter.start_date;
  if (filter?.end_date) params.end_date = filter.end_date;
  return client.get("/admin/history", { params });
}

export function getAdminAnalyticsSummary(query: AdminAnalyticsQuery): Promise<AdminAnalyticsSummary> {
  return client.get("/admin/analytics/summary", { params: buildAnalyticsParams(query) });
}

export function getAdminAnalyticsTimeseries(query: AdminAnalyticsQuery): Promise<AdminAnalyticsTimeseries> {
  return client.get("/admin/analytics/timeseries", { params: buildAnalyticsParams(query) });
}

export function getAdminAnalyticsBreakdown(query: AdminAnalyticsQuery): Promise<AdminAnalyticsBreakdown> {
  return client.get("/admin/analytics/breakdown", { params: buildAnalyticsParams(query) });
}

export function getAdminConfig(): Promise<AdminConfig | null> {
  return client.get("/admin/api-key");
}

export function setAdminConfig(payload: {
  contact_qr_image?: string;
  announcement_enabled?: boolean;
  announcement_content?: string;
}): Promise<AdminConfig> {
  return client.put("/admin/api-key", payload);
}

export function deleteAdminConfig(): Promise<void> {
  return client.delete("/admin/api-key");
}

export function getExternalApiSecrets(): Promise<ExternalApiSecretConfig | null> {
  return client.get("/admin/external-api-secrets");
}

export function setExternalApiSecrets(payload: {
  key?: string;
  tongyi_key?: string;
}): Promise<ExternalApiSecretConfig> {
  return client.put("/admin/external-api-secrets", payload);
}

export function getCosConfig(): Promise<CosConfig | null> {
  return client.get("/admin/cos-config");
}

export function setCosConfig(payload: {
  cos_secret_id?: string;
  cos_secret_key?: string;
  cos_bucket?: string;
  cos_region?: string;
  cos_public_base_url?: string;
}): Promise<CosConfig> {
  return client.put("/admin/cos-config", payload);
}

export function deleteCosConfig(): Promise<void> {
  return client.delete("/admin/cos-config");
}

export function listExternalApiConfigs(): Promise<ExternalApiConfig[]> {
  return client.get("/admin/external-api-configs");
}

export function createExternalApiConfig(payload: ExternalApiConfigPayload): Promise<ExternalApiConfig> {
  return client.post("/admin/external-api-configs", payload);
}

export function updateExternalApiConfig(configId: number, payload: ExternalApiConfigPayload): Promise<ExternalApiConfig> {
  return client.put(`/admin/external-api-configs/${configId}`, payload);
}

export function updateExternalApiConfigStatus(configId: number, status: ExternalApiConfigStatus): Promise<ExternalApiConfig> {
  return client.patch(`/admin/external-api-configs/${configId}/status`, { status });
}

export function listExternalApiSceneBindings(): Promise<ExternalApiSceneBinding[]> {
  return client.get("/admin/external-api-scene-bindings");
}

export function createExternalApiSceneBinding(
  payload: ExternalApiSceneBindingCreatePayload,
): Promise<ExternalApiSceneBinding> {
  return client.post("/admin/external-api-scene-bindings", payload);
}

export function updateExternalApiSceneBindingMeta(
  sceneKey: ExternalApiSceneBinding["scene_key"],
  payload: ExternalApiSceneBindingMetaPayload,
): Promise<ExternalApiSceneBinding> {
  return client.patch(`/admin/external-api-scene-bindings/${sceneKey}/meta`, payload);
}

export function updateExternalApiSceneBindingStatus(
  sceneKey: ExternalApiSceneBinding["scene_key"],
  status: ExternalApiConfigStatus,
): Promise<ExternalApiSceneBinding> {
  return client.patch(`/admin/external-api-scene-bindings/${sceneKey}/status`, { status });
}

export function deleteExternalApiSceneBinding(
  sceneKey: ExternalApiSceneBinding["scene_key"],
): Promise<void> {
  return client.delete(`/admin/external-api-scene-bindings/${sceneKey}`);
}

export function updateExternalApiSceneBinding(
  sceneKey: ExternalApiSceneBinding["scene_key"],
  payload: {
    api_config_id: number | null;
    credit_cost: number;
    display_name: string;
    subtitle: string;
  },
): Promise<ExternalApiSceneBinding> {
  return client.put(`/admin/external-api-scene-bindings/${sceneKey}`, payload);
}

export function testExternalApiConfig(payload: ExternalApiConfigPayload): Promise<ExternalApiConfigTestResult> {
  return client.post("/admin/external-api-configs/test", payload);
}
