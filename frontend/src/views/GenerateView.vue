<script setup lang="ts">
import { ref, computed, h, inject, onActivated, onBeforeUnmount, onMounted, watch, type Ref } from "vue";
import { message, Modal, notification } from "ant-design-vue";
import dayjs from "dayjs";
import { useRouter } from "vue-router";
import {
  FontSizeOutlined,
  CloseOutlined,
  CloudUploadOutlined,
  ClockCircleOutlined,
  ClearOutlined,
  CopyOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  EyeOutlined,
  PictureOutlined,
  SearchOutlined,
  HighlightOutlined,
  AppstoreOutlined,
  BarChartOutlined,
  LoadingOutlined,
  ExclamationCircleFilled,
  RedoOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
  DownOutlined,
  UndoOutlined,
  MessageOutlined,
} from "@ant-design/icons-vue";
import { getTaskScenes } from "@/api/config";
import { deleteHistoryTask, fetchHistory } from "@/api/history";
import { createTask, getTasks } from "@/api/tasks";
import { deleteImage, getDisplayImageUrl, getDownloadUrl, getPreviewImageUrl, resolveImageUrl } from "@/api/images";
import { reversePrompt } from "@/api/promptReverse";
import { uploadReferenceImage } from "@/api/upload";
import { getMe, getPromptHistory, deletePromptHistory } from "@/api/auth";
import { getMyCompletedUnreadFeedbackCount } from "@/api/feedback";
import { useAuthStore } from "@/stores/auth";
import RepaintCanvas from "@/components/generate/RepaintCanvas.vue";
import FeedbackDialog from "@/components/feedback/FeedbackDialog.vue";
import { withBaseUrl } from "@/lib/assets";
import {
  formatGenerationErrorMessage,
  formatGenerationTaskFailureMessage,
  getPreferredGenerationErrorMessage,
} from "@/lib/generationErrors";
import { setStoredUserCompletedUnreadFeedbackCount } from "@/lib/userFeedbackNotice";
import type { GenerationModelOption, ImageResult, PromptHistoryItem, SceneOptionItem, TaskResult, TaskSceneConfig, UserHistoryCard } from "@/types";

const auth = useAuthStore();
const router = useRouter();
const loginModalVisible = inject<Ref<boolean>>("loginModalVisible")!;
const openCreditsContact = inject<() => void>("openCreditsContact");
const COMPLETED_UNREAD_FEEDBACK_NOTIFICATION_KEY = "user-completed-unread-feedback";

function isInsufficientCreditsError(err: any) {
  const detail = String(err?.response?.data?.detail || err?.message || "");
  return detail.includes("积分不足");
}

function showInsufficientCreditsContact(detail?: string) {
  if (detail) {
    message.warning(detail);
  }
  openCreditsContact?.();
}

type GenerateMode = "textGenerate" | "imageEdit" | "inpaint" | "promptReverse";
const MAX_RECENT_GENERATED_TASKS = 20;
const MAX_ACTIVE_GENERATION_IMAGES = 8;
const DEFAULT_SCENE_COSTS: Record<string, number> = {
  banana: 4,
  banana2: 4,
  banana_pro: 4,
  banana_pro_plus: 4,
  banana_edit: 4,
  banana2_edit: 4,
  banana_pro_edit: 4,
  banana_pro_plus_edit: 4,
  prompt_reverse: 1,
  inpaint: 4,
};

const generateMode = ref<GenerateMode>("textGenerate");
const failedResultAsset = withBaseUrl("failed-result.svg");
const generateEmptyStateAsset = withBaseUrl("generate-task-card.svg");
const expiredResultAsset = `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(`
<svg xmlns="http://www.w3.org/2000/svg" width="960" height="960" viewBox="0 0 960 960">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#fff8ee"/>
      <stop offset="100%" stop-color="#ffe6c8"/>
    </linearGradient>
  </defs>
  <rect width="960" height="960" rx="56" fill="url(#bg)"/>
  <rect x="74" y="74" width="812" height="812" rx="42" fill="none" stroke="#efc784" stroke-dasharray="18 16" stroke-width="10"/>
  <g fill="none" stroke="#d08a24" stroke-linecap="round" stroke-linejoin="round">
    <rect x="282" y="248" width="396" height="286" rx="28" stroke-width="18"/>
    <path d="M326 490l110-108 92 88 72-66 76 86" stroke-width="18"/>
    <circle cx="400" cy="330" r="34" fill="#ffd585" stroke-width="12"/>
  </g>
  <text x="480" y="654" text-anchor="middle" font-size="54" font-weight="700" fill="#8c5a16">原图已过期</text>
  <text x="480" y="726" text-anchor="middle" font-size="34" fill="#a9742e">服务器仅保留 15 天原图</text>
  <text x="480" y="776" text-anchor="middle" font-size="34" fill="#a9742e">请在有效期内查看或下载</text>
</svg>
`)}`;
const prompt = ref("");
const repaintPrompt = ref("");
const TASK_PROMPT_MAX_LENGTH = 5000;
const selectedModel = ref("");
const numImages = ref(1);
const resolution = ref("2K");
const size = ref("9:16");
const customSize = ref("");

type GeneratedTaskStatus = TaskResult["status"] | "submitting";
type SubmitMode = Exclude<GenerateMode, "promptReverse">;

interface GeneratedTaskItem {
  localId: string;
  taskId: string | null;
  mode: SubmitMode;
  prompt: string;
  model?: string;
  numImages: number;
  size: string;
  resolution: string;
  customSize: string;
  referenceImages: string[];
  sourceImage?: string;
  maskImage?: string;
  createdAt: string;
  status: GeneratedTaskStatus;
  errorMessage?: string;
  creditRefunded?: boolean;
  images: ImageResult[];
}

const generatedTasks = ref<GeneratedTaskItem[]>([]);
const taskPollTimer = ref<ReturnType<typeof setInterval> | null>(null);
const taskPollingInFlight = ref(false);

type UploadItemStatus = "uploading" | "success" | "failed";

interface UploadPreviewItem {
  id: string;
  localUrl: string;
  remoteUrl: string;
  status: UploadItemStatus;
  objectUrl?: string;
}

const DEFAULT_MAX_REFERENCE_IMAGES = 6;
const referenceItems = ref<UploadPreviewItem[]>([]);
const fileInput = ref<HTMLInputElement | null>(null);
const sourceImageUrl = ref("");
const sourcePreviewUrl = ref("");
const repaintMaskUrl = ref("");
const sourceUploading = ref(false);
const sourceInput = ref<HTMLInputElement | null>(null);
const reverseImageUrl = ref("");
const reverseUploading = ref(false);
const reverseInput = ref<HTMLInputElement | null>(null);
const reverseLoading = ref(false);
const reversePromptResult = ref("");
const brushSize = ref(28);
const repaintTool = ref<"paint" | "erase">("paint");
const hasRepaintMask = ref(false);
const canUndoMask = ref(false);
const canRedoMask = ref(false);
const repaintCanvasRef = ref<{
  clearMask: () => void;
  hasDrawnMask: () => boolean;
  exportMaskBlob: () => Promise<Blob | null>;
  undo: () => boolean;
  canUndo: () => boolean;
  redo: () => boolean;
  canRedo: () => boolean;
} | null>(null);

const previewVisible = ref(false);
const previewCurrent = ref("");
const feedbackDialogOpen = ref(false);
const feedbackTarget = ref<{
  taskId: string;
  model?: string;
  prompt: string;
  createdAt: string;
} | null>(null);
const viewportWidth = ref(typeof window === "undefined" ? 1200 : window.innerWidth);

const historyVisible = ref(false);
const historyItems = ref<PromptHistoryItem[]>([]);
const historyLoading = ref(false);
const sceneConfigLoading = ref(true);
const HISTORY_DRAFT_KEY = "generateDraftFromHistory";
const TEMPLATE_DRAFT_KEY = "generateDraftFromTemplate";
const taskScenes = ref<TaskSceneConfig[]>([]);
const DEFAULT_IMAGE_SIZE_OPTIONS: SceneOptionItem[] = [
  { label: "1K", value: "1K" },
  { label: "2K", value: "2K" },
  { label: "4K", value: "4K" },
];
const DEFAULT_CUSTOM_SIZE_OPTIONS: SceneOptionItem[] = [
  { label: "1024 x 1024", value: "1024x1024" },
  { label: "1152 x 896", value: "1152x896" },
  { label: "896 x 1152", value: "896x1152" },
  { label: "1280 x 720", value: "1280x720" },
];
const DEFAULT_ASPECT_RATIO_OPTIONS: SceneOptionItem[] = [
  { label: "■  1:1", value: "1:1" },
  { label: "▮  2:3", value: "2:3" },
  { label: "▬  3:2", value: "3:2" },
  { label: "▮  3:4", value: "3:4" },
  { label: "▬  4:3", value: "4:3" },
  { label: "▮  9:16", value: "9:16" },
  { label: "▬  16:9", value: "16:9" },
];

function toGenerationModelOption(scene: TaskSceneConfig): GenerationModelOption {
  return {
    model_key: scene.scene_key,
    model_label: scene.scene_label,
    model_description: scene.scene_description,
    display_name: scene.display_name,
    subtitle: scene.subtitle,
    sort_order: scene.sort_order,
    hide_aspect_ratio: scene.hide_aspect_ratio,
    hide_resolution: scene.hide_resolution,
    hide_custom_size: scene.hide_custom_size,
    credit_cost: scene.credit_cost,
    max_reference_images: scene.max_reference_images,
    aspect_ratio_options: scene.aspect_ratio_options,
    image_size_options: scene.image_size_options,
    custom_size_options: scene.custom_size_options,
  };
}

const resultEmptyTitle = computed(() => (
  generateMode.value === "promptReverse" ? "提示词反推结果会在左侧展示" : "生图结果将在这里展示"
));
const resultEmptyDesc = computed(() => (
  generateMode.value === "promptReverse"
    ? "上传图片后点击「开始反推」，即可得到适合 AI 绘画的中文提示词"
    : "在左侧设置提示词和参数后发起任务，右侧会展示最近 20 个生图任务结果"
));
const referenceUrls = computed(() => (
  referenceItems.value
    .filter((item) => item.status === "success" && item.remoteUrl)
    .map((item) => item.remoteUrl)
));
const uploading = computed(() => referenceItems.value.some((item) => item.status === "uploading"));
const hasPendingReferenceUploads = computed(() => referenceItems.value.some((item) => item.status === "uploading"));
const hasFailedReferenceUploads = computed(() => referenceItems.value.some((item) => item.status === "failed"));
const sourceDisplayUrl = computed(() => resolveImageUrl(sourcePreviewUrl.value || sourceImageUrl.value));
const isTextGenerateMode = computed(() => generateMode.value === "textGenerate");
const isImageEditMode = computed(() => generateMode.value === "imageEdit");
const textGenerateModels = computed(() => (
  taskScenes.value
    .filter((item) => item.scene_type === "generate" && item.scene_key !== "prompt_reverse" && item.scene_key !== "inpaint")
    .map(toGenerationModelOption)
));
const imageEditModels = computed(() => {
  const models = taskScenes.value
    .filter((item) => item.scene_type === "image_edit")
    .map(toGenerationModelOption);
  return models.length ? models : textGenerateModels.value;
});
const generationModels = computed(() => (isImageEditMode.value ? imageEditModels.value : textGenerateModels.value));
const hasBlockedUploads = computed(() => {
  if (generateMode.value === "inpaint") {
    return !!sourcePreviewUrl.value && !sourceImageUrl.value;
  }
  if (isImageEditMode.value) {
    return hasPendingReferenceUploads.value || hasFailedReferenceUploads.value;
  }
  return false;
});
const canClickGenerate = computed(() => {
  if (hasBlockedUploads.value) return false;
  if (isImageEditMode.value) return true;
  return !!activePrompt.value.trim();
});
const activeGenerationImageCount = computed(() => (
  generatedTasks.value.reduce((total, task) => {
    if (!["submitting", "pending", "queued", "processing"].includes(task.status)) return total;
    return total + Math.max(task.images.length, task.numImages || 1);
  }, 0)
));
const remainingGenerationImageSlots = computed(() => Math.max(
  MAX_ACTIVE_GENERATION_IMAGES - activeGenerationImageCount.value,
  0
));
const selectedModelOption = computed(
  () => generationModels.value.find((item) => item.model_key === selectedModel.value) || null
);
const maxReferenceImages = computed(() => {
  if (!isImageEditMode.value) return 0;
  const configured = Number(selectedModelOption.value?.max_reference_images || 0);
  return configured > 0 ? configured : DEFAULT_MAX_REFERENCE_IMAGES;
});
const sizeOptions = computed(() => (
  selectedModelOption.value?.aspect_ratio_options?.length
    ? selectedModelOption.value.aspect_ratio_options
    : DEFAULT_ASPECT_RATIO_OPTIONS
));
const resolutionOptions = computed(() => (
  selectedModelOption.value?.image_size_options?.length
    ? selectedModelOption.value.image_size_options
    : DEFAULT_IMAGE_SIZE_OPTIONS
));
const customSizeOptions = computed(() => (
  selectedModelOption.value?.custom_size_options?.length
    ? selectedModelOption.value.custom_size_options
    : DEFAULT_CUSTOM_SIZE_OPTIONS
));
const hideAspectRatio = computed(() => (
  (isTextGenerateMode.value || isImageEditMode.value) && !!selectedModelOption.value?.hide_aspect_ratio
));
const hideResolution = computed(() => (
  (isTextGenerateMode.value || isImageEditMode.value) && !!selectedModelOption.value?.hide_resolution
));
const hideCustomSize = computed(() => (
  (isTextGenerateMode.value || isImageEditMode.value) && !!selectedModelOption.value?.hide_custom_size
));
const sceneCostMap = computed(() => Object.fromEntries(taskScenes.value.map((item) => [item.scene_key, item.credit_cost])));
const selectedModelCreditCost = computed(() => (
  selectedModelOption.value?.credit_cost
  ?? sceneCostMap.value[selectedModel.value]
  ?? DEFAULT_SCENE_COSTS[selectedModel.value]
  ?? 0
));
const promptReverseCreditCost = computed(() => sceneCostMap.value.prompt_reverse ?? DEFAULT_SCENE_COSTS.prompt_reverse);
const inpaintCreditCost = computed(() => sceneCostMap.value.inpaint ?? DEFAULT_SCENE_COSTS.inpaint);
const isExtendedToolMode = computed(() => generateMode.value === "promptReverse" || generateMode.value === "inpaint");
const activeExtendedToolLabel = computed(() => (
  generateMode.value === "promptReverse"
    ? "提示词反推"
    : generateMode.value === "inpaint"
      ? "局部重绘"
      : "更多工具"
));
const activeExtendedToolMenuKeys = computed(() => (
  isExtendedToolMode.value ? [generateMode.value] : []
));

watch(
  () => maxReferenceImages.value,
  (limit) => {
    if (!isImageEditMode.value || limit <= 0 || referenceItems.value.length <= limit) return;
    const removedItems = referenceItems.value.slice(limit);
    removedItems.forEach((item) => revokeObjectUrl(item.objectUrl));
    referenceItems.value = referenceItems.value.slice(0, limit);
    message.warning(`当前模型最多支持 ${limit} 张参考图，已自动保留前 ${limit} 张`);
  }
);

const accentIndicatorStyle = { fontSize: "20px", color: "var(--theme-accent)" };
const smallAccentIndicatorStyle = { fontSize: "18px", color: "var(--theme-accent)" };
const neutralIndicatorStyle = { fontSize: "24px", color: "var(--text-secondary)" };

type GenerateTaskPayload = {
  model?: string;
  prompt: string;
  num_images: number;
  size: string;
  resolution: string;
  custom_size?: string;
  mode?: "generate" | "inpaint";
  reference_images?: string[];
  source_image?: string;
  mask_image?: string;
};

type GeneratedTaskDraft = Omit<GeneratedTaskItem, "localId" | "taskId" | "createdAt" | "status" | "images">;

function createPendingImages(count: number) {
  return Array.from({ length: count }, (_, index) => ({
    id: -(Date.now() + index + Math.floor(Math.random() * 1000)),
    image_url: "",
    status: "pending" as const,
  }));
}

function parseAspectRatio(value?: string) {
  if (!value) return null;
  const normalized = value.trim();
  const ratioMatch = normalized.match(/^(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)$/);
  if (ratioMatch) {
    const width = Number(ratioMatch[1]);
    const height = Number(ratioMatch[2]);
    if (width > 0 && height > 0) return `${width} / ${height}`;
  }

  const sizeMatch = normalized.match(/^(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)$/);
  if (sizeMatch) {
    const width = Number(sizeMatch[1]);
    const height = Number(sizeMatch[2]);
    if (width > 0 && height > 0) return `${width} / ${height}`;
  }

  return null;
}

function getTaskAspectRatio(task: GeneratedTaskItem) {
  return parseAspectRatio(task.customSize) || parseAspectRatio(task.size) || "1 / 1";
}

function getTaskAspectRatioValue(task: GeneratedTaskItem) {
  const ratio = getTaskAspectRatio(task);
  const [widthText, heightText] = ratio.split("/").map((item) => item.trim());
  const width = Number(widthText);
  const height = Number(heightText);
  if (!width || !height) return 1;
  return width / height;
}

function createLocalGeneratedTask(taskDraft: GeneratedTaskDraft): GeneratedTaskItem {
  return {
    localId: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    taskId: null,
    ...taskDraft,
    numImages: 1,
    createdAt: new Date().toISOString(),
    status: "submitting",
    errorMessage: "",
    creditRefunded: false,
    images: createPendingImages(1),
  };
}

function limitGeneratedTasks(tasks: GeneratedTaskItem[]) {
  return tasks.slice(0, MAX_RECENT_GENERATED_TASKS);
}

function isGeneratedTaskExpired(task: Pick<GeneratedTaskItem, "createdAt" | "status">) {
  if (task.status !== "success") return false;
  if (!task.createdAt) return false;
  return dayjs().diff(dayjs(task.createdAt), "day", true) >= 15;
}

const resultItems = computed(() => (
  generatedTasks.value.flatMap((task) => task.images.map((img, index) => ({
    taskLocalId: task.localId,
    taskId: task.taskId,
    task,
    image: img,
    index,
  })))
));

const resultColumnCount = computed(() => {
  if (viewportWidth.value <= 640) return 1;
  if (viewportWidth.value <= 960) return 2;
  return 3;
});

const resultColumns = computed(() => {
  const columns = Array.from({ length: resultColumnCount.value }, () => [] as typeof resultItems.value);
  const columnHeights = Array.from({ length: resultColumnCount.value }, () => 0);
  const fixedRowItems = resultColumnCount.value * 2;

  resultItems.value.forEach((item, itemIndex) => {
    let columnIndex = 0;
    if (itemIndex < fixedRowItems) {
      columnIndex = itemIndex % resultColumnCount.value;
    } else {
      columnIndex = columnHeights.reduce((bestIndex, height, index, list) => (
        height < list[bestIndex] ? index : bestIndex
      ), 0);
    }

    columns[columnIndex].push(item);
    columnHeights[columnIndex] += 1 / getTaskAspectRatioValue(item.task);
  });
  return columns;
});

function syncViewportWidth() {
  viewportWidth.value = window.innerWidth;
}

function updateGeneratedTask(localId: string, updater: (task: GeneratedTaskItem) => GeneratedTaskItem) {
  generatedTasks.value = generatedTasks.value.map((task) => (
    task.localId === localId ? updater(task) : task
  ));
}

function updateGeneratedTaskByTaskId(taskId: string, updater: (task: GeneratedTaskItem) => GeneratedTaskItem) {
  generatedTasks.value = generatedTasks.value.map((task) => (
    task.taskId === taskId ? updater(task) : task
  ));
}

const activePollingTaskIds = computed(() => (
  generatedTasks.value
    .filter((task) => task.taskId && task.status !== "success" && task.status !== "failed")
    .map((task) => task.taskId as string)
));

function stopAllTaskPolling() {
  if (taskPollTimer.value) {
    clearInterval(taskPollTimer.value);
    taskPollTimer.value = null;
  }
  taskPollingInFlight.value = false;
}

function handleExtendedToolMenuClick({ key }: { key: string }) {
  if (key === "promptReverse" || key === "inpaint") {
    generateMode.value = key;
  }
}

function syncTaskFromResult(taskId: string, data: TaskResult) {
  const current = generatedTasks.value.find((task) => task.taskId === taskId);
  if (!current) return;
  const previousStatus = current.status;
  const nextErrorMessage = data.error_message || data.images.find((image) => image.status === "failed" && image.error_message)?.error_message || "";
  updateGeneratedTaskByTaskId(taskId, (task) => ({
    ...task,
    status: data.status,
    errorMessage: nextErrorMessage,
    creditRefunded: Boolean(data.credit_refunded),
    createdAt: data.created_at || task.createdAt,
    model: data.model || task.model,
    size: data.size || task.size,
    resolution: data.resolution || task.resolution,
    customSize: data.custom_size || task.customSize,
    numImages: data.num_images || task.numImages,
    images: data.images.length ? data.images : task.images,
  }));
  if (previousStatus !== data.status && (data.status === "success" || data.status === "failed")) {
    data.status === "success"
      ? message.success(`任务 #${taskId} 已完成`)
      : message.warning(formatGenerationTaskFailureMessage(nextErrorMessage, Boolean(data.credit_refunded)));
  }
}

function syncTasksFromResults(items: TaskResult[]) {
  items.forEach((item) => syncTaskFromResult(item.id, item));
}

async function refreshTasks(taskIds = activePollingTaskIds.value) {
  if (!taskIds.length) {
    stopAllTaskPolling();
    return [];
  }
  const items = await getTasks(taskIds);
  syncTasksFromResults(items);
  if (!activePollingTaskIds.value.length) {
    stopAllTaskPolling();
  }
  return items;
}

function convertHistoryCardToGeneratedTask(item: UserHistoryCard): GeneratedTaskItem {
  const fallbackImageCount = Math.max(1, Number(item.num_images || item.images.length || 1));
  const taskMode: SubmitMode = item.mode === "inpaint"
    ? "inpaint"
    : Array.isArray(item.reference_images) && item.reference_images.length
      ? "imageEdit"
      : "textGenerate";
  return {
    localId: `history-${item.task_id || item.history_id || "unknown"}`,
    taskId: item.task_id || null,
    mode: taskMode,
    prompt: item.prompt || "",
    model: item.model || undefined,
    numImages: fallbackImageCount,
    size: item.size || "9:16",
    resolution: item.resolution || "2K",
    customSize: item.custom_size || "",
    referenceImages: Array.isArray(item.reference_images) ? item.reference_images : [],
    sourceImage: item.source_image || undefined,
    maskImage: item.mask_image || undefined,
    createdAt: item.created_at,
    status: item.status as GeneratedTaskStatus,
    errorMessage: item.error_message || item.images.find((image) => image.status === "failed" && image.error_message)?.error_message || "",
    creditRefunded: Boolean(item.credit_refunded),
    images: item.images.length ? item.images : createPendingImages(fallbackImageCount),
  };
}

function getGeneratedTaskFailureMessage(task: GeneratedTaskItem, image: ImageResult) {
  return getPreferredGenerationErrorMessage(task.errorMessage, image.error_message, Boolean(task.creditRefunded), "生成失败，请重试");
}

function isGeneratedResultFailed(task: GeneratedTaskItem, image: ImageResult) {
  return task.status === "failed" && image.status === "failed";
}

function canRemoveGeneratedResult(task: GeneratedTaskItem, image: ImageResult) {
  return image.status === "success" || isGeneratedResultFailed(task, image);
}

async function loadRecentGeneratedTasks() {
  if (!auth.isLoggedIn) {
    generatedTasks.value = [];
    stopAllTaskPolling();
    return;
  }

  try {
    const seenTaskIds = new Set<string>();
    const recentHistoryItems: UserHistoryCard[] = [];
    let page = 1;
    let total = Infinity;

    while (recentHistoryItems.length < total && seenTaskIds.size < MAX_RECENT_GENERATED_TASKS) {
      const res = await fetchHistory(page, MAX_RECENT_GENERATED_TASKS, {
        respect_pins: false,
        include_prompt_reverse: false,
      });
      total = res.total;
      if (!res.items.length) break;

      res.items.forEach((item) => {
        if (item.mode === "promptReverse" || !item.task_id || seenTaskIds.has(item.task_id)) return;
        seenTaskIds.add(item.task_id);
        recentHistoryItems.push(item);
      });
      page += 1;
    }

    const recentTasks = recentHistoryItems
      .slice(0, MAX_RECENT_GENERATED_TASKS)
      .map(convertHistoryCardToGeneratedTask);

    generatedTasks.value = limitGeneratedTasks(recentTasks);

    if (!activePollingTaskIds.value.length) {
      stopAllTaskPolling();
      return;
    }

    try {
      const items = await refreshTasks(activePollingTaskIds.value);
      if (items.some((item) => item.status !== "success" && item.status !== "failed")) startTaskPolling();
    } catch {
      startTaskPolling();
    }
  } catch {
    stopAllTaskPolling();
  }
}

function startTaskPolling() {
  if (taskPollTimer.value) return;
  taskPollTimer.value = setInterval(async () => {
    if (taskPollingInFlight.value || !activePollingTaskIds.value.length) {
      if (!activePollingTaskIds.value.length) stopAllTaskPolling();
      return;
    }
    taskPollingInFlight.value = true;
    try {
      await refreshTasks();
    } catch {
      stopAllTaskPolling();
    } finally {
      taskPollingInFlight.value = false;
    }
  }, 5000);
}

function getTaskDraftCreditCost(task: GeneratedTaskItem, nextNumImages = task.numImages) {
  if (task.mode === "inpaint") return inpaintCreditCost.value;
  const perImageCost = task.model
    ? generationModels.value.find((item) => item.model_key === task.model)?.credit_cost
      ?? sceneCostMap.value[task.model]
      ?? DEFAULT_SCENE_COSTS[task.model]
      ?? selectedModelCreditCost.value
    : selectedModelCreditCost.value;
  return nextNumImages * perImageCost;
}

async function submitGeneratedTask(
  payload: GenerateTaskPayload,
  taskDraft: GeneratedTaskDraft
) {
  const taskCount = Math.max(1, payload.num_images);
  const localTasks = Array.from({ length: taskCount }, () => createLocalGeneratedTask(taskDraft));
  const localTaskIds = new Set(localTasks.map((task) => task.localId));
  generatedTasks.value = limitGeneratedTasks([...localTasks, ...generatedTasks.value]);

  try {
    const res = await createTask(payload);
    const taskIds = res.task_ids?.length ? res.task_ids : (res.task_id ? [res.task_id] : []);
    if (taskIds.length > 1 && taskIds.length <= localTasks.length) {
      const acceptedLocalTasks = localTasks.slice(0, taskIds.length);
      const extraTaskIds = new Set(localTasks.slice(taskIds.length).map((task) => task.localId));
      generatedTasks.value = generatedTasks.value.filter((task) => !extraTaskIds.has(task.localId));
      acceptedLocalTasks.forEach((localTask, index) => {
        const taskId = taskIds[index];
        updateGeneratedTask(localTask.localId, (task) => ({ ...task, taskId, status: "pending" }));
      });
      if (taskIds.length < localTasks.length) {
        message.info(`当前剩余 ${taskIds.length} 个生成名额，已自动发起 ${taskIds.length} 个任务`);
      }
      try {
        const items = await refreshTasks(taskIds);
        if (items.some((item) => item.status !== "success" && item.status !== "failed")) startTaskPolling();
      } catch {
        startTaskPolling();
      }
    } else if (taskIds.length === 1) {
      const legacyTaskId = taskIds[0];
      const [primaryTask, ...extraTasks] = localTasks;
      const extraTaskIds = new Set(extraTasks.map((task) => task.localId));

      generatedTasks.value = generatedTasks.value
        .filter((task) => !extraTaskIds.has(task.localId))
        .map((task) => (
          task.localId === primaryTask.localId
            ? {
                ...task,
                taskId: legacyTaskId,
                numImages: taskCount,
                status: "pending",
                images: createPendingImages(taskCount),
              }
            : task
        ));

      try {
        const items = await refreshTasks([legacyTaskId]);
        if (items.some((item) => item.status !== "success" && item.status !== "failed")) startTaskPolling();
      } catch {
        startTaskPolling();
      }
    } else {
      throw new Error("服务端返回的任务数量异常");
    }

    getMe().then((u) => auth.updateUser(u)).catch(() => {});
  } catch (err: any) {
    generatedTasks.value = generatedTasks.value.filter((task) => !localTaskIds.has(task.localId));
    throw err;
  }
}

async function ensureAuthenticated() {
  if (!auth.isLoggedIn) {
    loginModalVisible.value = true;
    return false;
  }
  try {
    auth.updateUser(await getMe());
    return true;
  } catch {
    loginModalVisible.value = true;
    return false;
  }
}

async function triggerUpload() {
  if (!(await ensureAuthenticated())) return;
  fileInput.value?.click();
}

function revokeObjectUrl(url?: string) {
  if (url?.startsWith("blob:")) URL.revokeObjectURL(url);
}

function syncReferenceItems(urls: string[]) {
  referenceItems.value.forEach((item) => revokeObjectUrl(item.objectUrl));
  referenceItems.value = urls.map((url, index) => ({
    id: `${Date.now()}-${index}-${url}`,
    localUrl: url,
    remoteUrl: url,
    status: "success",
  }));
}

function getReferencePreviewUrl(item: UploadPreviewItem) {
  return resolveImageUrl(item.localUrl || item.remoteUrl);
}

function updateReferenceItem(id: string, patch: Partial<UploadPreviewItem>) {
  const index = referenceItems.value.findIndex((item) => item.id === id);
  if (index === -1) return;
  referenceItems.value[index] = {
    ...referenceItems.value[index],
    ...patch,
  };
}

async function handleFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  if (!files.length) return;

  const remainingSlots = Math.max(0, maxReferenceImages.value - referenceItems.value.length);
  if (!remainingSlots) {
    message.warning(`当前模型最多上传 ${maxReferenceImages.value} 张参考图`);
    input.value = "";
    return;
  }

  const acceptedFiles = files.slice(0, remainingSlots);
  const skippedDueToLimit = files.length - acceptedFiles.length;

  if (skippedDueToLimit > 0) {
    message.warning(`当前模型最多支持 ${maxReferenceImages.value} 张参考图，本次仅上传前 ${acceptedFiles.length} 张`);
  }

  let uploadedCount = 0;
  let failedCount = 0;
  let oversizedCount = 0;

  try {
    for (const file of acceptedFiles) {
      if (file.size > 10 * 1024 * 1024) {
        oversizedCount += 1;
        continue;
      }

      const objectUrl = URL.createObjectURL(file);
      const item: UploadPreviewItem = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        localUrl: objectUrl,
        remoteUrl: "",
        status: "uploading",
        objectUrl,
      };
      referenceItems.value.push(item);

      try {
        const res = await uploadReferenceImage(file, "ref");
        revokeObjectUrl(objectUrl);
        updateReferenceItem(item.id, {
          objectUrl: undefined,
          localUrl: res.url,
          remoteUrl: res.url,
          status: "success",
        });
        uploadedCount += 1;
      } catch {
        updateReferenceItem(item.id, { status: "failed" });
        failedCount += 1;
      }
    }
  } finally {
    input.value = "";
  }

  if (uploadedCount > 0) {
    message.success(`成功上传 ${uploadedCount} 张参考图`);
  }
  if (oversizedCount > 0) {
    message.warning(`${oversizedCount} 张图片超过 10MB，已跳过`);
  }
  if (failedCount > 0) {
    message.error(`${failedCount} 张参考图上传失败，请重试`);
  }
}

function removeReference(index: number) {
  const item = referenceItems.value[index];
  if (item) revokeObjectUrl(item.objectUrl);
  referenceItems.value.splice(index, 1);
}

async function triggerSourceUpload() {
  if (!(await ensureAuthenticated())) return;
  sourceInput.value?.click();
}

async function handleSourceFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;

  if (file.size > 10 * 1024 * 1024) {
    message.warning("图片大小不能超过 10MB");
    input.value = "";
    return;
  }

  revokeObjectUrl(sourcePreviewUrl.value);
  sourcePreviewUrl.value = URL.createObjectURL(file);
  sourceImageUrl.value = "";
  sourceUploading.value = true;
  try {
    const res = await uploadReferenceImage(file, "source");
    sourceImageUrl.value = res.url;
    repaintMaskUrl.value = "";
    hasRepaintMask.value = false;
    repaintCanvasRef.value?.clearMask();
    message.success("原图上传成功");
  } catch {
    message.error("原图上传失败，请重试");
  } finally {
    sourceUploading.value = false;
    input.value = "";
  }
}

function removeSourceImage() {
  revokeObjectUrl(sourcePreviewUrl.value);
  sourcePreviewUrl.value = "";
  sourceImageUrl.value = "";
  repaintMaskUrl.value = "";
  hasRepaintMask.value = false;
  canUndoMask.value = false;
  canRedoMask.value = false;
}

async function triggerReverseUpload() {
  if (!(await ensureAuthenticated())) return;
  reverseInput.value?.click();
}

async function handleReverseFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;

  if (file.size > 10 * 1024 * 1024) {
    message.warning("图片大小不能超过 10MB");
    input.value = "";
    return;
  }

  reverseUploading.value = true;
  try {
    const res = await uploadReferenceImage(file, "reverse");
    reverseImageUrl.value = res.url;
    reversePromptResult.value = "";
    message.success("反推图片上传成功");
  } catch {
    message.error("图片上传失败，请重试");
  } finally {
    reverseUploading.value = false;
    input.value = "";
  }
}

function removeReverseImage() {
  reverseImageUrl.value = "";
  reversePromptResult.value = "";
}

function clearRepaintMask() {
  repaintMaskUrl.value = "";
  repaintCanvasRef.value?.clearMask();
  hasRepaintMask.value = false;
  canUndoMask.value = false;
  canRedoMask.value = false;
}

function undoRepaintMask() {
  const changed = repaintCanvasRef.value?.undo();
  if (!changed) return;
  hasRepaintMask.value = repaintCanvasRef.value?.hasDrawnMask() ?? false;
  canUndoMask.value = repaintCanvasRef.value?.canUndo() ?? false;
  canRedoMask.value = repaintCanvasRef.value?.canRedo() ?? false;
}

function redoRepaintMask() {
  const changed = repaintCanvasRef.value?.redo();
  if (!changed) return;
  hasRepaintMask.value = repaintCanvasRef.value?.hasDrawnMask() ?? false;
  canUndoMask.value = repaintCanvasRef.value?.canUndo() ?? false;
  canRedoMask.value = repaintCanvasRef.value?.canRedo() ?? false;
}

function handleMaskChange(value: boolean) {
  hasRepaintMask.value = value;
  canUndoMask.value = repaintCanvasRef.value?.canUndo() ?? false;
  canRedoMask.value = repaintCanvasRef.value?.canRedo() ?? false;
}

const creditCost = computed(() => (
  generateMode.value === "inpaint"
    ? inpaintCreditCost.value
    : numImages.value * selectedModelCreditCost.value
));
const actualSubmitImageCount = computed(() => (
  generateMode.value === "inpaint"
    ? Math.min(1, remainingGenerationImageSlots.value)
    : Math.min(numImages.value, remainingGenerationImageSlots.value)
));
const actualSubmitCreditCost = computed(() => (
  generateMode.value === "inpaint"
    ? inpaintCreditCost.value
    : actualSubmitImageCount.value * selectedModelCreditCost.value
));
const userCredits = computed(() => auth.user?.credits ?? 0);
const isSuperAdmin = computed(() => auth.isSuperAdmin);
const generateButtonText = computed(() => {
  if (generateMode.value === "inpaint" && sourceUploading.value) {
    return "原图上传中...";
  }
  if (generateMode.value === "inpaint" && sourcePreviewUrl.value && !sourceImageUrl.value) {
    return "原图未上传完成";
  }
  if (isImageEditMode.value && hasPendingReferenceUploads.value) {
    return "参考图上传中...";
  }
  if (isImageEditMode.value && hasFailedReferenceUploads.value) {
    return "参考图上传失败，请处理后再生成";
  }
  if (remainingGenerationImageSlots.value <= 0) {
    return "生成队列已满";
  }
  return isSuperAdmin.value ? "开始生成" : `开始生成 · ${actualSubmitCreditCost.value} 积分`;
});
const promptReverseButtonText = computed(() => {
  if (reverseLoading.value) return "提示词反推中...";
  return isSuperAdmin.value ? "开始反推" : `开始反推 · ${promptReverseCreditCost.value} 积分`;
});
const activePrompt = computed(() => (
  generateMode.value === "inpaint" ? repaintPrompt.value : prompt.value
));

async function handlePromptReverse() {
  if (!(await ensureAuthenticated())) return;
  if (!reverseImageUrl.value.trim()) {
    message.warning("请先上传需要反推提示词的图片");
    return;
  }
  if (!isSuperAdmin.value && userCredits.value < promptReverseCreditCost.value) {
    showInsufficientCreditsContact(`积分不足，需要 ${promptReverseCreditCost.value} 积分，当前余额 ${userCredits.value}`);
    return;
  }

  reverseLoading.value = true;
  try {
    const res = await reversePrompt(reverseImageUrl.value);
    reversePromptResult.value = res.prompt;
    message.success("提示词反推完成");
    getMe().then((u) => auth.updateUser(u)).catch(() => {});
  } catch (err: any) {
    const detail = err.response?.data?.detail || "";
    if (isInsufficientCreditsError(err)) {
      showInsufficientCreditsContact(detail);
      return;
    }
    message.error(detail || "提示词反推失败");
  } finally {
    reverseLoading.value = false;
  }
}

function copyReversePrompt() {
  if (!reversePromptResult.value.trim()) return;
  navigator.clipboard.writeText(reversePromptResult.value).then(() => {
    message.success("已复制提示词");
  });
}

function applyReversePrompt() {
  if (!reversePromptResult.value.trim()) return;
  prompt.value = reversePromptResult.value;
  generateMode.value = "textGenerate";
  message.success("已带入到文生图");
}

async function handleGenerate() {
  if (!(await ensureAuthenticated())) return;
  if (isImageEditMode.value && hasPendingReferenceUploads.value) {
    message.warning("参考图仍在上传中，请稍候再发起任务");
    return;
  }
  if (isImageEditMode.value && hasFailedReferenceUploads.value) {
    message.warning("存在上传失败的参考图，请删除或重新上传后再试");
    return;
  }
  if (isImageEditMode.value && !referenceUrls.value.length) {
    message.warning("请先上传参考图片，再开始图编辑；如无需上传图片，请切换到文生图");
    return;
  }
  if (!activePrompt.value.trim()) {
    message.warning("请输入提示词");
    return;
  }
  const availableSlots = remainingGenerationImageSlots.value;
  if (availableSlots <= 0) {
    message.warning(`当前最多允许同时生成 ${MAX_ACTIVE_GENERATION_IMAGES} 张图片，请等待部分任务完成后再试`);
    return;
  }
  if (!isSuperAdmin.value && userCredits.value < actualSubmitCreditCost.value) {
    showInsufficientCreditsContact(`积分不足，需要 ${actualSubmitCreditCost.value} 积分，当前余额 ${userCredits.value}`);
    return;
  }

  let payload: GenerateTaskPayload;
  let requestedImageCount = 1;

  if (generateMode.value === "inpaint") {
    if (!sourceImageUrl.value.trim()) {
      message.warning(sourceUploading.value ? "原图上传中，请稍候再试" : "请先上传需要局部重绘的原图");
      return;
    }
    if (!hasRepaintMask.value || !repaintCanvasRef.value?.hasDrawnMask()) {
      message.warning("请先在原图上涂抹需要重绘的区域");
      return;
    }
    const maskBlob = await repaintCanvasRef.value.exportMaskBlob();
    if (!maskBlob) {
      message.warning("蒙版生成失败，请重新涂抹后再试");
      return;
    }
    const maskFile = new File([maskBlob], `mask-${Date.now()}.png`, { type: "image/png" });
    let maskUploadUrl = "";
    try {
      const uploaded = await uploadReferenceImage(maskFile, "mask");
      maskUploadUrl = uploaded.url;
    } catch {
      message.error("蒙版上传失败，请重试");
      return;
    }
    payload = {
      mode: "inpaint",
      prompt: repaintPrompt.value,
      num_images: 1,
      size: size.value,
      resolution: resolution.value,
      custom_size: customSize.value,
      source_image: sourceImageUrl.value,
      mask_image: maskUploadUrl,
    };
  } else {
    requestedImageCount = Math.min(numImages.value, availableSlots);
    payload = {
      mode: "generate",
      model: selectedModel.value,
      prompt: prompt.value,
      num_images: requestedImageCount,
      size: hideAspectRatio.value ? "" : size.value,
      resolution: hideResolution.value ? "" : resolution.value,
      custom_size: hideCustomSize.value ? "" : customSize.value,
      reference_images: isImageEditMode.value && referenceUrls.value.length ? referenceUrls.value : undefined,
    };
    if (requestedImageCount < numImages.value) {
      message.info(`当前剩余 ${requestedImageCount} 个生成名额，已自动发起 ${requestedImageCount} 个任务`);
    }
  }

  const submitMode: SubmitMode = generateMode.value === "imageEdit"
    ? "imageEdit"
    : generateMode.value === "textGenerate"
      ? "textGenerate"
      : "inpaint";
  try {
    await submitGeneratedTask(payload, {
      mode: submitMode,
      prompt: activePrompt.value.trim(),
      model: payload.model,
      numImages: payload.num_images,
      size: payload.size,
      resolution: payload.resolution,
      customSize: payload.custom_size || "",
      referenceImages: payload.reference_images ? [...payload.reference_images] : [],
      sourceImage: payload.source_image,
      maskImage: payload.mask_image,
    });
  } catch (err: any) {
    const detail = err.response?.data?.detail || "";
    if (isInsufficientCreditsError(err)) {
      showInsufficientCreditsContact(detail);
      return;
    }
    message.error(formatGenerationErrorMessage(detail, "创建任务失败"));
  }
}

function handleReeditTask(task: GeneratedTaskItem) {
  generateMode.value = task.mode;
  size.value = task.size || "9:16";
  resolution.value = task.resolution || "2K";
  customSize.value = task.customSize || "";

  if (task.mode === "inpaint") {
    repaintPrompt.value = task.prompt;
    prompt.value = "";
    syncReferenceItems([]);
    revokeObjectUrl(sourcePreviewUrl.value);
    sourcePreviewUrl.value = "";
    sourceImageUrl.value = task.sourceImage || "";
    repaintMaskUrl.value = task.maskImage || "";
    hasRepaintMask.value = false;
    canUndoMask.value = false;
    canRedoMask.value = false;
  } else {
    generateMode.value = task.referenceImages.length ? "imageEdit" : "textGenerate";
    prompt.value = task.prompt;
    repaintPrompt.value = "";
    if (task.model) selectedModel.value = task.model;
    numImages.value = Math.min(MAX_ACTIVE_GENERATION_IMAGES, Math.max(1, Number(task.numImages || 1)));
    syncReferenceItems(task.referenceImages);
    revokeObjectUrl(sourcePreviewUrl.value);
    sourcePreviewUrl.value = "";
    sourceImageUrl.value = "";
    repaintMaskUrl.value = "";
    hasRepaintMask.value = false;
    canUndoMask.value = false;
    canRedoMask.value = false;
    repaintCanvasRef.value?.clearMask();
  }
  message.success("已回填到编辑区");
}

function handleEditImageTask(task: GeneratedTaskItem, image: ImageResult) {
  const referenceImage = image.image_url || image.preview_url || "";
  if (!referenceImage) {
    message.warning("当前结果图暂不可用于图编辑");
    return;
  }
  generateMode.value = "imageEdit";
  prompt.value = task.prompt;
  repaintPrompt.value = "";
  if (task.model) selectedModel.value = task.model;
  size.value = task.size || "9:16";
  resolution.value = task.resolution || "2K";
  customSize.value = task.customSize || "";
  numImages.value = Math.min(MAX_ACTIVE_GENERATION_IMAGES, Math.max(1, Number(task.numImages || 1)));
  syncReferenceItems([referenceImage]);
  revokeObjectUrl(sourcePreviewUrl.value);
  sourcePreviewUrl.value = "";
  sourceImageUrl.value = "";
  repaintMaskUrl.value = "";
  reverseImageUrl.value = "";
  reversePromptResult.value = "";
  hasRepaintMask.value = false;
  canUndoMask.value = false;
  canRedoMask.value = false;
  repaintCanvasRef.value?.clearMask();
  window.scrollTo({ top: 0, behavior: "smooth" });
  message.success("已切换到图编辑，并载入当前结果图");
}

async function handleRegenerate(task: GeneratedTaskItem) {
  const payload: GenerateTaskPayload = task.mode === "inpaint"
    ? {
        mode: "inpaint",
        prompt: task.prompt,
        num_images: 1,
        size: task.size,
        resolution: task.resolution,
        custom_size: task.customSize,
        source_image: task.sourceImage,
        mask_image: task.maskImage,
      }
    : {
        mode: "generate",
        model: task.model,
        prompt: task.prompt,
        num_images: 1,
        size: task.size,
        resolution: task.resolution,
        custom_size: task.customSize,
        reference_images: task.referenceImages.length ? task.referenceImages : undefined,
      };

  if (task.mode === "inpaint" && (!task.sourceImage || !task.maskImage)) {
    message.warning("当前局部重绘任务缺少完整参数，请使用重新编辑后再提交");
    return;
  }
  const regenerateCost = getTaskDraftCreditCost(task, 1);
  if (!isSuperAdmin.value && userCredits.value < regenerateCost) {
    showInsufficientCreditsContact(`积分不足，需要 ${regenerateCost} 积分，当前余额 ${userCredits.value}`);
    return;
  }
  try {
    await submitGeneratedTask(payload, {
      mode: task.mode,
      prompt: task.prompt,
      model: task.model,
      numImages: 1,
      size: task.size,
      resolution: task.resolution,
      customSize: task.customSize,
      referenceImages: [...task.referenceImages],
      sourceImage: task.sourceImage,
      maskImage: task.maskImage,
    });
    message.success("已发起新的生图任务");
  } catch (err: any) {
    const detail = err.response?.data?.detail || "";
    if (isInsufficientCreditsError(err)) {
      showInsufficientCreditsContact(detail);
      return;
    }
    message.error(formatGenerationErrorMessage(detail, "重新生成失败"));
  }
}

function handlePreview(url: string) {
  previewCurrent.value = url;
  previewVisible.value = true;
}

function openFeedbackDialogForGeneratedTask(task: GeneratedTaskItem) {
  if (!task.taskId) {
    message.warning("当前任务尚未生成完成，暂时无法提交反馈");
    return;
  }
  feedbackTarget.value = {
    taskId: task.taskId,
    model: task.model,
    prompt: task.prompt,
    createdAt: task.createdAt,
  };
  feedbackDialogOpen.value = true;
}

function getResultDisplayUrl(img: ImageResult) {
  return getDisplayImageUrl(img);
}

function getResultPreviewUrl(img: ImageResult) {
  return getPreviewImageUrl(img);
}

function getGeneratedResultDisplayUrl(task: GeneratedTaskItem, img: ImageResult) {
  if (img.status !== "success") return getResultDisplayUrl(img);
  if (isGeneratedTaskExpired(task)) return expiredResultAsset;
  return getResultDisplayUrl(img);
}

function getGeneratedResultPreviewUrl(task: GeneratedTaskItem, img: ImageResult) {
  if (img.status !== "success") return getResultPreviewUrl(img);
  if (isGeneratedTaskExpired(task)) return "";
  return getResultPreviewUrl(img);
}

function canEditGeneratedImage(task: GeneratedTaskItem, img: ImageResult) {
  return img.status === "success" && !isGeneratedTaskExpired(task) && !!(img.image_url || img.preview_url);
}

function handleDownload(imageId: number, imageUrl: string, previewUrl?: string) {
  const a = document.createElement("a");
  a.href = getDownloadUrl(imageId, imageUrl, previewUrl);
  a.download = `banana_${imageId}.png`;
  a.click();
}

async function openHistory() {
  if (!(await ensureAuthenticated())) return;
  historyVisible.value = true;
  historyLoading.value = true;
  try {
    historyItems.value = await getPromptHistory();
  } catch {
    message.error("获取历史提示词失败");
  } finally {
    historyLoading.value = false;
  }
}

async function removeHistoryItem(id: number) {
  try {
    await deletePromptHistory(id);
    historyItems.value = historyItems.value.filter((i) => i.id !== id);
  } catch {
    message.error("删除失败");
  }
}

async function removeGeneratedTask(task: GeneratedTaskItem) {
  if (!task.taskId) {
    generatedTasks.value = generatedTasks.value.filter((item) => item.localId !== task.localId);
    stopAllTaskPolling();
    if (activePollingTaskIds.value.length) startTaskPolling();
    message.success("已移除当前任务卡片");
    return;
  }

  try {
    await deleteHistoryTask(task.taskId);
    generatedTasks.value = generatedTasks.value.filter((item) => item.taskId !== task.taskId);
    stopAllTaskPolling();
    if (activePollingTaskIds.value.length) startTaskPolling();
    await loadRecentGeneratedTasks();
    message.success("删除成功");
  } catch {
    message.error("删除失败");
  }
}

function confirmRemoveGeneratedTask(task: GeneratedTaskItem) {
  const isLocalOnly = !task.taskId;
  const isGenerating = task.status === "submitting" || task.status === "pending" || task.status === "queued" || task.status === "processing";

  Modal.confirm({
    title: isLocalOnly ? "确认移除这张任务卡片？" : "确认删除这个任务？",
    content: isLocalOnly
      ? "这会从当前页面移除该本地任务卡片，不影响服务器中的其他记录。"
      : isGenerating
        ? "删除后会移除该任务及其当前结果，历史记录中的对应任务也会一并删除。"
        : "删除后会移除该任务及其结果图，历史记录中的对应任务也会一并删除。",
    centered: true,
    async onOk() {
      await removeGeneratedTask(task);
    },
  });
}

function useHistoryPrompt(text: string) {
  prompt.value = text;
  generateMode.value = "textGenerate";
  historyVisible.value = false;
}

function historyModeLabel(mode: PromptHistoryItem["mode"]) {
  if (mode === "inpaint") return "局部重绘";
  if (mode === "promptReverse") return "提示词反推";
  return "文生图/图编辑";
}

function applyDraft(raw: string | null, successText: string, storageKey: string) {
  if (!raw) return;
  try {
    const draft = JSON.parse(raw) as {
      mode?: "generate" | "inpaint" | "promptReverse";
      prompt?: string;
      model?: string;
      reference_images?: string[];
      num_images?: number;
      size?: string;
      resolution?: string;
      custom_size?: string;
      source_image?: string;
      mask_image?: string;
    };
    const draftMode: GenerateMode = draft.mode === "inpaint"
      ? "inpaint"
      : draft.mode === "promptReverse"
        ? "promptReverse"
        : Array.isArray(draft.reference_images) && draft.reference_images.length
          ? "imageEdit"
          : "textGenerate";
    generateMode.value = draftMode;
    size.value = draft.size || "9:16";
    resolution.value = draft.resolution || "2K";
    customSize.value = draft.custom_size || "";

    if (draftMode === "inpaint") {
      repaintPrompt.value = draft.prompt || "";
      revokeObjectUrl(sourcePreviewUrl.value);
      sourceImageUrl.value = draft.source_image || "";
      sourcePreviewUrl.value = "";
      repaintMaskUrl.value = draft.mask_image || "";
      hasRepaintMask.value = false;
      canUndoMask.value = false;
      canRedoMask.value = false;
      prompt.value = "";
      syncReferenceItems([]);
      numImages.value = 1;
      reverseImageUrl.value = "";
      reversePromptResult.value = "";
    } else if (draftMode === "promptReverse") {
      reverseImageUrl.value = draft.source_image || "";
      reversePromptResult.value = draft.prompt || "";
      prompt.value = "";
      repaintPrompt.value = "";
      syncReferenceItems([]);
      revokeObjectUrl(sourcePreviewUrl.value);
      sourcePreviewUrl.value = "";
      sourceImageUrl.value = "";
      repaintMaskUrl.value = "";
      hasRepaintMask.value = false;
      canUndoMask.value = false;
      canRedoMask.value = false;
      numImages.value = 1;
    } else {
      prompt.value = draft.prompt || "";
      selectedModel.value = draft.model || selectedModel.value;
      syncReferenceItems(Array.isArray(draft.reference_images) ? draft.reference_images.slice(0, maxReferenceImages.value) : []);
      numImages.value = Math.min(MAX_ACTIVE_GENERATION_IMAGES, Math.max(1, Number(draft.num_images || 1)));
      repaintPrompt.value = "";
      revokeObjectUrl(sourcePreviewUrl.value);
      sourcePreviewUrl.value = "";
      sourceImageUrl.value = "";
      repaintMaskUrl.value = "";
      reverseImageUrl.value = "";
      reversePromptResult.value = "";
      hasRepaintMask.value = false;
      canUndoMask.value = false;
      canRedoMask.value = false;
      repaintCanvasRef.value?.clearMask();
    }
    localStorage.removeItem(storageKey);
    message.success(successText);
  } catch {
    localStorage.removeItem(storageKey);
  }
}

async function loadTaskSceneConfigs() {
  try {
    taskScenes.value = await getTaskScenes();
  } catch {
    // ignore scene config loading failures, backend will still validate on submit
  } finally {
    sceneConfigLoading.value = false;
  }
}

async function notifyCompletedUnreadFeedbacks() {
  if (!auth.isLoggedIn) return;
  try {
    const { count } = await getMyCompletedUnreadFeedbackCount();
    setStoredUserCompletedUnreadFeedbackCount(count);
    if (count > 1) {
      notification.info({
        key: COMPLETED_UNREAD_FEEDBACK_NOTIFICATION_KEY,
        message: "您的反馈有新进展，点击前往查看！",
        placement: "topRight",
        duration: 5,
        style: {
          cursor: "pointer",
          borderRadius: "18px",
          background: "linear-gradient(180deg, rgba(255, 250, 240, 0.98), rgba(255, 245, 225, 0.98))",
          border: "1px solid rgba(240, 210, 150, 0.95)",
          boxShadow: "0 16px 28px rgba(228, 174, 74, 0.18)",
        },
        onClick: () => {
          notification.close(COMPLETED_UNREAD_FEEDBACK_NOTIFICATION_KEY);
          router.push("/feedbacks");
        },
      });
      return;
    }
    notification.close(COMPLETED_UNREAD_FEEDBACK_NOTIFICATION_KEY);
  } catch {
    // ignore unread feedback reminder failures
  }
}

onMounted(async () => {
  syncViewportWidth();
  window.addEventListener("resize", syncViewportWidth);
  await Promise.all([
    loadTaskSceneConfigs(),
    loadRecentGeneratedTasks(),
    notifyCompletedUnreadFeedbacks(),
  ]);
  applyDraft(
    localStorage.getItem(HISTORY_DRAFT_KEY),
    "已回填历史任务参数，可继续编辑后重新生成",
    HISTORY_DRAFT_KEY
  );
  applyDraft(
    localStorage.getItem(TEMPLATE_DRAFT_KEY),
    "已套用创意模版参数，可继续编辑后生成",
    TEMPLATE_DRAFT_KEY
  );
});

onActivated(() => {
  void loadRecentGeneratedTasks();
  void notifyCompletedUnreadFeedbacks();
});

onBeforeUnmount(() => {
  stopAllTaskPolling();
  window.removeEventListener("resize", syncViewportWidth);
  referenceItems.value.forEach((item) => revokeObjectUrl(item.objectUrl));
  revokeObjectUrl(sourcePreviewUrl.value);
});

watch(generationModels, (models) => {
  if (!models.length) {
    selectedModel.value = "";
    return;
  }
  if (!models.some((item) => item.model_key === selectedModel.value)) {
    selectedModel.value = models[0].model_key;
  }
}, { immediate: true });

watch(sizeOptions, (options) => {
  if (hideAspectRatio.value || !options.length) return;
  if (!options.some((item) => item.value === size.value)) {
    size.value = options[0].value;
  }
}, { immediate: true });

watch([resolutionOptions, hideResolution], ([options, shouldHide]) => {
  if (shouldHide || !options.length) return;
  if (!options.some((item) => item.value === resolution.value)) {
    resolution.value = options[0].value;
  }
}, { immediate: true });

watch([customSizeOptions, hideCustomSize], ([options, shouldHide]) => {
  if (shouldHide || !options.length) return;
  if (!options.some((item) => item.value === customSize.value)) {
    customSize.value = options[0].value;
  }
}, { immediate: true });

watch(() => auth.isLoggedIn, (isLoggedIn) => {
  if (isLoggedIn) {
    void loadRecentGeneratedTasks();
    return;
  }
  generatedTasks.value = [];
  stopAllTaskPolling();
});
</script>

<template>
  <div class="generate-page">
    <div class="generate-workbench">
      <div class="left-col">
        <div class="generate-mode-shell">
          <div class="generate-mode-switch">
            <div class="mode-switch-cluster">
              <div class="mode-switch-group mode-switch-group-primary">
                <button
                  type="button"
                  class="mode-switch-btn"
                  :class="{ active: generateMode === 'textGenerate' }"
                  @click="generateMode = 'textGenerate'"
                >
                  <span class="generate-tab-label">
                    <FontSizeOutlined />
                    <span>文生图</span>
                  </span>
                </button>
                <button
                  type="button"
                  class="mode-switch-btn"
                  :class="{ active: generateMode === 'imageEdit' }"
                  @click="generateMode = 'imageEdit'"
                >
                  <span class="generate-tab-label">
                    <PictureOutlined />
                    <span>图编辑</span>
                  </span>
                </button>
              </div>
            </div>

            <div class="mode-switch-cluster">
              <div class="mode-switch-group mode-switch-group-secondary">
                <a-dropdown
                  :trigger="['hover']"
                  placement="bottomRight"
                  overlay-class-name="generate-tool-dropdown"
                >
                  <button
                    type="button"
                    class="mode-switch-btn tool tool-trigger"
                    :class="{ active: isExtendedToolMode }"
                  >
                    <span class="mode-switch-trigger-content">
                      <AppstoreOutlined class="mode-switch-trigger-icon" />
                      <span class="mode-switch-trigger-value">{{ activeExtendedToolLabel }}</span>
                    </span>
                    <DownOutlined class="mode-switch-trigger-arrow" />
                  </button>
                  <template #overlay>
                    <a-menu
                      class="generate-tool-menu"
                      :selected-keys="activeExtendedToolMenuKeys"
                      @click="handleExtendedToolMenuClick"
                    >
                      <a-menu-item key="promptReverse">
                        <span class="generate-tool-menu-item-label">
                          <SearchOutlined />
                          <span>提示词反推</span>
                        </span>
                      </a-menu-item>
                      <a-menu-item key="inpaint">
                        <span class="generate-tool-menu-item-label">
                          <HighlightOutlined />
                          <span>局部重绘</span>
                        </span>
                      </a-menu-item>
                    </a-menu>
                  </template>
                </a-dropdown>
              </div>
            </div>
          </div>

          <transition name="generate-panel-slide" mode="out-in">
            <section
              v-if="generateMode === 'textGenerate'"
              key="textGenerate"
              class="work-panel settings-panel generate-config-panel"
            >
              <div class="settings-scroll">
              <template v-if="sceneConfigLoading">
                <div class="config-skeleton-shell" aria-hidden="true">
                  <div class="config-skeleton-section">
                    <div class="config-skeleton-line config-skeleton-line-title"></div>
                    <div class="config-skeleton-line config-skeleton-line-control"></div>
                  </div>
                  <div class="config-skeleton-section">
                    <div class="config-skeleton-line config-skeleton-line-title"></div>
                    <div class="config-skeleton-line config-skeleton-line-area"></div>
                  </div>
                  <div class="config-skeleton-row">
                    <div class="config-skeleton-chip"></div>
                    <div class="config-skeleton-chip"></div>
                    <div class="config-skeleton-chip"></div>
                  </div>
                  <div class="config-skeleton-section config-skeleton-section-last">
                    <div class="config-skeleton-line config-skeleton-line-title config-skeleton-line-short"></div>
                    <div class="config-skeleton-line config-skeleton-line-slider"></div>
                  </div>
                </div>
              </template>
              <template v-else>
              <div class="settings-row model-row config-section">
                <div class="setting-item setting-item-full">
                  <div class="setting-label-row">
                    <label>选择模型</label>
                    <div class="model-help">
                      <a-popover trigger="hover" placement="bottomRight" overlay-class-name="model-help-popover">
                        <template #content>
                          <div class="model-help-tip">
                            <div class="model-help-grid model-help-grid-head">
                              <div>模型</div>
                              <div>细节与质量</div>
                              <div>伪影</div>
                              <div>推荐使用场景</div>
                            </div>
                            <div class="model-help-grid">
                              <div>Image 2（顶级）</div>
                              <div>最高保真度，锐利边缘、精细纹理、文字表现最佳</div>
                              <div>最少</div>
                              <div>最终成品、完美文字、高清精度需求（印刷、专业输出、复杂构图）</div>
                            </div>
                            <div class="model-help-grid">
                              <div>Image 2（高质量）</div>
                              <div>平衡，细节较好</div>
                              <div>较少</div>
                              <div>大多数日常生产用途（社交媒体、网页素材等）</div>
                            </div>
                            <div class="model-help-grid">
                              <div>Image 2（性价比）</div>
                              <div>较粗糙，细节一般</div>
                              <div>较多</div>
                              <div>快速迭代、草稿、缩略图、高频批量生成、成本敏感场景</div>
                            </div>
                            <div class="model-help-grid">
                              <div>Nano Banana Pro</div>
                              <div>极致细节、复杂构图、干净文字</div>
                              <div>最少</div>
                              <div>需要极致细节、复杂构图、文字排版时使用</div>
                            </div>
                            <div class="model-help-grid">
                              <div>Nano Banana 2</div>
                              <div>接近 Pro，速度与质量平衡最佳</div>
                              <div>较少</div>
                              <div>大多数人日常使用首选（性价比最高）</div>
                            </div>
                            <div class="model-help-grid">
                              <div>Nano Banana</div>
                              <div>一般，适合快速草稿验证</div>
                              <div>较多</div>
                              <div>现在较少使用，主要用于低成本快速测试</div>
                            </div>
                          </div>
                        </template>
                        <button type="button" class="model-help-trigger">
                          <BarChartOutlined />
                          <span>模型对比</span>
                        </button>
                      </a-popover>
                    </div>
                  </div>
                  <a-select
                    v-model:value="selectedModel"
                    :bordered="false"
                    class="flat-select"
                    popup-class-name="generate-dropdown"
                  >
                    <a-select-option v-for="model in generationModels" :key="model.model_key" :value="model.model_key">
                      <div class="model-option">
                        <div class="model-option-label">{{ model.model_label }}</div>
                        <div v-if="model.model_description" class="model-option-desc">{{ model.model_description }}</div>
                      </div>
                    </a-select-option>
                  </a-select>
                </div>
              </div>

              <div class="prompt-block config-section">
                <div class="prompt-label-row">
                  <label>提示词</label>
                  <a-button type="text" class="history-btn" @click="openHistory">
                    <template #icon><ClockCircleOutlined /></template>
                  </a-button>
                </div>
                <a-textarea
                  v-model:value="prompt"
                  :rows="5"
                  placeholder="描述您想要生成的图片..."
                  class="prompt-input"
                  :maxlength="TASK_PROMPT_MAX_LENGTH"
                  show-count
                />
              </div>

              <div class="settings-row settings-row-inline config-section compact-config-section">
                <div v-if="!hideAspectRatio" class="setting-item setting-item-inline">
                  <label>宽高比</label>
                  <a-select
                    v-model:value="size"
                    :bordered="false"
                    class="flat-select"
                    popup-class-name="generate-dropdown"
                    :options="sizeOptions"
                  />
                </div>
                <div v-if="!hideResolution" class="setting-item setting-item-inline">
                  <label>分辨率</label>
                  <a-select
                    v-model:value="resolution"
                    :bordered="false"
                    class="flat-select"
                    popup-class-name="generate-dropdown"
                    :options="resolutionOptions"
                  />
                </div>
                <div v-if="!hideCustomSize" class="setting-item setting-item-inline">
                  <label>分辨率</label>
                  <a-select
                    v-model:value="customSize"
                    :bordered="false"
                    class="flat-select"
                    popup-class-name="generate-dropdown"
                    :options="customSizeOptions"
                  />
                </div>
              </div>

              <div class="generate-actions-block config-section action-config-section">
                <div class="field-block">
                  <label>图片数量：{{ numImages }}</label>
                  <a-slider
                    v-model:value="numImages"
                    :min="1"
                    :max="MAX_ACTIVE_GENERATION_IMAGES"
                    :marks="{ 1: '1', 2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8' }"
                    class="num-slider"
                  />
                </div>
              </div>
              </template>

              </div>

              <div class="settings-footer">
                <div class="generate-link-tip">
                  <div class="generate-link-tip-left">
                    <a
                      href="https://80ai.net/gptimage2-prompt"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="generate-link-tip-anchor"
                    >
                      提示词灵感
                    </a>
                    (400+模版)
                  </div>
                  <div class="generate-link-tip-right">
                    支持 <strong>8</strong> 张图片同时生成（{{ activeGenerationImageCount }} / {{ MAX_ACTIVE_GENERATION_IMAGES }}）
                  </div>
                </div>
                <a-button
                  type="primary"
                  block
                  size="large"
                  :disabled="sceneConfigLoading || !canClickGenerate"
                  class="generate-btn"
                  @click="handleGenerate"
                >
                  <template #icon><ThunderboltOutlined /></template>
                  {{ generateButtonText }}
                </a-button>
              </div>
            </section>

            <section
              v-else-if="generateMode === 'imageEdit'"
              key="imageEdit"
              class="work-panel settings-panel generate-config-panel"
            >
              <div class="settings-scroll">
              <template v-if="sceneConfigLoading">
                <div class="config-skeleton-shell" aria-hidden="true">
                  <div class="config-skeleton-section">
                    <div class="config-skeleton-line config-skeleton-line-title"></div>
                    <div class="config-skeleton-line config-skeleton-line-control"></div>
                  </div>
                  <div class="config-skeleton-section">
                    <div class="config-skeleton-line config-skeleton-line-title"></div>
                    <div class="config-skeleton-line config-skeleton-line-area"></div>
                  </div>
                  <div class="config-skeleton-row">
                    <div class="config-skeleton-chip"></div>
                    <div class="config-skeleton-chip"></div>
                    <div class="config-skeleton-chip"></div>
                  </div>
                  <div class="config-skeleton-section config-skeleton-section-last">
                    <div class="config-skeleton-line config-skeleton-line-title config-skeleton-line-short"></div>
                    <div class="config-skeleton-line config-skeleton-line-slider"></div>
                  </div>
                </div>
              </template>
              <template v-else>
              <div class="settings-row model-row config-section">
                <div class="setting-item setting-item-full">
                  <div class="setting-label-row">
                    <label>选择模型</label>
                    <div class="model-help">
                      <a-popover trigger="hover" placement="bottomRight" overlay-class-name="model-help-popover">
                        <template #content>
                          <div class="model-help-tip">
                            <div class="model-help-grid model-help-grid-head">
                              <div>模型</div>
                              <div>细节与质量</div>
                              <div>伪影</div>
                              <div>推荐使用场景</div>
                            </div>
                            <div class="model-help-grid">
                              <div>Image 2（顶级）</div>
                              <div>最高保真度，锐利边缘、精细纹理、文字表现最佳</div>
                              <div>最少</div>
                              <div>最终成品、完美文字、高清精度需求（印刷、专业输出、复杂构图）</div>
                            </div>
                            <div class="model-help-grid">
                              <div>Image 2（高质量）</div>
                              <div>平衡，细节较好</div>
                              <div>较少</div>
                              <div>大多数日常生产用途（社交媒体、网页素材等）</div>
                            </div>
                            <div class="model-help-grid">
                              <div>Image 2（性价比）</div>
                              <div>较粗糙，细节一般</div>
                              <div>较多</div>
                              <div>快速迭代、草稿、缩略图、高频批量生成、成本敏感场景</div>
                            </div>
                            <div class="model-help-grid">
                              <div>Nano Banana Pro</div>
                              <div>极致细节、复杂构图、干净文字</div>
                              <div>最少</div>
                              <div>需要极致细节、复杂构图、文字排版时使用</div>
                            </div>
                            <div class="model-help-grid">
                              <div>Nano Banana 2</div>
                              <div>接近 Pro，速度与质量平衡最佳</div>
                              <div>较少</div>
                              <div>大多数人日常使用首选（性价比最高）</div>
                            </div>
                            <div class="model-help-grid">
                              <div>Nano Banana</div>
                              <div>一般，适合快速草稿验证</div>
                              <div>较多</div>
                              <div>已较少使用，主要用于低成本快速测试</div>
                            </div>
                          </div>
                        </template>
                        <button type="button" class="model-help-trigger">
                          <BarChartOutlined />
                          <span>模型对比</span>
                        </button>
                      </a-popover>
                    </div>
                  </div>
                  <a-select
                    v-model:value="selectedModel"
                    :bordered="false"
                    class="flat-select"
                    popup-class-name="generate-dropdown"
                  >
                    <a-select-option v-for="model in generationModels" :key="model.model_key" :value="model.model_key">
                      <div class="model-option">
                        <div class="model-option-label">{{ model.model_label }}</div>
                        <div v-if="model.model_description" class="model-option-desc">{{ model.model_description }}</div>
                      </div>
                    </a-select-option>
                  </a-select>
                </div>
              </div>

              <div class="field-block ref-upload-block config-section">
                <div class="panel-head">
                  <h3>参考图</h3>
                  <span class="panel-hint">(最多 {{ maxReferenceImages }} 张)</span>
                </div>

                <input
                  ref="fileInput"
                  type="file"
                  accept="image/*"
                  multiple
                  hidden
                  @change="handleFileChange"
                />

                <div class="upload-grid">
                  <div
                    v-for="(item, idx) in referenceItems"
                    :key="item.id"
                    class="upload-thumb"
                    @click="handlePreview(getReferencePreviewUrl(item))"
                  >
                    <img :src="getReferencePreviewUrl(item)" alt="参考图" />
                    <div v-if="item.status !== 'success'" class="upload-thumb-mask" :class="{ error: item.status === 'failed' }">
                      <a-spin
                        v-if="item.status === 'uploading'"
                        :indicator="h(LoadingOutlined, { style: smallAccentIndicatorStyle })"
                      />
                      <span v-else>上传失败</span>
                    </div>
                    <button
                      type="button"
                      class="thumb-remove"
                      aria-label="删除参考图"
                      @click.stop="removeReference(idx)"
                    >
                      <CloseOutlined />
                    </button>
                  </div>

                  <div
                    v-if="referenceItems.length < maxReferenceImages"
                    class="upload-add"
                    @click="triggerUpload"
                  >
                    <a-spin
                      v-if="uploading"
                      :indicator="h(LoadingOutlined, { style: accentIndicatorStyle })"
                    />
                    <template v-else>
                      <CloudUploadOutlined style="font-size: 22px; color: var(--theme-accent)" />
                      <span>上传</span>
                    </template>
                  </div>
                </div>
              </div>

              <div class="prompt-block config-section">
                <div class="prompt-label-row">
                  <label>提示词</label>
                  <a-button type="text" class="history-btn" @click="openHistory">
                    <template #icon><ClockCircleOutlined /></template>
                  </a-button>
                </div>
                <a-textarea
                  v-model:value="prompt"
                  :rows="5"
                  placeholder="描述您想要生成的图片..."
                  class="prompt-input"
                  :maxlength="TASK_PROMPT_MAX_LENGTH"
                  show-count
                />
              </div>

              <div class="settings-row settings-row-inline config-section compact-config-section">
                <div v-if="!hideAspectRatio" class="setting-item setting-item-inline">
                  <label>宽高比</label>
                  <a-select
                    v-model:value="size"
                    :bordered="false"
                    class="flat-select"
                    popup-class-name="generate-dropdown"
                    :options="sizeOptions"
                  />
                </div>
                <div v-if="!hideResolution" class="setting-item setting-item-inline">
                  <label>分辨率</label>
                  <a-select
                    v-model:value="resolution"
                    :bordered="false"
                    class="flat-select"
                    popup-class-name="generate-dropdown"
                    :options="resolutionOptions"
                  />
                </div>
                <div v-if="!hideCustomSize" class="setting-item setting-item-inline">
                  <label>分辨率</label>
                  <a-select
                    v-model:value="customSize"
                    :bordered="false"
                    class="flat-select"
                    popup-class-name="generate-dropdown"
                    :options="customSizeOptions"
                  />
                </div>
              </div>

              <div class="generate-actions-block config-section action-config-section">
                <div class="field-block">
                  <label>图片数量：{{ numImages }}</label>
                  <a-slider
                    v-model:value="numImages"
                    :min="1"
                    :max="MAX_ACTIVE_GENERATION_IMAGES"
                    :marks="{ 1: '1', 2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8' }"
                    class="num-slider"
                  />
                </div>
              </div>
              </template>

              </div>

              <div class="settings-footer">
                <div class="generate-link-tip">
                  <div class="generate-link-tip-left">
                    <a
                      href="https://80ai.net/gptimage2-prompt"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="generate-link-tip-anchor"
                    >
                      提示词灵感
                    </a>
                    (400+模版)
                  </div>
                  <div class="generate-link-tip-right">
                    支持 <strong>8</strong> 张图片同时生成（{{ activeGenerationImageCount }} / {{ MAX_ACTIVE_GENERATION_IMAGES }}）
                  </div>
                </div>
                <a-button
                  type="primary"
                  block
                  size="large"
                  :disabled="sceneConfigLoading || !canClickGenerate"
                  class="generate-btn"
                  @click="handleGenerate"
                >
                  <template #icon><ThunderboltOutlined /></template>
                  {{ generateButtonText }}
                </a-button>
              </div>
            </section>

            <section
              v-else-if="generateMode === 'promptReverse'"
              key="promptReverse"
              class="work-panel settings-panel prompt-reverse-panel"
            >
              <div class="settings-scroll">
              <div class="field-block">
                <div class="panel-head">
                  <h3>上传图片</h3>
                  <span class="panel-hint">(每次反推消耗 1 积分)</span>
                </div>

                <input
                  ref="reverseInput"
                  type="file"
                  accept="image/*"
                  hidden
                  @change="handleReverseFileChange"
                />

                <div
                  v-if="!reverseImageUrl"
                  class="source-upload-empty"
                  @click="triggerReverseUpload"
                >
                  <a-spin
                    v-if="reverseUploading"
                    :indicator="h(LoadingOutlined, { style: accentIndicatorStyle })"
                  />
                  <template v-else>
                    <CloudUploadOutlined class="source-upload-icon" />
                    <div class="source-upload-title">点击上传图片</div>
                    <div class="source-upload-desc">系统将自动分析图片内容并反推出专业中文提示词</div>
                  </template>
                </div>

                <div v-else class="reverse-preview-shell" @click="handlePreview(reverseImageUrl)">
                  <button type="button" class="canvas-remove-btn" @click.stop="removeReverseImage">
                    <CloseOutlined />
                  </button>
                  <img :src="reverseImageUrl" alt="提示词反推图片" class="reverse-preview-image" />
                </div>
              </div>

              <transition name="generate-panel-slide" mode="out-in">
                <div v-if="reversePromptResult" key="reverse-result" class="reverse-result-card">
                  <div class="panel-head">
                    <h3>反推结果</h3>
                  </div>
                  <a-textarea
                    :value="reversePromptResult"
                    :rows="8"
                    readonly
                    class="prompt-input reverse-result-input"
                  />
                  <div class="reverse-actions">
                    <a-button class="reverse-action-btn reverse-action-btn-secondary" @click="copyReversePrompt">
                      <template #icon><CopyOutlined /></template>
                      复制提示词
                    </a-button>
                    <a-button class="reverse-action-btn reverse-action-btn-primary" type="primary" @click="applyReversePrompt">
                      带入文生图
                    </a-button>
                  </div>
                </div>

                <div v-else key="reverse-placeholder" class="reverse-result-placeholder">
                  上传图片后，点击「开始反推」即可获得适合 AI 绘画的中文提示词。
                </div>
              </transition>
              </div>

              <div class="settings-footer">
                <div class="generate-link-tip">
                  <div class="generate-link-tip-left">
                    <a
                      href="https://80ai.net/gptimage2-prompt"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="generate-link-tip-anchor"
                    >
                      提示词灵感
                    </a>
                    (400+模版)
                  </div>
                </div>
                <a-button
                  type="primary"
                  block
                  size="large"
                  :loading="reverseLoading || reverseUploading"
                  class="generate-btn"
                  @click="handlePromptReverse"
                >
                  <template #icon><ThunderboltOutlined /></template>
                  {{ promptReverseButtonText }}
                </a-button>
              </div>
            </section>

            <section
              v-else
              key="inpaint"
              class="work-panel settings-panel inpaint-panel"
            >
              <div class="settings-scroll">
              <div class="field-block">
                <div class="panel-head">
                  <h3>绘制区域</h3>
                  <span class="panel-hint">(必传，涂抹后仅重绘选区)</span>
                </div>

                <input
                  ref="sourceInput"
                  type="file"
                  accept="image/*"
                  hidden
                  @change="handleSourceFileChange"
                />

                <div
                  v-if="!sourceDisplayUrl"
                  class="source-upload-empty"
                  @click="triggerSourceUpload"
                >
                  <a-spin
                    v-if="sourceUploading"
                    :indicator="h(LoadingOutlined, { style: accentIndicatorStyle })"
                  />
                  <template v-else>
                    <CloudUploadOutlined class="source-upload-icon" />
                    <div class="source-upload-title">点击上传原图</div>
                    <div class="source-upload-desc">上传后可直接在图片上涂抹需要重绘的区域</div>
                  </template>
                </div>

                <template v-else>
                  <div class="repaint-status-card" :class="{ ready: hasRepaintMask }">
                    <div class="repaint-status-title">
                      {{ hasRepaintMask ? "已选择重绘区域" : "请在图片上涂抹需要重绘的区域" }}
                    </div>
                    <div class="repaint-status-desc">
                      {{ hasRepaintMask ? "提交后只会修改已涂抹部分，未涂抹区域保持不变。" : "先上传原图，再直接在图片上绘制需要重绘的局部范围。" }}
                    </div>
                    <div v-if="sourceUploading || (!sourceImageUrl && sourcePreviewUrl)" class="repaint-status-uploading">
                      {{ sourceUploading ? "原图上传中，完成后可提交任务" : "原图上传未完成，请重新上传后再试" }}
                    </div>
                  </div>

                  <div class="repaint-canvas-shell">
                    <button type="button" class="canvas-remove-btn" @click.stop="removeSourceImage">
                      <CloseOutlined />
                    </button>
                    <RepaintCanvas
                      ref="repaintCanvasRef"
                      :image-url="sourceDisplayUrl"
                      :mask-url="resolveImageUrl(repaintMaskUrl)"
                      :brush-size="brushSize"
                      :tool="repaintTool"
                      @mask-change="handleMaskChange"
                    />
                  </div>

                  <div class="repaint-toolbar">
                    <button
                      type="button"
                      class="tool-btn"
                      :class="{ active: repaintTool === 'paint' }"
                      @click="repaintTool = 'paint'"
                    >
                      <EditOutlined />
                    </button>
                    <button
                      type="button"
                      class="tool-btn"
                      :class="{ active: repaintTool === 'erase' }"
                      @click="repaintTool = 'erase'"
                    >
                      <ClearOutlined />
                    </button>
                    <div class="toolbar-divider" />
                    <div class="toolbar-slider">
                      <a-slider v-model:value="brushSize" :min="12" :max="60" class="brush-slider" />
                    </div>
                    <div class="brush-preview" :style="{ width: `${Math.max(10, Math.min(brushSize, 34))}px`, height: `${Math.max(10, Math.min(brushSize, 34))}px` }" />
                    <div class="toolbar-divider" />
                    <button
                      type="button"
                      class="tool-btn"
                      @click="clearRepaintMask"
                    >
                      <ReloadOutlined />
                    </button>
                    <button
                      type="button"
                      class="tool-btn"
                      :disabled="!canUndoMask"
                      @click="undoRepaintMask"
                    >
                      <UndoOutlined />
                    </button>
                    <button
                      type="button"
                      class="tool-btn"
                      :disabled="!canRedoMask"
                      @click="redoRepaintMask"
                    >
                      <RedoOutlined />
                    </button>
                  </div>

                  <div class="mask-tip">
                    请直接在图片上涂抹需要重绘的区域，当前蒙层为 50% 透明度，提交时仅对白色蒙版区域进行重绘。
                  </div>
                </template>
              </div>

              <div class="prompt-block inpaint-prompt-block">
                <div class="prompt-label-row">
                  <label>提示词</label>
                </div>
                <a-textarea
                  v-model:value="repaintPrompt"
                  :rows="5"
                  placeholder="描述需要局部重绘后的效果..."
                  class="prompt-input"
                  :maxlength="TASK_PROMPT_MAX_LENGTH"
                  show-count
                />
              </div>
              </div>

              <div class="settings-footer">
                <a-button
                  type="primary"
                  block
                  size="large"
                  :loading="sourceUploading"
                  :disabled="!canClickGenerate"
                  class="generate-btn"
                  @click="handleGenerate"
                >
                  <template #icon><ThunderboltOutlined /></template>
                  {{ generateButtonText }}
                </a-button>
              </div>
            </section>
          </transition>
        </div>
      </div>

      <section class="work-panel result-panel">
        <div class="result-head">
          <div class="result-head-main">
            <div class="panel-head result-panel-head">
              <h3>生成任务</h3>
            </div>
            <div class="result-tips">
              <div class="result-tip-line">
                每日前 10 次失败任务不扣积分，所有任务可在
                <router-link to="/history" class="result-tip-link">历史图片</router-link>
                中查看
              </div>
            </div>
          </div>
          <div class="result-retain-badge">
            <ExclamationCircleFilled class="result-retain-icon" />
            <span>服务器只保留原图15天</span>
          </div>
        </div>

        <div class="result-body">
          <template v-if="resultItems.length">
            <div class="result-list">
              <TransitionGroup
                v-for="(column, columnIndex) in resultColumns"
                :key="`result-column-${columnIndex}`"
                name="generate-result"
                tag="div"
                class="result-column"
              >
                <div
                  v-for="(item, index) in column"
                  :key="`${item.taskLocalId}-${item.image.id}-${item.index}`"
                  class="result-card"
                  :style="{
                    '--generate-result-delay': `${Math.min(columnIndex + index, 9) * 45}ms`,
                    '--result-aspect-ratio': getTaskAspectRatio(item.task),
                    '--result-pending-bg-image': `url('${generateEmptyStateAsset}')`,
                  }"
                  :class="{ pending: item.image.status === 'pending' }"
                >
                  <div
                    v-if="item.taskId || item.image.status !== 'pending'"
                    class="result-top-actions"
                  >
                    <a-tooltip v-if="item.taskId" title="反馈">
                      <button
                        type="button"
                        class="result-more-trigger icon-chip"
                        :class="{ 'result-more-trigger-failed': isGeneratedResultFailed(item.task, item.image) }"
                        @click.stop="openFeedbackDialogForGeneratedTask(item.task)"
                      >
                        <MessageOutlined class="result-more-icon" />
                      </button>
                    </a-tooltip>
                    <a-tooltip v-if="canRemoveGeneratedResult(item.task, item.image)" title="删除">
                      <a-button
                        shape="circle"
                        class="icon-chip result-delete-trigger"
                        danger
                        @click.stop="confirmRemoveGeneratedTask(item.task)"
                      >
                        <template #icon><DeleteOutlined /></template>
                      </a-button>
                    </a-tooltip>
                  </div>
                  <div
                    class="result-frame"
                    :class="{
                      pending: item.image.status === 'pending',
                      failed: isGeneratedResultFailed(item.task, item.image),
                      clickable: !!getGeneratedResultPreviewUrl(item.task, item.image),
                    }"
                    @click="getGeneratedResultPreviewUrl(item.task, item.image) && handlePreview(getGeneratedResultPreviewUrl(item.task, item.image))"
                  >
                    <template v-if="item.image.status === 'success' && getGeneratedResultDisplayUrl(item.task, item.image)">
                      <img :src="getGeneratedResultDisplayUrl(item.task, item.image)" alt="生成结果" loading="lazy" />
                      <div class="result-actions">
                        <a-tooltip v-if="getGeneratedResultPreviewUrl(item.task, item.image)" title="查看原图">
                          <a-button shape="circle" class="icon-chip" @click.stop="handlePreview(getGeneratedResultPreviewUrl(item.task, item.image))">
                            <template #icon><EyeOutlined /></template>
                          </a-button>
                        </a-tooltip>
                        <a-tooltip v-if="canEditGeneratedImage(item.task, item.image)" title="结果图编辑">
                          <a-button shape="circle" class="icon-chip" @click.stop="handleEditImageTask(item.task, item.image)">
                            <template #icon><EditOutlined /></template>
                          </a-button>
                        </a-tooltip>
                        <a-tooltip title="重新生成">
                          <a-button
                            shape="circle"
                            class="icon-chip"
                            :disabled="!item.taskId"
                            @click.stop="handleReeditTask(item.task)"
                          >
                            <template #icon><ReloadOutlined /></template>
                          </a-button>
                        </a-tooltip>
                        <a-tooltip title="下载原图">
                          <a-button
                            shape="circle"
                            class="icon-chip"
                            :disabled="isGeneratedTaskExpired(item.task)"
                            @click.stop="handleDownload(item.image.id, item.image.image_url, item.image.preview_url)"
                          >
                            <template #icon><DownloadOutlined /></template>
                          </a-button>
                        </a-tooltip>
                      </div>
                    </template>

                    <template v-else-if="isGeneratedResultFailed(item.task, item.image)">
                      <img :src="failedResultAsset" alt="生成失败" class="failed-image" />
                      <div class="frame-state error">
                        <span>{{ getGeneratedTaskFailureMessage(item.task, item.image) }}</span>
                      <a-button shape="circle" class="icon-chip" @click.stop="handleReeditTask(item.task)">
                        <template #icon><EditOutlined /></template>
                      </a-button>
                      </div>
                    </template>

                    <template v-else>
                      <div class="frame-state">
                        <a-spin
                          :indicator="h(LoadingOutlined, { style: neutralIndicatorStyle })"
                        />
                        <span>正在生成图片...</span>
                        <span class="frame-state-subtext">预计 30 秒 ～ 2 分钟</span>
                      </div>
                      <div class="result-actions result-actions-pending">
                        <a-tooltip title="重新生成">
                          <a-button shape="circle" class="icon-chip" @click.stop="handleReeditTask(item.task)">
                            <template #icon><ReloadOutlined /></template>
                          </a-button>
                        </a-tooltip>
                      </div>
                    </template>
                  </div>
                </div>
              </TransitionGroup>
            </div>

            <div class="result-list-footnote">
              当前仅展示最近 20 个生图任务。若需查看更早记录、完整参数或全部结果，请前往
              <router-link to="/history" class="result-tip-link">历史图片</router-link>
              查看。
            </div>
          </template>

          <div v-else class="result-empty">
            <transition name="generate-panel-slide" mode="out-in">
              <div :key="generateMode" class="result-empty-copy">
                <div class="empty-illustration-shell">
                  <img
                    :src="generateEmptyStateAsset"
                    alt="生成结果占位插画"
                    class="empty-illustration"
                  />
                </div>
                <div class="empty-title">{{ resultEmptyTitle }}</div>
                <div class="empty-desc">{{ resultEmptyDesc }}</div>
              </div>
            </transition>
          </div>
        </div>
      </section>
    </div>

    <!-- Prompt history dialog -->
    <a-modal
      v-model:open="historyVisible"
      title="历史提示词"
      :footer="null"
      :width="560"
      centered
    >
      <a-spin :spinning="historyLoading">
        <div v-if="historyItems.length === 0 && !historyLoading" class="history-empty">
          暂无历史提示词
        </div>
        <TransitionGroup v-else name="history-item" tag="div" class="history-list">
          <div
            v-for="(item, index) in historyItems"
            :key="item.id"
            class="history-item"
            :style="{ '--history-item-delay': `${Math.min(index, 9) * 35}ms` }"
            @click="useHistoryPrompt(item.prompt)"
          >
            <div v-if="item.source_image" class="history-thumb">
              <img :src="resolveImageUrl(item.source_image)" alt="历史图片" />
            </div>
            <div class="history-content">
              <div class="history-meta">
                <span class="history-tag">{{ historyModeLabel(item.mode) }}</span>
              </div>
              <div class="history-text">{{ item.prompt }}</div>
            </div>
            <a-button
              type="text"
              shape="circle"
              size="small"
              class="history-del"
              @click.stop="removeHistoryItem(item.id)"
            >
              <template #icon><DeleteOutlined /></template>
            </a-button>
          </div>
        </TransitionGroup>
      </a-spin>
    </a-modal>

    <div v-if="previewVisible" style="display: none">
      <a-image
        :src="previewCurrent"
        :preview="{
          visible: previewVisible,
          onVisibleChange: (v: boolean) => (previewVisible = v),
        }"
      />
    </div>
    <FeedbackDialog
      v-model:open="feedbackDialogOpen"
      :task-id="feedbackTarget?.taskId"
      :model="feedbackTarget?.model"
      :prompt="feedbackTarget?.prompt"
      :created-at="feedbackTarget?.createdAt"
    />
  </div>
</template>

<style scoped lang="scss">
.generate-page {
  min-height: calc(100vh - 112px);
  height: calc(100vh - 112px);
  --config-title-size: 14px;
  --config-title-gap: 8px;
  --config-title-color: #5e4524;
  --config-section-gap: 17px;
  animation: generate-page-enter var(--motion-duration-reveal-soft) ease both;
}

@keyframes generate-page-enter {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes generate-fade-up {
  from {
    opacity: 0;
    transform: translate3d(0, 16px, 0);
  }
  to {
    opacity: 1;
    transform: translate3d(0, 0, 0);
  }
}

@keyframes generate-panel-in {
  from {
    opacity: 0;
    transform: translate3d(0, 18px, 0) scale(0.99);
  }
  to {
    opacity: 1;
    transform: translate3d(0, 0, 0) scale(1);
  }
}

@keyframes generate-empty-float {
  0% {
    transform: translate3d(0, 0, 0);
  }
  50% {
    transform: translate3d(0, -12px, 0);
  }
  100% {
    transform: translate3d(0, 0, 0);
  }
}

@keyframes generate-slide-left-in {
  from {
    opacity: 0;
    transform: translate3d(-28px, 0, 0);
  }
  to {
    opacity: 1;
    transform: translate3d(0, 0, 0);
  }
}

@keyframes generate-slide-right-in {
  from {
    opacity: 0;
    transform: translate3d(28px, 0, 0);
  }
  to {
    opacity: 1;
    transform: translate3d(0, 0, 0);
  }
}

.generate-workbench {
  display: grid;
  grid-template-columns: 382fr 618fr;
  gap: 20px;
  align-items: stretch;
  min-height: 100%;
  height: 100%;
  animation: generate-fade-up var(--motion-duration-reveal) var(--motion-ease-enter) 0.04s both;
}

.left-col {
  display: flex;
  flex-direction: column;
  min-height: 0;
  animation: generate-slide-left-in var(--motion-duration-stage) var(--motion-ease-enter) 0.08s both;
}

.generate-mode-shell {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
}

.generate-mode-switch {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 14px;
}

.mode-switch-cluster {
  min-width: 0;
  display: flex;
  align-items: center;
}

.mode-switch-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.mode-switch-group-primary {
  gap: 12px;
}

.mode-switch-group-secondary {
  gap: 8px;
  justify-content: flex-end;
}

.mode-switch-btn {
  appearance: none;
  border: 1px solid transparent;
  background: transparent;
  color: #8f7558;
  padding: 0;
  border-radius: 16px;
  cursor: pointer;
  transition:
    color var(--motion-duration-fast) var(--motion-ease-soft),
    transform var(--motion-duration-press) var(--motion-ease-soft),
    box-shadow var(--motion-duration-fast) var(--motion-ease-soft),
    background var(--motion-duration-fast) var(--motion-ease-soft),
    border-color var(--motion-duration-fast) var(--motion-ease-soft);

  &:hover {
    color: #b77a17;
    transform: translateY(-1px);
  }

  &:active {
    transform: scale(0.97);
  }
}

.mode-switch-btn.active {
  color: var(--theme-accent-text);
}

.mode-switch-group-primary .mode-switch-btn {
  height: 42px;
  min-width: 116px;
  border-radius: 14px;
  border-color: var(--theme-control-border-strong);
  background: rgba(var(--theme-surface-strong-rgb), 0.92);
  box-shadow: none;

  &:hover,
  &:focus {
    color: var(--theme-accent-text-hover);
    border-color: var(--theme-border-strong);
    background: rgba(var(--theme-page-base-rgb), 0.96);
    box-shadow: 0 10px 20px var(--theme-shadow-soft);
  }
}

.mode-switch-group-primary .mode-switch-btn.active,
.mode-switch-group-primary .mode-switch-btn.active:hover,
.mode-switch-group-primary .mode-switch-btn.active:focus {
  color: var(--theme-accent-contrast);
  border-color: transparent;
  background: var(--theme-accent);
  box-shadow: 0 14px 24px var(--theme-shadow-strong);
}

.mode-switch-btn.tool {
  min-width: 152px;
  border-width: 1px;
  border-style: solid;
  border-color: var(--theme-control-border-strong);
  background: rgba(var(--theme-surface-strong-rgb), 0.74);
  box-shadow: none;

  &:hover,
  &:focus {
    border-color: var(--theme-border-strong);
    background: rgba(var(--theme-surface-strong-rgb), 0.9);
    box-shadow: 0 10px 20px var(--theme-shadow-soft);
  }
}

.mode-switch-btn.tool.active {
  border-color: var(--theme-panel-border-strong);
  background: linear-gradient(180deg, rgba(var(--theme-surface-strong-rgb), 0.94), rgba(var(--theme-page-base-rgb), 0.9));
  box-shadow: 0 6px 14px var(--theme-shadow-soft);
}

.generate-tab-label {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  line-height: 1;
  min-height: 42px;
  padding: 0 14px;
  white-space: nowrap;

  .anticon {
    font-size: 16px;
    opacity: 0.88;
  }
}

.mode-switch-group-primary .generate-tab-label {
  min-height: 40px;
  padding: 0 18px;
  border-radius: 14px;
  font-weight: 700;

  .anticon {
    font-size: 17px;
  }
}

.tool-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  height: 42px;
  min-height: 42px;
  padding: 0 12px;
  border-radius: 13px;
}

.mode-switch-trigger-content {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.mode-switch-trigger-icon {
  flex: 0 0 auto;
  font-size: 14px;
  opacity: 0.8;
}

.mode-switch-trigger-value {
  color: inherit;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.1;
  white-space: nowrap;
}

.mode-switch-trigger-arrow {
  color: inherit;
  font-size: 11px;
  opacity: 0.58;
}

.generate-tool-menu-item-label {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
}

/* --- Prompt (standalone) --- */
.settings-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.generate-config-panel {
  padding: 16px;
  border-radius: 24px;
  border-color: var(--theme-panel-border);
  box-shadow:
    0 18px 36px var(--theme-shadow-soft),
    inset 0 1px 0 var(--theme-panel-inset);
}

.generate-config-panel > * + * {
  margin-top: var(--config-section-gap);
}

.settings-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0 10px 0 4px;
}

.settings-footer {
  position: relative;
  z-index: 3;
  flex-shrink: 0;
  margin-top: auto;
  padding-top: 8px;
  background: linear-gradient(
    180deg,
    rgba(var(--theme-surface-strong-rgb), 0),
    rgba(var(--theme-surface-strong-rgb), 0.94) 28%,
    var(--theme-surface-strong)
  );
}

.generate-link-tip {
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  text-align: left;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
}

.generate-link-tip-left,
.generate-link-tip-right {
  min-width: 0;
}

.generate-link-tip-right {
  flex-shrink: 0;
  text-align: right;
}

.generate-link-tip-anchor {
  color: var(--theme-accent-text);
  font-weight: 600;
  text-decoration: none;
}

.generate-link-tip-anchor:hover,
.generate-link-tip-anchor:focus {
  color: var(--theme-accent-text-hover);
  text-decoration: underline;
}

.config-section {
  position: relative;
  padding: 0 0 10px;
  transition: transform var(--motion-duration-base) var(--motion-ease-soft), opacity var(--motion-duration-base) var(--motion-ease-soft);
}

.compact-config-section {
  padding-top: 0;
  padding-bottom: 10px;
}

.action-config-section {
  padding-bottom: 0;
}

.prompt-block {
  display: flex;
  flex-direction: column;
}

.prompt-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--config-title-gap);

  label {
    color: var(--config-title-color);
    font-size: 15px;
    font-weight: 700;
    line-height: 1.4;
    letter-spacing: 0.01em;
  }
}

.history-btn {
  width: 32px;
  height: 32px;
  border-radius: 12px;
  color: #a88962 !important;
  font-size: 15px;
  background: rgba(255, 250, 242, 0.92) !important;
  border: 1px solid rgba(241, 221, 183, 0.95) !important;
  transition:
    transform var(--motion-duration-press) var(--motion-ease-soft),
    background var(--motion-duration-fast) var(--motion-ease-soft),
    border-color var(--motion-duration-fast) var(--motion-ease-soft),
    color var(--motion-duration-fast) var(--motion-ease-soft),
    box-shadow var(--motion-duration-fast) var(--motion-ease-soft);

  &:hover {
    color: #d38a12 !important;
    background: rgba(255, 238, 205, 0.92) !important;
    border-color: #efc784 !important;
    transform: translateY(-1px);
    box-shadow: 0 10px 20px var(--theme-shadow-soft);
  }

  &:active {
    transform: scale(0.94);
  }
}

.generate-config-panel .prompt-input {
  border: none !important;
  background: transparent !important;
  padding: 0 !important;
  font-size: 14px;
  resize: none;
  box-shadow: none !important;

  &:focus {
    box-shadow: none !important;
  }

  :deep(textarea) {
    min-height: 144px;
    line-height: 1.7;
    color: var(--theme-title);
    border-radius: 14px !important;
    border-color: var(--theme-control-border) !important;
    background: var(--theme-control-bg) !important;
    padding: 12px 15px !important;
    box-shadow: inset 0 1px 0 var(--theme-panel-inset);
  }

  :deep(textarea:hover),
  :deep(textarea:focus) {
    border-color: var(--theme-border-accent) !important;
    box-shadow: 0 0 0 3px var(--theme-focus-ring);
  }

  :deep(.ant-input-data-count) {
    color: var(--text-muted);
    font-size: 12px;
  }

  :deep(textarea::placeholder) {
    color: var(--text-muted);
  }
}

/* --- Settings row --- */
.settings-row {
  display: flex;
  gap: 16px;
}

.settings-row-inline {
  align-items: center;
}

.setting-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--config-title-gap);

  label {
    color: var(--config-title-color);
    font-size: 15px;
    font-weight: 700;
    line-height: 1.4;
  }
}

.setting-item-full {
  flex: 1 1 100%;
}

.setting-item-inline {
  flex-direction: row;
  align-items: center;
  gap: 8px;

  label {
    margin: 0;
    min-width: 62px;
    flex: 0 0 auto;
  }

  .flat-select {
    flex: 1;
  }
}

.generate-actions-block {
  display: flex;
  flex-direction: column;
}

.config-skeleton-shell {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-right: 6px;
}

.config-skeleton-section,
.config-skeleton-row {
  padding: 16px;
  border-radius: 20px;
  background: rgba(var(--theme-surface-strong-rgb), 0.96);
  border: 1px solid var(--theme-panel-border);
}

.config-skeleton-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.config-skeleton-section-last {
  padding-bottom: 20px;
}

.config-skeleton-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.config-skeleton-line,
.config-skeleton-chip {
  position: relative;
  overflow: hidden;
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    rgba(var(--theme-page-base-rgb), 0.82),
    rgba(var(--theme-surface-strong-rgb), 0.98),
    rgba(var(--theme-page-base-rgb), 0.82)
  );
  background-size: 200% 100%;
  animation: config-skeleton-shimmer 1.4s ease-in-out infinite;
}

.config-skeleton-line-title {
  width: 72px;
  height: 14px;
}

.config-skeleton-line-short {
  width: 92px;
}

.config-skeleton-line-control {
  width: 100%;
  height: 52px;
}

.config-skeleton-line-area {
  width: 100%;
  height: 144px;
  border-radius: 18px;
}

.config-skeleton-chip {
  height: 52px;
}

.config-skeleton-line-slider {
  width: 100%;
  height: 56px;
  border-radius: 18px;
}

@keyframes config-skeleton-shimmer {
  0% {
    background-position: 100% 0;
  }

  100% {
    background-position: -100% 0;
  }
}

/* --- Card panel --- */
.work-panel {
  background: var(--theme-modal-bg);
  border: 1px solid var(--theme-panel-border);
  border-radius: 24px;
  box-shadow: 0 18px 45px var(--theme-shadow-soft);
  padding: 20px;
}

.panel-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: var(--config-title-gap);

  h3 {
    font-size: 14px;
    line-height: 1.35;
    color: var(--config-title-color);
    margin: 0;
    font-weight: 700;
  }
}

.panel-hint {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
  line-height: 1.5;
}

/* --- Upload (compact) --- */
.generate-config-panel .upload-grid {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.generate-config-panel .upload-thumb {
  position: relative;
  width: 72px;
  height: 72px;
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid var(--theme-panel-border);
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-soft));
  flex-shrink: 0;
  cursor: zoom-in;
  box-shadow: 0 8px 18px var(--theme-shadow-soft);
  transition:
    transform var(--motion-duration-swift) var(--motion-ease-soft),
    box-shadow var(--motion-duration-swift) var(--motion-ease-soft),
    border-color var(--motion-duration-swift) var(--motion-ease-soft);

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    transition: transform var(--motion-duration-hover) var(--motion-ease-enter);
  }

  &:hover {
    transform: translateY(-2px);
    border-color: var(--theme-border-strong);
    box-shadow: 0 14px 24px var(--theme-shadow-medium);
  }

  &:hover img {
    transform: scale(1.04);
  }
}

.generate-config-panel .upload-thumb-mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  background: rgba(var(--theme-surface-strong-rgb), 0.72);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  text-align: center;

  &.error {
    background: rgba(255, 245, 243, 0.9);
    color: #d6574b;
  }
}

.thumb-remove {
  position: absolute;
  top: 6px;
  right: 6px;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.82);
  color: #fff;
  font-size: 11px;
  line-height: 1;
  opacity: 0;
  cursor: pointer;
  transform: scale(0.92);
  transition:
    opacity var(--motion-duration-fast) var(--motion-ease-soft),
    transform var(--motion-duration-fast) var(--motion-ease-soft),
    background var(--motion-duration-fast) var(--motion-ease-soft);
}

.generate-config-panel .upload-thumb:hover .thumb-remove,
.generate-config-panel .upload-thumb:focus-within .thumb-remove {
  opacity: 1;
  transform: scale(1);
}

.thumb-remove:hover,
.thumb-remove:focus-visible {
  background: rgba(0, 0, 0, 0.92);
}

.generate-config-panel .upload-add {
  width: 72px;
  height: 72px;
  border-radius: 16px;
  border: 1px dashed var(--theme-panel-border-strong);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  background: linear-gradient(
    180deg,
    rgba(var(--theme-surface-strong-rgb), 0.96),
    rgba(var(--theme-page-base-rgb), 0.92)
  );
  box-shadow:
    inset 0 1px 0 var(--theme-panel-inset),
    0 10px 22px var(--theme-shadow-soft);
  transition:
    border-color var(--motion-duration-fast) var(--motion-ease-soft),
    transform var(--motion-duration-fast) var(--motion-ease-soft),
    box-shadow var(--motion-duration-fast) var(--motion-ease-soft);
  flex-shrink: 0;

  &:hover {
    border-color: var(--theme-border-strong);
    transform: translateY(-2px);
    box-shadow:
      inset 0 1px 0 var(--theme-panel-inset),
      0 14px 24px var(--theme-shadow-medium);
  }

  &:active {
    transform: scale(0.96);
  }
}

/* --- Fields --- */
.field-block + .field-block {
  margin-top: 12px;
}

.field-block label {
  display: block;
  margin-bottom: var(--config-title-gap);
  color: var(--config-title-color);
  font-size: 15px;
  font-weight: 700;
  line-height: 1.4;
}

.setting-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: var(--config-title-gap);
}

.setting-label-row label {
  margin-bottom: 0;
}

.model-help {
  display: inline-flex;
  align-items: center;
  flex: 0 0 auto;
}

.model-help-trigger {
  appearance: none;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: none;
  padding: 0;
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  line-height: 1.4;
  cursor: help;
  transition: color var(--motion-duration-fast) var(--motion-ease-soft);
}

.model-help:hover .model-help-trigger {
  color: var(--theme-accent-text-hover);
}

.model-help-grid {
  display: grid;
  grid-template-columns: 1.12fr 12px 1.2fr 20px 0.72fr 6px 1.8fr;
  gap: 0;
  padding: 12px 0;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  font-size: 13px;
  line-height: 1.55;
}

.model-help-grid > div:nth-child(2) {
  grid-column: 3;
}

.model-help-grid > div:nth-child(3) {
  grid-column: 5;
}

.model-help-grid > div:nth-child(4) {
  grid-column: 7;
}

.model-help-grid:first-child {
  border-top: none;
  padding-top: 0;
}

.model-help-grid:last-child {
  padding-bottom: 0;
}

.model-help-grid-head {
  color: #ffffff;
  font-size: 13px;
  font-weight: 800;
  line-height: 1.35;
}

.generate-config-panel .flat-select {
  width: 100%;
  background: linear-gradient(180deg, var(--theme-control-bg), var(--theme-panel-bg-soft));
  border-radius: 16px;
  border: 1px solid var(--theme-control-border);
  box-shadow:
    inset 0 1px 0 var(--theme-panel-inset),
    0 10px 22px var(--theme-shadow-soft);
  transition: border-color var(--motion-duration-fast) var(--motion-ease-soft), box-shadow var(--motion-duration-fast) var(--motion-ease-soft), transform var(--motion-duration-fast) var(--motion-ease-soft);

  &:hover {
    border-color: var(--theme-border-strong);
    transform: translateY(-1px);
    box-shadow:
      inset 0 1px 0 var(--theme-panel-inset),
      0 12px 22px var(--theme-shadow-medium);
  }

  &:focus-within {
    border-color: var(--theme-border-accent);
    box-shadow:
      inset 0 1px 0 var(--theme-panel-inset),
      0 0 0 3px var(--theme-focus-ring),
      0 12px 22px var(--theme-shadow-medium);
  }

  :deep(.ant-select-selector) {
    height: 48px !important;
    padding: 0 15px !important;
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
    border-radius: 16px !important;
    font-weight: 600;
    color: var(--theme-title);
  }

  :deep(.ant-select-selection-item) {
    line-height: 48px !important;
  }

  :deep(.ant-select-arrow) {
    color: var(--text-muted);
  }

  :deep(.ant-select-selection-placeholder) {
    color: var(--text-muted);
  }
}

.model-option {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.model-option-label {
  font-weight: 700;
  color: var(--theme-title);
}

.model-option-desc {
  font-size: 12px;
  color: var(--text-secondary);
}

/* --- Slider --- */
.num-slider {
  margin: 4px 8px 2px;

  :deep(.ant-slider-rail) {
    background: linear-gradient(90deg, var(--theme-control-border), var(--theme-control-border-strong));
    height: 8px;
    border-radius: 999px;
  }

  :deep(.ant-slider-track) {
    background: var(--theme-accent);
    height: 8px;
    border-radius: 999px;
  }

  :deep(.ant-slider-handle) {
    width: 22px;
    height: 22px;
    margin-top: -6px;
    border: none;
    background: transparent;
    box-shadow: none;
    outline: none !important;
    transform: translateX(-50%);

    &::after {
      width: 22px;
      height: 22px;
      inset-inline-start: 0;
      inset-block-start: 0;
      border-radius: 50%;
      border: 3px solid var(--theme-accent);
      background: var(--theme-panel-bg);
      box-shadow: 0 4px 12px var(--theme-shadow-medium);
    }

    &:hover::after,
    &:focus::after {
      border-color: var(--theme-accent-strong);
      box-shadow: 0 4px 16px var(--theme-shadow-strong);
    }
  }

  :deep(.ant-slider-dot) {
    width: 10px;
    height: 10px;
    border: 2px solid var(--theme-control-border-strong);
    background: var(--theme-control-bg);
    top: -1px;
    transform: translateX(-50%);
  }

  :deep(.ant-slider-dot-active) {
    border-color: var(--theme-accent);
  }

  :deep(.ant-slider-mark-text) {
    color: var(--text-secondary);
    font-size: 12px;
    font-weight: 600;
    margin-top: 5px;
  }

  :deep(.ant-slider-mark-text-active) {
    color: var(--theme-title);
  }
}

.generate-btn {
  margin-top: 10px;
  height: 48px;
  border-radius: 16px;
  font-size: 15px;
  font-weight: 700;
  background: var(--theme-accent) !important;
  border: none !important;
  box-shadow: 0 18px 32px var(--theme-shadow-strong) !important;

  &:hover,
  &:focus {
    background: var(--primary-dark) !important;
    box-shadow: 0 20px 34px var(--theme-shadow-strong) !important;
    transform: translateY(-2px);
  }

  &:disabled {
    background: var(--theme-control-hover-bg) !important;
    color: var(--text-muted) !important;
    box-shadow: none !important;
  }

  &:active {
    transform: scale(0.97);
  }
}

.source-upload-empty {
  min-height: 280px;
  padding: 26px 20px;
  border-radius: 20px;
  border: 2px dashed var(--theme-panel-border-strong);
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-soft));
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  cursor: pointer;
  transition: border-color var(--motion-duration-fast) var(--motion-ease-soft), transform var(--motion-duration-fast) var(--motion-ease-soft), box-shadow var(--motion-duration-base) var(--motion-ease-soft);

  &:hover {
    border-color: var(--theme-border-strong);
    transform: translateY(-2px);
    box-shadow: 0 16px 28px var(--theme-shadow-soft);
  }

  &:active {
    transform: scale(0.99);
  }
}

.source-upload-icon {
  font-size: 30px;
  color: var(--theme-accent);
}

.source-upload-title {
  margin-top: 12px;
  font-size: 16px;
  font-weight: 700;
  color: var(--theme-title);
}

.source-upload-desc {
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.reverse-preview-shell {
  position: relative;
  border-radius: 20px;
  overflow: hidden;
  border: 1px solid var(--theme-panel-border);
  background: var(--theme-panel-bg-soft);
  cursor: zoom-in;
  transition: transform var(--motion-duration-base) var(--motion-ease-soft), box-shadow var(--motion-duration-base) var(--motion-ease-soft);
}

.reverse-preview-image {
  width: 100%;
  display: block;
  max-height: 420px;
  object-fit: contain;
  transition: transform var(--motion-duration-hover) var(--motion-ease-enter);
}

.reverse-preview-shell:hover {
  transform: translateY(-2px);
  box-shadow: 0 18px 30px var(--theme-shadow-soft);
}

.reverse-preview-shell:hover .reverse-preview-image {
  transform: scale(1.01);
}

.reverse-result-card {
  margin-top: 2px;
  padding: 16px;
  border-radius: 20px;
  border: 1px solid var(--theme-panel-border);
  background: var(--theme-panel-bg);
}

.reverse-result-input {
  :deep(textarea) {
    min-height: 180px;
    font-family: "SF Mono", "Consolas", "Monaco", monospace;
    line-height: 1.7;
  }
}

.reverse-actions {
  display: flex;
  gap: 10px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.reverse-action-btn {
  height: 42px;
  border-radius: 14px;
  font-weight: 700;
  border: none !important;
  box-shadow: none !important;

  &:hover,
  &:focus {
    transform: translateY(-2px);
  }

  &:active {
    transform: scale(0.97);
  }
}

.reverse-action-btn-secondary {
  color: var(--theme-accent-text) !important;
  background: var(--theme-panel-bg-strong) !important;
  border: 1px solid var(--theme-panel-border-strong) !important;

  &:hover,
  &:focus {
    color: var(--theme-accent-text-hover) !important;
    background: var(--theme-control-hover-bg) !important;
    border-color: var(--theme-border-strong) !important;
  }
}

.reverse-action-btn-primary {
  background: var(--theme-accent) !important;
  border: none !important;
  box-shadow: 0 14px 24px var(--theme-shadow-strong) !important;

  &:hover,
  &:focus {
    background: var(--primary-dark) !important;
    box-shadow: 0 16px 28px var(--theme-shadow-strong) !important;
  }
}

.reverse-result-placeholder {
  padding: 22px 18px;
  border-radius: 18px;
  border: 1px dashed var(--theme-panel-border-strong);
  background: rgba(var(--theme-page-base-rgb), 0.48);
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.8;
}

.repaint-status-card {
  margin-bottom: 14px;
  padding: 14px 16px;
  border-radius: 16px;
  background: linear-gradient(180deg, var(--theme-panel-bg-soft), var(--theme-panel-bg));
  border: 1px solid var(--theme-panel-border);
  transition: transform var(--motion-duration-base) var(--motion-ease-soft), box-shadow var(--motion-duration-base) var(--motion-ease-soft), border-color var(--motion-duration-base) var(--motion-ease-soft);

  &.ready {
    background: linear-gradient(180deg, var(--theme-panel-bg-strong), var(--theme-panel-bg-soft));
    border-color: var(--theme-border-strong);
  }
}

.repaint-status-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 24px var(--theme-shadow-soft);
}

.repaint-status-title {
  color: var(--theme-title);
  font-size: 14px;
  font-weight: 700;
}

.repaint-status-desc {
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.7;
}

.repaint-status-uploading {
  margin-top: 8px;
  color: var(--theme-accent-text);
  font-size: 12px;
  font-weight: 700;
}

.repaint-canvas-shell {
  position: relative;
  border-radius: 18px;
}

.canvas-remove-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 2;
  width: 40px;
  height: 40px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 14px;
  background: rgba(38, 38, 42, 0.84);
  color: rgba(255, 255, 255, 0.92);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  cursor: pointer;
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.18);
  backdrop-filter: blur(8px);
  opacity: 0;
  transform: scale(0.92);
  transition:
    opacity var(--motion-duration-fast) var(--motion-ease-soft),
    background var(--motion-duration-fast) var(--motion-ease-soft),
    transform var(--motion-duration-fast) var(--motion-ease-soft),
    border-color var(--motion-duration-fast) var(--motion-ease-soft);

  &:hover {
    background: rgba(48, 48, 54, 0.94);
    border-color: rgba(255, 255, 255, 0.24);
    transform: translateY(-1px) scale(1.03);
  }

  &:active {
    transform: scale(0.94);
  }
}

.reverse-preview-shell:hover .canvas-remove-btn,
.reverse-preview-shell:focus-within .canvas-remove-btn,
.repaint-canvas-shell:hover .canvas-remove-btn,
.repaint-canvas-shell:focus-within .canvas-remove-btn {
  opacity: 1;
  transform: scale(1);
}

.repaint-toolbar {
  margin-top: 14px;
  padding: 10px 14px;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: linear-gradient(180deg, rgba(46, 46, 52, 0.96), rgba(34, 34, 38, 0.96));
  display: flex;
  align-items: center;
  gap: 10px;
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.18);
}

.tool-btn {
  width: 42px;
  height: 42px;
  border: 1px solid transparent;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.9);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  cursor: pointer;
  transition:
    background var(--motion-duration-fast) var(--motion-ease-soft),
    color var(--motion-duration-fast) var(--motion-ease-soft),
    opacity var(--motion-duration-fast) var(--motion-ease-soft),
    border-color var(--motion-duration-fast) var(--motion-ease-soft),
    transform var(--motion-duration-fast) var(--motion-ease-soft);

  &:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.12);
    border-color: rgba(255, 255, 255, 0.12);
    transform: translateY(-2px);
  }

  &.active {
    background: linear-gradient(180deg, rgba(116, 107, 255, 0.9), rgba(95, 91, 240, 0.9));
    color: #fff;
    border-color: rgba(170, 167, 255, 0.38);
    box-shadow: 0 10px 18px rgba(90, 87, 230, 0.24);
  }

  &:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }

  &:active:not(:disabled) {
    transform: scale(0.95);
  }
}

.toolbar-divider {
  width: 1px;
  height: 30px;
  background: rgba(255, 255, 255, 0.12);
}

.toolbar-slider {
  flex: 1;
  min-width: 120px;
  max-width: 180px;
}

.brush-preview {
  flex: 0 0 auto;
  min-width: 10px;
  min-height: 10px;
  max-width: 34px;
  max-height: 34px;
  border-radius: 50%;
  background: rgba(255, 171, 37, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.56);
  box-shadow:
    0 0 0 6px rgba(255, 255, 255, 0.06),
    0 4px 10px rgba(0, 0, 0, 0.16);
}

.brush-slider {
  margin: 0 4px;

  :deep(.ant-slider-rail) {
    height: 8px;
    background: rgba(255, 255, 255, 0.2);
    border-radius: 999px;
  }

  :deep(.ant-slider-track) {
    height: 8px;
    background: #6d6cff;
    border-radius: 999px;
  }

  :deep(.ant-slider-handle) {
    width: 24px;
    height: 24px;
    margin-top: -8px;
    border: none;
    background: transparent;
    box-shadow: none;

    &::after {
      width: 24px;
      height: 24px;
      border-color: #6d6cff;
      background: #fff;
      box-shadow: 0 4px 12px rgba(57, 56, 138, 0.32);
    }
  }
}

.mask-tip {
  margin-top: 12px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.inpaint-prompt-block {
  margin-top: 6px;
}

/* --- Results --- */
.result-panel {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  padding: 16px 18px 18px;
  animation: generate-slide-right-in var(--motion-duration-stage-delayed) var(--motion-ease-enter) 0.14s both;
}

.result-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.result-head-main {
  min-width: 0;
}

.result-panel-head {
  margin-bottom: 2px;
}

.result-tips {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 0;
}

.result-tip-line {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.result-retain-badge {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(var(--theme-surface-strong-rgb), 0.96), rgba(var(--theme-page-base-rgb), 0.92));
  border: 1px solid var(--theme-panel-border);
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
  box-shadow: 0 10px 20px var(--theme-shadow-soft);
}

.result-retain-icon {
  color: #e25555;
  font-size: 13px;
}

.result-tip-link {
  color: var(--theme-link);
  font-weight: 700;
  text-decoration: none;

  &:hover {
    color: var(--theme-link-hover);
    text-decoration: underline;
  }
}

.result-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  align-items: start;
  gap: 12px;
  margin-top: 12px;
}

.result-column {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  margin-top: 14px;
  padding-right: 4px;
  display: flex;
  flex-direction: column;
  scrollbar-width: thin;
  scrollbar-color: rgba(210, 188, 150, 0.45) transparent;

  &::-webkit-scrollbar {
    width: 8px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    border-radius: 999px;
    border: 2px solid transparent;
    background-clip: padding-box;
    background: rgba(210, 188, 150, 0.45);
  }

  &:hover::-webkit-scrollbar-thumb {
    background: rgba(193, 164, 116, 0.58);
  }
}

.result-list-footnote {
  margin: 12px 4px 2px;
  padding: 0 2px 4px;
  color: #a38a65;
  font-size: 12px;
  line-height: 1.7;
  text-align: center;
}

.result-card {
  display: block;
  width: 100%;
  margin: 0;
  position: relative;
  border-radius: 16px;
  transition: transform var(--motion-duration-hover) var(--motion-ease-enter);

  &:hover {
    transform: translateY(-4px);
  }

  &:active {
    transform: scale(0.992);
  }
}

.result-frame {
  position: relative;
  aspect-ratio: var(--result-aspect-ratio, 1 / 1);
  min-height: 0;
  border-radius: 16px;
  overflow: hidden;
  border: 1px dashed var(--theme-panel-border);
  background: var(--theme-panel-bg-soft);
  box-shadow: 0 12px 24px var(--theme-shadow-soft);
  transition:
    transform var(--motion-duration-hover) var(--motion-ease-enter),
    box-shadow var(--motion-duration-hover) var(--motion-ease-soft),
    border-color var(--motion-duration-hover) var(--motion-ease-soft);

  img {
    width: 100%;
    height: 100%;
    display: block;
    object-fit: cover;
    transition: transform var(--motion-duration-emphasis) var(--motion-ease-enter);
  }

  &.clickable {
    cursor: pointer;
  }

  &.pending {
    background:
      linear-gradient(180deg, rgba(255, 252, 246, 0.24), rgba(255, 248, 238, 0.34)),
      linear-gradient(180deg, var(--theme-panel-bg-soft), var(--theme-panel-bg));
  }

  &.pending::before {
    content: "";
    position: absolute;
    inset: 0;
    background: var(--result-pending-bg-image) center / cover no-repeat;
    opacity: 0.5;
    pointer-events: none;
  }

  &.failed {
    border-color: rgba(214, 87, 75, 0.34);
    background: linear-gradient(180deg, #fff0ed, #ffe1db);
    box-shadow: 0 14px 26px rgba(214, 87, 75, 0.16);
  }
}

.result-card:hover .result-frame.clickable {
  border-color: var(--theme-border-strong);
  box-shadow: 0 16px 28px var(--theme-shadow-medium);
}

.result-card:hover .result-frame.clickable img {
  transform: scale(1.03);
}

.failed-image {
  object-fit: contain !important;
  padding: 28px;
  background: linear-gradient(180deg, #fff2ef, #ffdcd5);
  opacity: 0.96;
}

.result-actions {
  position: absolute;
  inset: auto 12px 12px auto;
  display: flex;
  gap: 8px;
  opacity: 0;
  transform: translateY(6px);
  pointer-events: none;
  transition:
    opacity var(--motion-duration-fast) var(--motion-ease-soft),
    transform var(--motion-duration-fast) var(--motion-ease-soft);

  .icon-chip {
    border: 1px solid rgba(255, 240, 214, 0.18) !important;
    background: rgba(76, 52, 26, 0.58) !important;
    color: #fff7ea !important;
    box-shadow: 0 10px 20px rgba(34, 22, 10, 0.22);
    backdrop-filter: blur(10px);

    &:hover,
    &:focus {
      background: rgba(76, 52, 26, 0.78) !important;
      border-color: rgba(255, 240, 214, 0.26) !important;
      color: #fffdfa !important;
      box-shadow: 0 14px 26px rgba(34, 22, 10, 0.28);
    }

    &:disabled {
      border-color: rgba(255, 240, 214, 0.08) !important;
      background: rgba(56, 40, 24, 0.34) !important;
      color: rgba(255, 247, 234, 0.45) !important;
      box-shadow: none;
      opacity: 1;
    }
  }
}

.result-top-actions {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 3;
  display: flex;
  gap: 8px;
}

.frame-state {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #8d7758;
  font-size: 14px;
  background: linear-gradient(180deg, rgba(255, 250, 240, 0.1), rgba(255, 250, 240, 0.16));
  backdrop-filter: blur(0.25px);

  &.error {
    background: linear-gradient(
      180deg,
      rgba(255, 233, 228, 0.42),
      rgba(255, 221, 214, 0.92)
    );
    color: #c9493c;
  }
}

.frame-state-subtext {
  margin-top: -4px;
  color: rgba(141, 119, 88, 0.78);
  font-size: 12px;
}

.result-more-trigger.icon-chip {
  opacity: 0;
  transform: translateY(-6px);
  pointer-events: none;
  border: 1px solid rgba(255, 240, 214, 0.18) !important;
  background: rgba(76, 52, 26, 0.58) !important;
  color: #fff7ea !important;
  box-shadow: 0 10px 20px rgba(34, 22, 10, 0.22);
  backdrop-filter: blur(10px);
  transition:
    opacity var(--motion-duration-fast) var(--motion-ease-soft),
    transform var(--motion-duration-fast) var(--motion-ease-soft),
    background var(--motion-duration-fast) var(--motion-ease-soft),
    border-color var(--motion-duration-fast) var(--motion-ease-soft),
    color var(--motion-duration-fast) var(--motion-ease-soft),
    box-shadow var(--motion-duration-fast) var(--motion-ease-soft);

  &:hover,
  &:focus {
    background: rgba(76, 52, 26, 0.78) !important;
    border-color: rgba(255, 240, 214, 0.26) !important;
    color: #fffdfa !important;
    box-shadow: 0 14px 26px rgba(34, 22, 10, 0.28);
  }
}

.result-delete-trigger.icon-chip {
  opacity: 0;
  transform: translateY(-6px);
  pointer-events: none;
  border-color: rgba(255, 214, 209, 0.18) !important;
  background: rgba(180, 58, 43, 0.88) !important;
  color: #fff5f2 !important;
  box-shadow: 0 10px 22px rgba(140, 40, 28, 0.24);

  &:hover,
  &:focus {
    background: rgba(201, 73, 60, 0.98) !important;
    border-color: rgba(255, 224, 220, 0.24) !important;
    color: #fff7f5 !important;
    box-shadow: 0 14px 26px rgba(140, 40, 28, 0.34);
  }
}

.result-more-icon {
  font-size: 14px;
}

.result-more-trigger-failed.icon-chip {
  border-color: rgba(255, 214, 209, 0.18) !important;
  background: rgba(180, 58, 43, 0.88) !important;
  color: #fff5f2 !important;
  box-shadow: 0 10px 22px rgba(140, 40, 28, 0.24);

  &:hover,
  &:focus {
    background: rgba(201, 73, 60, 0.98) !important;
    border-color: rgba(255, 224, 220, 0.24) !important;
    color: #fff7f5 !important;
    box-shadow: 0 14px 26px rgba(140, 40, 28, 0.34);
  }
}

.result-card:hover .result-actions,
.result-card:focus-within .result-actions {
  opacity: 1;
  transform: translateY(0);
  pointer-events: auto;
}

.result-card:hover .result-more-trigger.icon-chip,
.result-card:focus-within .result-more-trigger.icon-chip,
.result-card:hover .result-delete-trigger.icon-chip,
.result-card:focus-within .result-delete-trigger.icon-chip {
  opacity: 1;
  transform: translateY(0);
  pointer-events: auto;
}

.icon-chip {
  width: 32px;
  height: 32px;
  border-radius: 999px !important;
  border: none !important;
  background: rgba(255, 255, 255, 0.92) !important;
  color: #684825 !important;
  box-shadow: 0 10px 16px rgba(0, 0, 0, 0.1);
  font-size: 14px !important;
  transition:
    transform var(--motion-duration-press) var(--motion-ease-soft),
    background var(--motion-duration-fast) var(--motion-ease-soft),
    color var(--motion-duration-fast) var(--motion-ease-soft),
    box-shadow var(--motion-duration-fast) var(--motion-ease-soft);

  &:hover,
  &:focus {
    transform: translateY(-1px);
    box-shadow: 0 14px 22px rgba(0, 0, 0, 0.12);
  }

  &:active {
    transform: scale(0.93);
  }

  &.danger {
    color: #d6574b !important;
  }
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .icon-chip {
  background: rgba(var(--theme-surface-strong-rgb), 0.92) !important;
  border: 1px solid var(--theme-panel-border) !important;
  color: var(--theme-accent-text) !important;
  box-shadow: 0 10px 16px var(--theme-shadow-soft);

  &:hover,
  &:focus {
    background: var(--theme-surface-strong) !important;
    color: var(--theme-accent-text-hover) !important;
    border-color: var(--theme-border-strong) !important;
    box-shadow: 0 14px 22px var(--theme-shadow-medium);
  }

  &.danger {
    color: #de8f84 !important;
  }
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-delete-trigger.icon-chip,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-more-trigger-failed.icon-chip {
  border-color: rgba(222, 143, 132, 0.24) !important;
  background: rgba(185, 56, 42, 0.82) !important;
  color: #fff5f2 !important;
  box-shadow: 0 12px 24px rgba(140, 40, 28, 0.3);

  &:hover,
  &:focus {
    background: rgba(185, 56, 42, 0.92) !important;
    border-color: rgba(240, 176, 166, 0.3) !important;
    color: #fff7f5 !important;
    box-shadow: 0 16px 28px rgba(140, 40, 28, 0.38);
  }
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-more-trigger.icon-chip {
  background: rgba(var(--theme-page-base-rgb), 0.82) !important;
  border-color: var(--theme-panel-border) !important;
  color: var(--theme-accent-contrast) !important;
  box-shadow: 0 10px 20px var(--theme-shadow-medium);
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-more-trigger.icon-chip:hover,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-more-trigger.icon-chip:focus {
  background: rgba(var(--theme-page-base-rgb), 0.94) !important;
  border-color: var(--theme-border-strong) !important;
  color: #ffffff !important;
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-more-trigger-failed.icon-chip {
  background: rgba(185, 56, 42, 0.82) !important;
  border-color: rgba(222, 143, 132, 0.28) !important;
  color: #fff5f2 !important;
}

/* --- Empty state --- */
.result-empty {
  flex: 1;
  min-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px 20px 28px;
  animation: generate-fade-up var(--motion-duration-reveal) var(--motion-ease-enter) 0.2s both;
}

.result-empty-copy {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  max-width: 420px;
  text-align: center;
}

.empty-illustration-shell {
  width: min(100%, 220px);
  margin-bottom: 8px;
}

.empty-illustration {
  display: block;
  width: 100%;
  height: auto;
  animation: generate-empty-float 8s ease-in-out infinite;
  transform-origin: center center;
  filter: drop-shadow(0 18px 34px rgba(217, 238, 243, 0.28));
}

.empty-title {
  margin-top: 8px;
  font-size: 17px;
  font-weight: 700;
  color: #8f7558;
}

.empty-desc {
  margin-top: 6px;
  font-size: 13px;
  color: #b8a080;
  line-height: 1.8;
}

/* --- History dialog --- */
.history-empty {
  text-align: center;
  padding: 32px 0;
  color: #a88962;
  font-size: 14px;
  animation: generate-fade-up var(--motion-duration-reveal-fast) var(--motion-ease-enter) both;
}

.history-list {
  max-height: 420px;
  overflow-y: auto;
}

.history-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  cursor: pointer;
  transition:
    background var(--motion-duration-micro) var(--motion-ease-soft),
    transform var(--motion-duration-micro) var(--motion-ease-soft),
    box-shadow var(--motion-duration-micro) var(--motion-ease-soft);

  &:hover {
    background: var(--theme-panel-bg-soft);
    transform: translateY(-1px);
    box-shadow: 0 10px 18px var(--theme-shadow-soft);
  }

  & + & {
    border-top: 1px solid var(--theme-border);
  }
}

.history-thumb {
  width: 52px;
  height: 52px;
  flex-shrink: 0;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--theme-panel-border);
  background: var(--theme-panel-bg-soft);

  img {
    width: 100%;
    height: 100%;
    display: block;
    object-fit: cover;
  }
}

.history-content {
  flex: 1;
  min-width: 0;
}

.history-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.history-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--theme-panel-bg-strong);
  color: var(--theme-accent-text);
  font-size: 11px;
  font-weight: 700;
}

.history-text {
  font-size: 13px;
  color: var(--theme-title);
  line-height: 1.6;
  word-break: break-all;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.history-del {
  flex-shrink: 0;
  color: var(--text-muted) !important;
  margin-top: 2px;
  transition: transform var(--motion-duration-press) var(--motion-ease-soft), color var(--motion-duration-fast) var(--motion-ease-soft);

  &:hover {
    color: #d6574b !important;
    transform: scale(1.05);
  }
}

.generate-result-enter-active,
.generate-result-leave-active {
  transition:
    opacity var(--motion-duration-emphasis) var(--motion-ease-soft),
    transform var(--motion-duration-emphasis-plus) var(--motion-ease-enter);
  transition-delay: var(--generate-result-delay, 0ms);
  will-change: opacity, transform;
}

.generate-result-enter-from,
.generate-result-leave-to {
  opacity: 0;
  transform: translate3d(0, 22px, 0) scale(0.985);
}

.generate-result-move {
  transition: transform var(--motion-duration-reveal-fast) var(--motion-ease-enter);
  will-change: transform;
}

.history-item-enter-active,
.history-item-leave-active {
  transition:
    opacity var(--motion-duration-base) var(--motion-ease-soft),
    transform var(--motion-duration-emphasis) var(--motion-ease-enter);
  transition-delay: var(--history-item-delay, 0ms);
}

.history-item-enter-from,
.history-item-leave-to {
  opacity: 0;
  transform: translate3d(0, 12px, 0);
}

.history-item-move {
  transition: transform var(--motion-duration-hover-slow) var(--motion-ease-enter);
}

.generate-panel-slide-enter-active,
.generate-panel-slide-leave-active {
  transition:
    opacity var(--motion-duration-slide) var(--motion-ease-soft),
    transform var(--motion-duration-slide) var(--motion-ease-enter),
    filter var(--motion-duration-slide) var(--motion-ease-soft);
}

.generate-panel-slide-enter-from,
.generate-panel-slide-leave-to {
  opacity: 0;
  transform: translate3d(0, -12px, 0) scale(0.985);
  filter: blur(6px);
}

@media (prefers-reduced-motion: reduce) {
  .generate-page,
  .generate-workbench,
  .left-col,
  .result-panel,
  .result-empty,
  .history-empty {
    animation: none !important;
  }

  .config-section,
  .history-btn,
  .generate-config-panel .upload-thumb,
  .generate-config-panel .upload-thumb img,
  .generate-config-panel .upload-add,
  .generate-config-panel .flat-select,
  .generate-btn,
  .source-upload-empty,
  .reverse-preview-shell,
  .reverse-preview-image,
  .reverse-action-btn,
  .repaint-status-card,
  .canvas-remove-btn,
  .tool-btn,
  .result-card,
  .result-frame,
  .result-frame img,
  .empty-illustration,
  .icon-chip,
  .history-item,
  .history-del,
  .generate-result-enter-active,
  .generate-result-leave-active,
  .generate-result-move,
  .history-item-enter-active,
  .history-item-leave-active,
  .history-item-move,
  .generate-panel-slide-enter-active,
  .generate-panel-slide-leave-active,
  .mode-switch-btn {
    transition: none !important;
  }
}

:deep(.generate-dropdown.ant-select-dropdown) {
  border-radius: 14px;
  padding: 6px;
  background: var(--theme-dropdown-bg);
  border: 1px solid var(--theme-panel-border);
  box-shadow: 0 18px 32px var(--theme-shadow-medium);
}

:deep(.generate-dropdown .ant-select-item) {
  border-radius: 10px;
}

:deep(.generate-dropdown .ant-select-item-option-active:not(.ant-select-item-option-disabled)) {
  background: var(--theme-dropdown-hover-bg);
}

:deep(.generate-dropdown .ant-select-item-option-selected:not(.ant-select-item-option-disabled)) {
  background: var(--theme-dropdown-selected-bg);
  color: var(--theme-dropdown-selected-text);
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 960px) {
  .generate-page {
    height: auto;
  }

  .generate-workbench {
    grid-template-columns: 1fr;
    height: auto;
  }

  .result-panel {
    min-height: auto;
    height: auto;
  }

  .result-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .result-body {
    overflow-y: visible;
    padding-right: 0;
  }

  .generate-mode-shell {
    min-height: unset;
  }

  .settings-panel,
  .generate-mode-shell {
    height: auto;
  }

  .settings-scroll {
    overflow-y: visible;
    padding: 0;
  }

  .generate-mode-switch {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    flex-wrap: nowrap;
  }

  .mode-switch-cluster:first-child {
    flex: 1 1 auto;
    min-width: 0;
  }

  .mode-switch-cluster:last-child {
    flex: 0 0 auto;
    margin-left: auto;
  }

  .mode-switch-group {
    flex-wrap: nowrap;
  }
}

@media (max-width: 640px) {
  .work-panel {
    padding: 16px;
    border-radius: 20px;
  }

  .generate-config-panel {
    padding: 15px;
  }

  .generate-config-panel .action-config-section {
    padding-bottom: 18px;
  }

  .generate-config-panel .settings-footer {
    z-index: 1;
    margin-top: 8px;
    padding-top: 0;
  }

  .generate-link-tip {
    flex-direction: column;
    align-items: stretch;
    gap: 2px;
  }

  .generate-link-tip-right {
    text-align: left;
  }

  .settings-row {
    flex-direction: column;
  }

  .settings-row-inline {
    flex-direction: row;
    align-items: center;
    gap: 10px;
  }

  .settings-row-inline .setting-item-inline {
    flex: 1 1 0;
    min-width: 0;
    justify-content: flex-start;
    gap: 6px;
  }

  .settings-row-inline .setting-item-inline label {
    min-width: auto;
    white-space: nowrap;
  }

  .settings-row-inline .setting-item-inline .flat-select {
    min-width: 0;
  }

  .settings-row-inline .setting-item-inline .flat-select :deep(.ant-select-selector) {
    height: 42px !important;
    padding: 0 10px !important;
  }

  .settings-row-inline .setting-item-inline .flat-select :deep(.ant-select-selection-item) {
    line-height: 42px !important;
  }

  .generate-config-panel .upload-thumb,
  .generate-config-panel .upload-add {
    width: 60px;
    height: 60px;
  }

  .result-list {
    grid-template-columns: 1fr;
  }

  .result-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .generate-mode-switch {
    margin-bottom: 12px;
    gap: 10px;
  }

  .mode-switch-group {
    gap: 8px;
  }

  .mode-switch-group-primary {
    gap: 8px;
  }

  .mode-switch-group-primary .mode-switch-btn {
    min-width: 0;
    flex: 1 1 0;
  }

  .mode-switch-btn.tool {
    flex: 0 0 auto;
    min-width: auto;
  }

  .tool-trigger {
    height: 42px;
    min-height: 42px;
    padding: 0 10px;
  }

  .generate-tab-label {
    gap: 6px;
    min-height: 38px;
    padding: 0 11px;
    font-size: 14px;
  }

  .mode-switch-trigger-value {
    font-size: 12px;
  }
}
</style>

<style lang="scss">
.generate-tool-dropdown .generate-tool-menu {
  min-width: 196px;
  padding: 12px;
  border-radius: 18px;
  border: 1px solid var(--theme-panel-border);
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-soft));
  box-shadow: 0 16px 28px var(--theme-shadow-soft);
}

.generate-tool-dropdown .generate-tool-menu .ant-menu-item {
  display: flex;
  align-items: center;
  min-height: 50px;
  margin: 0 !important;
  padding: 10px 16px !important;
  border-radius: 14px;
  color: var(--theme-title);
  font-weight: 700;
  transition:
    background var(--motion-duration-fast) var(--motion-ease-soft),
    color var(--motion-duration-fast) var(--motion-ease-soft),
    box-shadow var(--motion-duration-fast) var(--motion-ease-soft),
    transform var(--motion-duration-fast) var(--motion-ease-soft);
}

.generate-tool-dropdown .generate-tool-menu .ant-menu-item + .ant-menu-item {
  margin-top: 8px !important;
}

.generate-tool-dropdown .generate-tool-menu .ant-menu-item:hover {
  color: var(--theme-accent-text-hover) !important;
  background: linear-gradient(180deg, var(--theme-panel-bg-soft), var(--theme-panel-bg-strong)) !important;
  box-shadow: 0 10px 22px var(--theme-shadow-soft);
  transform: translateY(-1px);
}

.generate-tool-dropdown .generate-tool-menu .ant-menu-item-selected {
  color: var(--theme-accent-contrast) !important;
  background: var(--theme-accent) !important;
  box-shadow:
    inset 0 1px 0 var(--theme-panel-inset),
    0 10px 22px var(--theme-shadow-strong);
}

.model-help-popover {
  max-width: calc(100vw - 40px);

  .ant-popover-inner {
    padding: 0;
    border-radius: 16px;
    background: rgba(12, 12, 12, 0.96);
    box-shadow: 0 18px 42px rgba(0, 0, 0, 0.28);
  }

  .ant-popover-inner-content {
    padding: 12px 14px;
  }

  .ant-popover-arrow::before {
    background: rgba(12, 12, 12, 0.96);
  }

  .model-help-tip {
    width: min(620px, calc(100vw - 68px));
    color: #f5f5f5;
  }
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page {
  --config-title-color: var(--theme-title);
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .mode-switch-btn {
  color: var(--text-secondary);

  &:hover {
    color: var(--theme-title);
  }
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .mode-switch-group-primary .mode-switch-btn {
  border-color: var(--theme-control-border-strong);
  background: var(--theme-panel-bg);
  box-shadow: none;
  color: var(--theme-accent-text);

  &:hover,
  &:focus {
    color: var(--theme-accent-text-hover);
    border-color: var(--theme-border-strong);
    background: var(--theme-control-hover-bg);
    box-shadow: 0 10px 20px var(--theme-shadow-soft);
  }
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .mode-switch-group-primary .mode-switch-btn.active,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .mode-switch-group-primary .mode-switch-btn.active:hover,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .mode-switch-group-primary .mode-switch-btn.active:focus {
  color: var(--theme-accent-contrast);
  border-color: transparent;
  background: var(--theme-accent);
  box-shadow: 0 14px 24px var(--theme-shadow-strong);
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .mode-switch-btn.tool {
  border-color: var(--theme-panel-border);
  background: var(--theme-panel-bg-muted);
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .mode-switch-btn.tool.active {
  border-color: var(--theme-accent);
  background: var(--theme-accent);
  color: var(--theme-accent-contrast);
  box-shadow: 0 8px 16px var(--theme-shadow-medium);
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .settings-footer {
  background: linear-gradient(
    180deg,
    rgba(var(--theme-surface-strong-rgb), 0),
    rgba(var(--theme-surface-strong-rgb), 0.92) 28%,
    var(--theme-surface-strong)
  );
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .history-btn {
  color: var(--text-secondary) !important;
  background: var(--theme-panel-bg-soft) !important;
  border-color: var(--theme-panel-border) !important;

  &:hover {
    color: var(--theme-title) !important;
    background: var(--theme-control-hover-bg) !important;
    border-color: var(--theme-border-strong) !important;
    box-shadow: 0 10px 20px var(--theme-shadow-soft);
  }
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .generate-config-panel .prompt-input {
  border: none !important;
  background: transparent !important;
  box-shadow: none !important;

  &:focus,
  &:hover {
    box-shadow: none !important;
  }

  :deep(.ant-input-data-count) {
    color: var(--text-muted);
  }

  :deep(textarea) {
    color: var(--theme-title) !important;
    caret-color: var(--theme-title);
    border-color: var(--theme-control-border) !important;
    background: var(--theme-control-bg) !important;
    box-shadow: none;
  }

  :deep(textarea:hover),
  :deep(textarea:focus) {
    border-color: var(--theme-border-accent) !important;
    box-shadow: 0 0 0 3px var(--theme-focus-ring);
  }

  :deep(textarea::placeholder) {
    color: var(--text-muted);
  }
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .prompt-label-row label,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .setting-item label,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .field-block > label,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-panel-head h3,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-empty .empty-title {
  color: var(--theme-title) !important;
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .work-panel {
  background: linear-gradient(180deg, var(--theme-panel-bg) 0%, var(--theme-panel-bg-soft) 100%);
  border-color: var(--theme-panel-border);
  box-shadow: 0 18px 45px var(--theme-shadow-soft);
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .settings-panel.generate-config-panel {
  background: linear-gradient(
    180deg,
    rgba(var(--theme-surface-strong-rgb), 0.98) 0%,
    rgba(var(--theme-surface-strong-rgb), 0.94) 32%,
    var(--theme-panel-bg-soft) 100%
  );
  border-color: var(--theme-panel-border);
  box-shadow:
    inset 0 1px 0 var(--theme-panel-inset),
    0 18px 40px var(--theme-shadow-soft);
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .settings-panel.generate-config-panel .settings-footer {
  background: linear-gradient(
    180deg,
    rgba(var(--theme-surface-strong-rgb), 0),
    rgba(var(--theme-surface-strong-rgb), 0.9) 26%,
    var(--theme-panel-bg-soft)
  );
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .panel-hint,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .source-upload-desc,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .reverse-result-placeholder,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .repaint-status-desc,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .mask-tip,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-tip-line,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-retain-badge,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .history-text,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-list-footnote,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-empty .empty-desc,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .frame-state {
  color: var(--text-secondary);
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .generate-config-panel .upload-thumb {
  border-color: var(--theme-panel-border);
  background: var(--theme-panel-bg-soft);
  box-shadow: 0 8px 18px var(--theme-shadow-soft);

  &:hover {
    border-color: var(--theme-border-strong);
    box-shadow: 0 14px 24px var(--theme-shadow-medium);
  }
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .generate-config-panel .upload-thumb-mask {
  background: rgba(var(--theme-page-base-rgb), 0.78);
  color: var(--text-secondary);

  &.error {
    background: rgba(185, 56, 42, 0.18);
  }
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .generate-config-panel .upload-add,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .source-upload-empty {
  border-color: var(--theme-panel-border-strong);
  background: var(--theme-panel-bg-soft);
  color: var(--text-secondary);
  box-shadow: 0 10px 22px var(--theme-shadow-soft);

  &:hover {
    border-color: var(--theme-border-strong);
    box-shadow: 0 14px 24px var(--theme-shadow-medium);
  }
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .generate-config-panel .flat-select {
  background: var(--theme-control-bg);
  border-color: var(--theme-control-border);
  box-shadow: none;

  &:hover {
    border-color: var(--theme-border-strong);
    box-shadow: 0 12px 22px var(--theme-shadow-soft);
  }

  &:focus-within {
    border-color: var(--theme-border-accent);
    box-shadow: 0 0 0 3px var(--theme-focus-ring);
  }

  :deep(.ant-select-selector) {
    color: var(--theme-title);
  }

  :deep(.ant-select-arrow),
  :deep(.ant-select-selection-placeholder) {
    color: var(--text-muted);
  }
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .model-option-label {
  color: var(--theme-title);
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .model-option-desc {
  color: var(--text-secondary);
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .num-slider {
  :deep(.ant-slider-rail) {
    background: var(--theme-control-border);
  }

  :deep(.ant-slider-track) {
    background: var(--theme-accent);
  }

  :deep(.ant-slider-handle) {
    &::after {
      border: 3px solid var(--theme-accent);
      background: var(--theme-surface-strong);
      box-shadow: 0 4px 12px var(--theme-shadow-medium);
    }

    &:hover::after,
    &:focus::after {
      border-color: var(--theme-accent);
      box-shadow: 0 4px 16px var(--theme-shadow-strong);
    }
  }

  :deep(.ant-slider-dot) {
    border-color: var(--theme-control-border-strong);
  }

  :deep(.ant-slider-dot-active) {
    border-color: var(--theme-accent);
  }

  :deep(.ant-slider-mark-text) {
    color: var(--text-muted);
  }

  :deep(.ant-slider-mark-text-active) {
    color: var(--theme-title);
  }
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-retain-badge {
  background: var(--theme-panel-bg) !important;
  border: 1px solid var(--theme-panel-border) !important;
  box-shadow: none !important;
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-retain-icon {
  color: var(--theme-accent) !important;
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .generate-btn,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .reverse-action-btn-primary,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .generate-tool-dropdown .generate-tool-menu .ant-menu-item-selected {
  background: var(--theme-accent) !important;
  color: var(--theme-accent-contrast) !important;
  border-color: var(--theme-accent) !important;
  box-shadow: 0 14px 24px var(--theme-shadow-strong) !important;
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .generate-btn:hover,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .generate-btn:focus,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .reverse-action-btn-primary:hover,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .reverse-action-btn-primary:focus {
  background: var(--theme-accent-strong) !important;
  box-shadow: 0 16px 28px var(--theme-shadow-strong) !important;
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .generate-btn:disabled {
  background: var(--theme-control-hover-bg) !important;
  color: var(--text-muted) !important;
  box-shadow: none !important;
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .source-upload-icon,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .repaint-status-uploading,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-tip-link {
  color: var(--theme-accent);
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .source-upload-title,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .repaint-status-title {
  color: var(--theme-title);
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .reverse-preview-shell,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .reverse-result-card {
  border-color: var(--theme-panel-border);
  background: var(--theme-panel-bg-soft);
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-frame {
  border-color: var(--theme-panel-border) !important;
  background: var(--theme-panel-bg) !important;
  box-shadow: 0 12px 28px var(--theme-shadow-soft) !important;
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-frame.pending {
  background: var(--theme-panel-bg) !important;
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-frame.failed,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .failed-image,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .frame-state,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .frame-state.error {
  background: var(--theme-panel-bg-soft) !important;
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-card:hover .result-frame.clickable {
  border-color: var(--theme-border-strong) !important;
  box-shadow: 0 18px 30px var(--theme-shadow-medium) !important;
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-empty {
  background: transparent !important;
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-body {
  scrollbar-color: rgba(113, 113, 122, 0.42) transparent;
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-body::-webkit-scrollbar-thumb {
  background: rgba(113, 113, 122, 0.42);
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .result-body:hover::-webkit-scrollbar-thumb {
  background: rgba(82, 82, 91, 0.56);
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .reverse-preview-shell:hover {
  box-shadow: 0 18px 30px var(--theme-shadow-soft);
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .reverse-action-btn-secondary {
  color: var(--theme-accent-text) !important;
  background: var(--theme-panel-bg-strong) !important;
  border-color: var(--theme-panel-border-strong) !important;

  &:hover,
  &:focus {
    color: var(--theme-accent-text-hover) !important;
    background: var(--theme-control-hover-bg) !important;
    border-color: var(--theme-border-strong) !important;
  }
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .reverse-result-placeholder,
html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .repaint-status-card {
  border-color: var(--theme-panel-border);
  background: var(--theme-panel-bg-soft);
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .repaint-status-card.ready {
  background: var(--theme-control-hover-bg);
  border-color: var(--theme-border-strong);
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .repaint-status-card:hover {
  box-shadow: 0 14px 24px var(--theme-shadow-soft);
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .brush-preview {
  background: rgba(52, 54, 61, 0.5);
  border-color: var(--theme-border-strong);
}

html:is([data-theme="dark"], [data-theme="midnight"]) .generate-page .generate-tool-dropdown .generate-tool-menu .ant-menu-item-selected {
  box-shadow: 0 10px 22px var(--theme-shadow-medium) !important;
}

.generate-tool-dropdown .generate-tool-menu .ant-menu-item .anticon {
  font-size: 18px;
  color: currentColor;
}
</style>
