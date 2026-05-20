export interface UserInfo {
  id: string;
  business_id: string;
  username: string;
  email?: string | null;
  role: "user" | "admin" | "superadmin";
  avatar_url?: string;
  credits: number;
}

export interface LoginResponse {
  token: string;
  user: UserInfo;
}

export interface PromptHistoryItem {
  id: number;
  prompt: string;
  mode: "generate" | "inpaint" | "promptReverse";
  source_image: string;
  created_at: string;
}

export interface ImageResult {
  id: number;
  image_url: string;
  preview_url?: string;
  thumb_url?: string;
  status: "pending" | "success" | "failed";
  error_message?: string;
  image_format?: string;
  image_size_bytes?: number;
  is_deleted?: boolean;
}

export type TaskMode = "generate" | "inpaint" | "promptReverse";
export type TaskType = "text_generate" | "image_edit" | "inpaint" | "promptReverse";
export type TaskSource = "web" | "app";

export interface TaskResult {
  id: string;
  model: string;
  source: TaskSource;
  prompt: string;
  num_images: number;
  size: string;
  resolution: string;
  custom_size?: string;
  credit_cost: number;
  status: "pending" | "queued" | "processing" | "success" | "failed";
  error_message?: string;
  created_at: string;
  enqueued_at?: string | null;
  request_started_at?: string | null;
  request_finished_at?: string | null;
  images: ImageResult[];
}

export interface HistoryItem {
  item_type: "task" | "prompt_history";
  task_id?: string | null;
  history_id?: number | null;
  display_id?: string;
  user_id?: string;
  username?: string;
  avatar_url?: string;
  task_type: TaskType;
  model: string;
  source: TaskSource;
  mode: TaskMode;
  prompt: string;
  reference_images: string[];
  num_images: number;
  size: string;
  resolution: string;
  custom_size?: string;
  credit_cost: number;
  status: string;
  error_message?: string;
  task_is_deleted?: boolean;
  is_soft_deleted?: boolean;
  soft_deleted_count?: number;
  created_at: string;
  images: ImageResult[];
}

export interface HistoryFilter {
  mode?: TaskType;
  source?: TaskSource;
  model?: string;
  prompt?: string;
  status?: string;
  user_id?: string;
  start_date?: string;
  end_date?: string;
  respect_pins?: boolean;
  include_prompt_reverse?: boolean;
}

export interface HistoryResponse {
  total: number;
  total_credit_cost: number;
  items: HistoryItem[];
}

export interface UserHistoryCard {
  history_id?: number | null;
  item_type: "task" | "prompt_history";
  display_id?: string;
  task_id?: string | null;
  image_id?: number | null;
  is_pinned: boolean;
  pinned_at?: string | null;
  image_url: string;
  preview_url?: string;
  thumb_url?: string;
  status: "pending" | "queued" | "processing" | "success" | "failed";
  image_format?: string;
  image_size_bytes?: number;
  task_is_deleted?: boolean;
  is_soft_deleted?: boolean;
  task_type: TaskType;
  model: string;
  source: TaskSource;
  mode: TaskMode;
  prompt: string;
  reference_images: string[];
  reference_image_thumbs: string[];
  source_image: string;
  source_image_thumb: string;
  mask_image: string;
  mask_image_thumb: string;
  num_images: number;
  size: string;
  resolution: string;
  custom_size?: string;
  credit_cost: number;
  created_at: string;
  error_message?: string;
  images: ImageResult[];
}

export interface UserHistoryResponse {
  total: number;
  items: UserHistoryCard[];
}

export interface HistoryPinTogglePayload {
  item_type: "task" | "prompt_history";
  image_id?: number | null;
  history_id?: number | null;
}

export interface HistoryPinToggleResponse {
  is_pinned: boolean;
  pinned_at?: string | null;
}

export type FeedbackStatus = "pending" | "processing" | "completed";

export interface FeedbackTaskSummary {
  task_id: string;
  model: string;
  mode: TaskMode;
  task_type: TaskType;
  source: TaskSource;
  prompt: string;
  status: string;
  created_at?: string | null;
  images: ImageResult[];
}

export interface FeedbackItem {
  feedback_id: string;
  user_id: string;
  username: string;
  task_id: string;
  status: FeedbackStatus;
  is_read: boolean;
  content: string;
  process_note: string;
  result_note: string;
  handler_id?: string | null;
  handler_name: string;
  handled_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  task: FeedbackTaskSummary;
}

export interface FeedbackDetail extends FeedbackItem {
  task_user_id: string;
}

export interface FeedbackListResponse {
  total: number;
  items: FeedbackItem[];
}

export interface FeedbackUnresolvedCountResponse {
  count: number;
}

export interface FeedbackReadCountResponse {
  count: number;
}

export interface FeedbackListQuery {
  task_id?: string;
  status?: FeedbackStatus;
}

export interface FeedbackUpdatePayload {
  status?: FeedbackStatus;
  process_note?: string;
  result_note?: string;
}

export interface AdminFeedbackQuery extends FeedbackListQuery {
  user_id?: string;
  feedback_id?: string;
}

export interface SystemMessageSender {
  user_id: string;
  username: string;
}

export interface SystemMessageRecipient {
  user_id: string;
  username: string;
  email?: string | null;
  is_read: boolean;
  read_at?: string | null;
}

export type SystemMessageRecipientScope = "selected" | "all";

export interface SystemMessageItem {
  message_id: string;
  subject: string;
  content_text: string;
  sender: SystemMessageSender;
  recipient_scope: SystemMessageRecipientScope;
  recipient_count: number;
  is_read: boolean;
  read_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SystemMessageDetail extends SystemMessageItem {
  content_html: string;
  recipients?: SystemMessageRecipient[];
}

export interface SystemMessageListResponse {
  total: number;
  items: SystemMessageItem[];
}

export interface SystemMessageReadCountResponse {
  count: number;
}

export interface SystemMessageCreatePayload {
  subject: string;
  content_html: string;
  recipient_scope: SystemMessageRecipientScope;
  recipient_user_ids: string[];
}

export interface AdminUser {
  id: string;
  username: string;
  email?: string | null;
  avatar_url?: string;
  role: string;
  status: string;
  is_whitelisted: boolean;
  credits: number;
  consumed_credits: number;
  created_at: string;
}

export interface CreditLog {
  id: number;
  user_id: string;
  username: string;
  amount: number;
  type: "allocate" | "consume";
  mode: TaskType | "manual" | "redeem";
  description: string;
  operator_name: string;
  task_id?: string;
  created_at: string;
}

export type RedeemKeyStatus = "enabled" | "disabled";

export interface RedeemCreditResult {
  message: string;
  credit_amount: number;
  credits: number;
  redeem_key: string;
  used_at?: string | null;
}

export interface AdminRedeemKey {
  id: number;
  redeem_key: string;
  credit_amount: number;
  batch_no: string;
  status: RedeemKeyStatus;
  is_used: boolean;
  used_at?: string | null;
  used_by_user_id?: string | null;
  used_by_username: string;
  used_by_user_email: string;
  created_by_user_id?: string | null;
  created_by_username: string;
  created_at?: string | null;
}

export interface AdminRedeemKeyBatchResult {
  batch_no: string;
  credit_amount: number;
  count: number;
  items: AdminRedeemKey[];
}

export interface TemplateTag {
  id: number;
  name: string;
  template_count?: number;
}

export interface CreativeTemplate {
  id: number;
  prompt: string;
  model: string;
  reference_images: string[];
  reference_image_thumbs?: string[];
  num_images: number;
  size: string;
  resolution: string;
  custom_size: string;
  result_image: string;
  result_image_thumb?: string;
  sort_order: number;
  tags: TemplateTag[];
  created_at: string;
}

export interface TemplateListResponse {
  total: number;
  items: CreativeTemplate[];
}

export interface AdminStats {
  total_users: number;
  total_tasks: number;
  total_credit_cost: number;
  active_users: number;
}

export type AdminAnalyticsGranularity = "day" | "week" | "month";

export interface AdminAnalyticsQuery {
  granularity: AdminAnalyticsGranularity;
  start_date?: string;
  end_date?: string;
  user_id?: string;
  source?: TaskSource;
  model?: string;
  mode?: TaskType;
  status?: string;
}

export interface AdminAnalyticsMetric {
  current: number;
  previous: number;
  delta: number;
  delta_pct?: number | null;
}

export interface AdminAnalyticsSummary {
  granularity: AdminAnalyticsGranularity;
  current_range_label: string;
  previous_range_label: string;
  total_users: number;
  tasks_created: AdminAnalyticsMetric;
  success_tasks: AdminAnalyticsMetric;
  failed_tasks: AdminAnalyticsMetric;
  credits_consumed: AdminAnalyticsMetric;
  new_users: AdminAnalyticsMetric;
  active_users: AdminAnalyticsMetric;
}

export interface AdminAnalyticsTimeseriesPoint {
  label: string;
  bucket_start?: string | null;
  bucket_end?: string | null;
  tasks_created: number;
  success_tasks: number;
  failed_tasks: number;
  credits_consumed: number;
  new_users: number;
  active_users: number;
}

export interface AdminAnalyticsTimeseries {
  granularity: AdminAnalyticsGranularity;
  current_range_label: string;
  previous_range_label: string;
  current: AdminAnalyticsTimeseriesPoint[];
  previous: AdminAnalyticsTimeseriesPoint[];
}

export interface AdminAnalyticsBreakdownItem {
  name: string;
  count: number;
  credit_cost: number;
}

export interface AdminAnalyticsBreakdown {
  range_label: string;
  status_breakdown: AdminAnalyticsBreakdownItem[];
  source_breakdown: AdminAnalyticsBreakdownItem[];
  mode_breakdown: AdminAnalyticsBreakdownItem[];
  model_breakdown: AdminAnalyticsBreakdownItem[];
  top_users_by_tasks: AdminAnalyticsBreakdownItem[];
  top_users_by_credit: AdminAnalyticsBreakdownItem[];
}

export interface AdminConfig {
  id: number;
  contact_qr_image: string;
  announcement_enabled: boolean;
  announcement_content: string;
  announcement_updated_at?: string | null;
  updated_at: string;
}

export interface ExternalApiSecretConfig {
  id: number;
  key: string;
  tongyi_key: string;
  updated_at?: string | null;
}

export interface CosConfig {
  id: number;
  cos_secret_id: string;
  cos_secret_key: string;
  cos_bucket: string;
  cos_region: string;
  cos_public_base_url: string;
  updated_at?: string | null;
}

export interface AnnouncementConfig {
  announcement_enabled: boolean;
  announcement_content: string;
  announcement_updated_at?: string | null;
}

export type ExternalApiConfigStatus = "enabled" | "disabled";
export type ExternalApiRequestFormat = "json" | "multipart";
export type ExternalApiSceneType = "generate" | "image_edit" | "prompt_reverse" | "inpaint";

export interface SceneOptionItem {
  label: string;
  value: string;
}

export interface ExternalApiConfig {
  id: number;
  name: string;
  description: string;
  group_name: string;
  request_url: string;
  request_format: ExternalApiRequestFormat;
  headers_json: string;
  payload_json: string;
  response_json: string;
  result_base64_field: string;
  status: ExternalApiConfigStatus;
  created_at: string;
  updated_at?: string;
}

export interface ExternalApiConfigPayload {
  name: string;
  description: string;
  group_name: string;
  request_url: string;
  request_format: ExternalApiRequestFormat;
  headers_json: string;
  payload_json: string;
  response_json: string;
  result_base64_field: string;
  status: ExternalApiConfigStatus;
}

export interface ExternalApiSceneBinding {
  scene_key: string;
  scene_type: ExternalApiSceneType;
  scene_label: string;
  scene_description: string;
  display_name: string;
  subtitle: string;
  sort_order: number;
  hide_aspect_ratio: boolean;
  hide_resolution: boolean;
  hide_custom_size: boolean;
  status: ExternalApiConfigStatus;
  is_builtin: boolean;
  api_config_id?: number | null;
  api_config_name: string;
  api_group_name: string;
  api_status?: ExternalApiConfigStatus | null;
  credit_cost: number;
  max_reference_images: number;
  aspect_ratio_options_json: string;
  image_size_options_json: string;
  custom_size_options_json: string;
}

export interface ExternalApiSceneBindingCreatePayload {
  scene_key: string;
  scene_type: Extract<ExternalApiSceneType, "generate" | "image_edit">;
  scene_label: string;
  scene_description: string;
  sort_order: number;
  hide_aspect_ratio: boolean;
  hide_resolution: boolean;
  hide_custom_size: boolean;
  api_config_id: number | null;
  display_name: string;
  subtitle: string;
  credit_cost: number;
  max_reference_images: number;
  aspect_ratio_options_json: string;
  image_size_options_json: string;
  custom_size_options_json: string;
}

export interface ExternalApiSceneBindingMetaPayload {
  scene_key: string;
  scene_label: string;
  scene_description: string;
  sort_order: number;
  hide_aspect_ratio: boolean;
  hide_resolution: boolean;
  hide_custom_size: boolean;
  max_reference_images: number;
  aspect_ratio_options_json: string;
  image_size_options_json: string;
  custom_size_options_json: string;
}

export interface ExternalApiConfigTestResult {
  success: boolean;
  request_url: string;
  status_code?: number | null;
  response_preview: string;
}

export interface GenerationModelOption {
  model_key: string;
  model_label: string;
  model_description: string;
  display_name: string;
  subtitle: string;
  sort_order: number;
  hide_aspect_ratio: boolean;
  hide_resolution: boolean;
  hide_custom_size: boolean;
  credit_cost: number;
  max_reference_images: number;
  aspect_ratio_options: SceneOptionItem[];
  image_size_options: SceneOptionItem[];
  custom_size_options: SceneOptionItem[];
}

export interface TaskSceneConfig {
  scene_key: string;
  scene_type: ExternalApiSceneType;
  scene_label: string;
  scene_description: string;
  display_name: string;
  subtitle: string;
  sort_order: number;
  hide_aspect_ratio: boolean;
  hide_resolution: boolean;
  hide_custom_size: boolean;
  credit_cost: number;
  max_reference_images: number;
  aspect_ratio_options: SceneOptionItem[];
  image_size_options: SceneOptionItem[];
  custom_size_options: SceneOptionItem[];
}

export type UploadPurpose = "ref" | "source" | "mask" | "reverse" | "misc" | "template";

export interface UploadCredential {
  bucket: string;
  region: string;
  key: string;
  url: string;
  tmp_secret_id: string;
  tmp_secret_key: string;
  session_token: string;
  start_time?: number | null;
  expired_time: number;
}
