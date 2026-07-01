export interface UserInfo {
  id: string;
  business_id: string;
  username: string;
  email?: string | null;
  role: "user" | "admin" | "superadmin";
  avatar_url?: string;
  credits: number;
  is_whitelisted: boolean;
}

export interface LoginResponse {
  token: string;
  user: UserInfo;
}

export type UserApiKeyStatus = "enabled" | "disabled";

export interface UserApiKey {
  id: number;
  expire_time?: string | null;
  api_key: string;
  key_name: string;
  status: UserApiKeyStatus;
  is_delete: boolean;
  key_prefix: string;
  key_last4: string;
  created_at?: string | null;
  updated_at?: string | null;
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
export type TaskSource = "web" | "app" | "api";

export interface TaskResult {
  id: string;
  canvas_id?: number | null;
  mode: TaskMode;
  model: string;
  source: TaskSource;
  prompt: string;
  num_images: number;
  size: string;
  resolution: string;
  custom_size?: string;
  reference_images?: string[];
  reference_image_thumbs?: string[];
  source_image?: string;
  source_image_thumb?: string;
  mask_image?: string;
  mask_image_thumb?: string;
  credit_cost: number;
  credit_refunded?: boolean;
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
  canvas_id?: number | null;
  canvas_project_id?: string;
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
  credit_refunded?: boolean;
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
  board_id?: number;
  board_scope?: "default" | "all";
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
  canvas_id?: number | null;
  canvas_project_id?: string;
  image_id?: number | null;
  user_id?: string;
  username?: string;
  avatar_url?: string;
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
  credit_refunded?: boolean;
  created_at: string;
  run_time?: number | null;
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

export type BoardKey = "default" | `board:${number}`;

export interface UserBoardSummary {
  id: number | null;
  name: string;
  is_default: boolean;
  asset_count: number;
  updated_at?: string | null;
  preview_urls: string[];
}

export interface UserBoardListResponse {
  items: UserBoardSummary[];
}

export interface UserCanvasSummary {
  id: number;
  project_id: string;
  name: string;
  node_count: number;
  preview_urls: string[];
  viewport_x: number;
  viewport_y: number;
  zoom: number;
  is_readonly?: boolean;
  owner_user_id?: string;
  owner_username?: string;
  owner_avatar_url?: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CanvasNode {
  id: number;
  canvas_id: number;
  task_id: string;
  node_type: "task" | "text" | "image";
  content: string;
  image_url: string;
  x: number;
  y: number;
  width: number;
  height: number;
  z_index: number;
  created_at?: string | null;
  updated_at?: string | null;
  task?: TaskResult | null;
}

export interface CanvasEdge {
  id: number;
  canvas_id: number;
  source_node_id: number;
  target_node_id: number;
  edge_type: string;
  source_anchor: "auto" | "top" | "right" | "bottom" | "left";
  target_anchor: "auto" | "top" | "right" | "bottom" | "left";
  is_collapsed: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CanvasDetail extends UserCanvasSummary {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
}

export interface UserCanvasListResponse {
  items: UserCanvasSummary[];
}

export interface CanvasTaskPayload {
  model?: string;
  source?: "web" | "app" | "api";
  prompt: string;
  num_images: number;
  size: string;
  resolution: string;
  custom_size?: string;
  mode?: "generate" | "inpaint";
  reference_images?: string[];
  source_node_ids?: number[];
  source_image?: string;
  mask_image?: string;
  x: number;
  y: number;
  width?: number;
  height?: number;
}

export interface CanvasTaskCreateResponse {
  task_id?: string | null;
  task_ids: string[];
  nodes: CanvasNode[];
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
  error_message?: string;
  credit_refunded?: boolean;
  created_at?: string | null;
  reference_images: string[];
  reference_image_thumbs: string[];
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

export interface AdminUserPromoDashboard {
  user_id: string;
  username: string;
  summary: PromoCodeSummary;
  promo_codes: PromoCodeItem[];
  referrals: PromoReferralItem[];
  activities: PromoReferralActivityItem[];
}

export interface CreditLog {
  id: number;
  user_id: string;
  username: string;
  amount: number;
  type: "allocate" | "consume";
  mode: TaskType | "manual" | "redeem" | "purchase";
  description: string;
  operator_name: string;
  task_id?: string;
  created_at: string;
}

export interface PaymentPlan {
  key: string;
  title: string;
  amount_fen: number;
  display_amount: string;
  credits: number;
  tag: string;
  purchasable: boolean;
  disabled_reason: string;
}

export interface PaymentOrder {
  order_no: string;
  plan_key: string;
  subject: string;
  amount_fen: number;
  credits: number;
  status: "created" | "pending_pay" | "paid" | "credited" | "closed" | "failed";
  paid_at?: string | null;
  credited_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CreatePaymentOrderResult {
  order_no: string;
  status: "created" | "pending_pay" | "paid" | "credited" | "closed" | "failed";
  amount_fen: number;
  credits: number;
  subject: string;
  pay_url: string;
  result_token: string;
}

export type RedeemKeyStatus = "enabled" | "disabled";

export interface RedeemCreditResult {
  message: string;
  credit_amount: number;
  credits: number;
  redeem_key: string;
  used_at?: string | null;
}

export interface PromoCodeSummary {
  total_referrals: number;
  used_code_count: number;
  rewarded_registrations: number;
}

export interface PromoCodeItem {
  id: number;
  code: string;
  platform_name: string;
  status: string;
  created_at?: string | null;
  referral_count: number;
}

export interface PromoCodeListResponse {
  summary: PromoCodeSummary;
  items: PromoCodeItem[];
}

export interface PromoReferralItem {
  user_id: string;
  username: string;
  email_masked: string;
  email?: string | null;
  promo_code: string;
  platform_name: string;
  reward_credits: number;
  registered_at?: string | null;
}

export interface PromoReferralListResponse {
  total: number;
  items: PromoReferralItem[];
}

export interface PromoReferralActivityItem {
  user_id: string;
  username: string;
  email_masked: string;
  activity_type: "purchase" | "redeem";
  credits: number;
  amount_fen?: number | null;
  amount_yuan?: number | null;
  redeem_key: string;
  order_no: string;
  occurred_at?: string | null;
}

export interface PromoReferralActivityListResponse {
  total: number;
  items: PromoReferralActivityItem[];
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

export type AdminAnalyticsGranularity = "3hour" | "day" | "week" | "month";

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

export interface AdminDailyReportTestResult {
  sent: boolean;
  report_date: string;
  range_start: string;
  range_end: string;
  revenue_fen: number;
  revenue_yuan: number;
  total_revenue_yuan: number;
  paid_order_count: number;
  offline_order_revenue_fen: number;
  offline_order_revenue_yuan: number;
  offline_order_count: number;
  redeem_revenue_yuan: number;
  redeem_used_count: number;
  task_total_count: number;
  task_success_count: number;
  task_failed_count: number;
  credit_consumed: number;
}

export interface AdminDailyReportRangePayload {
  start_date: string;
  end_date: string;
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

export interface AdminAnalyticsRedeemRevenueItem {
  credit_amount: number;
  unit_price: number;
  used_count: number;
  total_amount: number;
}

export interface AdminAnalyticsRedeemRevenue {
  range_label: string;
  items: AdminAnalyticsRedeemRevenueItem[];
  total_used_count: number;
  total_amount: number;
}

export interface AdminErrorAnalyticsItem {
  error_category: string;
  error_message: string;
  count: number;
}

export interface AdminErrorAnalytics {
  range_label: string;
  total_failed_tasks: number;
  distinct_error_categories: number;
  distinct_error_messages: number;
  items: AdminErrorAnalyticsItem[];
}

export interface AdminErrorCategoryTimeseriesSeries {
  error_category: string;
  total_count: number;
}

export interface AdminErrorCategoryTimeseriesPoint {
  label: string;
  bucket_start?: string | null;
  bucket_end?: string | null;
  total_failed_tasks: number;
  categories: Record<string, number>;
}

export interface AdminErrorCategoryTimeseries {
  granularity: AdminAnalyticsGranularity;
  range_label: string;
  series: AdminErrorCategoryTimeseriesSeries[];
  points: AdminErrorCategoryTimeseriesPoint[];
}

export interface AdminErrorTaskItem {
  task_id: string;
  user_id: string;
  username: string;
  avatar_url: string;
  task_type: TaskType;
  model: string;
  source: TaskSource;
  mode: TaskMode;
  prompt: string;
  status: string;
  error_message: string;
  credit_cost: number;
  credit_refunded: boolean;
  created_at?: string | null;
}

export interface AdminErrorTaskList {
  total: number;
  items: AdminErrorTaskItem[];
}

export interface AdminPaymentOrder {
  id: number;
  order_no: string;
  out_trade_no: string;
  alipay_trade_no: string;
  user_id: string;
  username: string;
  user_email: string;
  plan_key: string;
  subject: string;
  amount_fen: number;
  amount_yuan: number;
  credits: number;
  status: "created" | "pending_pay" | "paid" | "credited" | "closed" | "failed";
  trade_status: string;
  buyer_id: string;
  paid_at?: string | null;
  credited_at?: string | null;
  closed_at?: string | null;
  failed_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AdminOfflineOrder {
  id: number;
  business_id: string;
  user_id: string;
  username: string;
  user_email: string;
  order_type: "purchase" | "refund";
  credit_amount: number;
  amount_fen: number;
  amount_yuan: number;
  remark: string;
  created_by: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CreateOfflineOrderPayload {
  user_id: string;
  order_type: "purchase" | "refund";
  credit_amount: number;
  amount_yuan: number;
  remark?: string;
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
  resolution_credit_costs_json: string;
  max_reference_images: number;
  aspect_ratio_options_json: string;
  image_size_options_json: string;
  custom_size_options_json: string;
  resolution_mapping_json: string;
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
  resolution_mapping_json: string;
  resolution_credit_costs_json: string;
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
  resolution_mapping_json: string;
  resolution_credit_costs_json: string;
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
  resolution_credit_costs: Record<string, number>;
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
  resolution_credit_costs: Record<string, number>;
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
