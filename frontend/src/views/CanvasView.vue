<script setup lang="ts">
import { computed, h, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { message, Modal } from "ant-design-vue";
import {
  AimOutlined,
  ClearOutlined,
  DeleteOutlined,
  DownloadOutlined,
  DownOutlined,
  EditOutlined,
  InfoCircleOutlined,
  LoadingOutlined,
  MessageOutlined,
  MinusOutlined,
  PictureOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  HistoryOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  UploadOutlined,
} from "@ant-design/icons-vue";
import { createCanvas, createCanvasNode, createCanvasTask, deleteCanvasNode, getCanvas, listCanvases, updateCanvas, updateCanvasEdge, updateCanvasNode, updateCanvasNodesBatch, updateCanvasViewport } from "@/api/canvases";
import { listUsers } from "@/api/admin";
import { getMe } from "@/api/auth";
import { getTaskScenes } from "@/api/config";
import { deleteHistoryTask } from "@/api/history";
import { getDisplayImageUrl, getDownloadUrl, getPreviewImageUrl } from "@/api/images";
import { getTasks } from "@/api/tasks";
import { uploadReferenceImage } from "@/api/upload";
import FeedbackDialog from "@/components/feedback/FeedbackDialog.vue";
import AdminUserInfoDialog from "@/components/admin/AdminUserInfoDialog.vue";
import HistoryDetailDialog from "@/components/history/HistoryDetailDialog.vue";
import { withApiBaseUrl, withBaseUrl } from "@/lib/assets";
import { getTaskImageFailureMessage } from "@/lib/generationErrors";
import { useAuthStore } from "@/stores/auth";
import type { AdminUser, CanvasEdge, CanvasNode, TaskResult, TaskSceneConfig, UserCanvasSummary, UserHistoryCard } from "@/types";

const props = defineProps<{
  projectId?: string;
}>();

type CanvasMode = "textGenerate" | "imageEdit";
type UploadStatus = "uploading" | "success" | "failed";
type ComposerPopover = "model" | "size" | "resolution";
type UploadMenuAnchor = "reference";
type CanvasBackgroundMode = "grid" | "solid";

interface CanvasReferenceOption {
  id: string;
  imageUrl: string;
  displayUrl: string;
  sourceNodeId?: number;
}

interface ReferenceItem {
  id: string;
  localUrl: string;
  remoteUrl: string;
  status: UploadStatus;
  sourceNodeId?: number;
  objectUrl?: string;
}

type CanvasWorkbenchNode = CanvasNode & {
  uploadStatus?: UploadStatus;
  localObjectUrl?: string;
  uploadError?: string;
};

const DEFAULT_ASPECT_RATIO_OPTIONS = [
  { label: "1:1", value: "1:1" },
  { label: "3:4", value: "3:4" },
  { label: "4:3", value: "4:3" },
  { label: "9:16", value: "9:16" },
  { label: "16:9", value: "16:9" },
];
const DEFAULT_IMAGE_SIZE_OPTIONS = [
  { label: "1K", value: "1K" },
  { label: "2K", value: "2K" },
  { label: "4K", value: "4K" },
];
const DEFAULT_NODE_WIDTH = 320;
const DEFAULT_NODE_HEIGHT = 420;
const CANVAS_ARRANGE_COLUMN_GAP = 34;
const CANVAS_ARRANGE_ROW_GAP = 96;
const MIN_ZOOM = 0.2;
const MAX_ZOOM = 2.4;
const CANVAS_BACKGROUND_STORAGE_KEY = "banana-canvas-background";
const failedResultAsset = withBaseUrl("failed-result.svg");
const generateEmptyStateAsset = withBaseUrl("generate-task-card.svg");
const neutralIndicatorStyle = { fontSize: "24px", color: "var(--text-secondary)" };

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const openPurchaseEntry = inject<() => void>("openPurchaseEntry", () => {});

function isInsufficientCreditsError(err: any) {
  const detail = String(err?.response?.data?.detail || err?.message || "");
  return detail.includes("积分不足");
}

function showInsufficientCreditsPurchase(detail?: string) {
  if (detail) {
    message.warning(detail);
  }
  openPurchaseEntry();
}

const canvases = ref<UserCanvasSummary[]>([]);
const selectedCanvasId = ref<number | null>(null);
const selectedCanvas = computed(() => canvases.value.find((item) => item.id === selectedCanvasId.value) || null);
const selectedCanvasProjectId = computed(() => selectedCanvas.value?.project_id || "");
const canvasReadOnlyState = ref(false);
const canvasReadOnly = computed(() => canvasReadOnlyState.value);
const adminUsers = ref<AdminUser[]>([]);
const readonlyOwnerDialogOpen = ref(false);
const selectedReadonlyOwner = ref<AdminUser | null>(null);
const readonlyCanvasOwnerFallback = computed<AdminUser | null>(() => {
  const canvas = selectedCanvas.value;
  if (!canvas?.owner_user_id) return null;
  return {
    id: canvas.owner_user_id,
    username: canvas.owner_username || "未知用户",
    avatar_url: canvas.owner_avatar_url || "",
    role: "user",
    status: "",
    is_whitelisted: false,
    credits: 0,
    consumed_credits: 0,
    created_at: "",
  };
});
const canvasFeedbackAppendContent = computed(() => {
  const url = selectedCanvasProjectId.value
    ? `${window.location.origin}/canvas/${selectedCanvasProjectId.value}`
    : window.location.href;
  return [
    "【反馈场景】无限画布",
    `【画布链接】${url}`,
    selectedCanvas.value?.name ? `【画布名称】${selectedCanvas.value.name}` : "",
  ].filter(Boolean).join("\n");
});
const nodes = ref<CanvasWorkbenchNode[]>([]);
const edges = ref<CanvasEdge[]>([]);
const loading = ref(false);
const creatingCanvas = ref(false);
const canvasMenuOpen = ref(false);
const guideOpen = ref(false);
const canvasSettingsOpen = ref(false);
const freeNodeMenuOpen = ref(false);
const generatePanelCollapsed = ref(false);
const composerPopover = ref<ComposerPopover | null>(null);
const projectSwitcherRef = ref<HTMLElement | null>(null);
const canvasStageRef = ref<HTMLElement | null>(null);
const viewport = ref({ x: 0, y: 0, zoom: 1 });
const viewportSaveTimer = ref<ReturnType<typeof setTimeout> | null>(null);

const taskScenes = ref<TaskSceneConfig[]>([]);
const sceneConfigLoading = ref(false);
const canvasMode = ref<CanvasMode>("imageEdit");
const composerModeSwitching = ref(false);
const selectedModel = ref("");
const prompt = ref("");
const numImages = ref(1);
const size = ref("9:16");
const resolution = ref("2K");
const customSize = ref("");
const promptSourceNodeId = ref<number | null>(null);
const generating = ref(false);
const uploadMenuOpen = ref(false);
const uploadMenuAnchor = ref<UploadMenuAnchor>("reference");
const canvasReferenceSelectMode = ref(false);
const referenceDragActive = ref(false);
const referenceDragCounter = ref(0);
const referenceItems = ref<ReferenceItem[]>([]);
const referenceInputRef = ref<HTMLInputElement | null>(null);
const freeNodeImageInputRef = ref<HTMLInputElement | null>(null);

const previewVisible = ref(false);
const previewCurrent = ref("");
const selectedNodeId = ref<number | null>(null);
const detailOpen = ref(false);
const detailItem = ref<UserHistoryCard | null>(null);
const feedbackDialogOpen = ref(false);
const feedbackTarget = ref<TaskResult | null>(null);
const canvasFeedbackOpen = ref(false);
const nodeSearchOpen = ref(false);
const nodeSearchKeyword = ref("");
const nodeSearchQuery = ref("");
const textNodeEditSaving = ref(false);
const textNodeEditTarget = ref<CanvasNode | null>(null);
const textNodeEditContent = ref("");
const loadedWebpImageUrls = ref<Set<string>>(new Set());
const taskPollTimer = ref<ReturnType<typeof setInterval> | null>(null);
const pollingInFlight = ref(false);
const canvasBackgroundMode = ref<CanvasBackgroundMode>(
  localStorage.getItem(CANVAS_BACKGROUND_STORAGE_KEY) === "solid" ? "solid" : "grid"
);

const isImageEditMode = computed(() => canvasMode.value === "imageEdit");
const hasComposerDraftContent = computed(() => !!prompt.value.trim() || referenceItems.value.length > 0);
const textGenerateModels = computed(() => taskScenes.value.filter((item) => item.scene_type === "generate" && item.scene_key !== "prompt_reverse" && item.scene_key !== "inpaint"));
const imageEditModels = computed(() => {
  const models = taskScenes.value.filter((item) => item.scene_type === "image_edit");
  return models.length ? models : textGenerateModels.value;
});
const generationModels = computed(() => (isImageEditMode.value ? imageEditModels.value : textGenerateModels.value));
const selectedModelOption = computed(() => generationModels.value.find((item) => item.scene_key === selectedModel.value) || null);
const maxReferenceImages = computed(() => Math.max(0, Number(selectedModelOption.value?.max_reference_images || (isImageEditMode.value ? 6 : 0))));
const referenceSlotsRemaining = computed(() => Math.max(0, maxReferenceImages.value - referenceItems.value.length));
const textGenerateBlockedByReferences = computed(() => !isImageEditMode.value && referenceItems.value.length > 0);
const selectedModelCreditCost = computed(() => {
  const resolutionKey = (resolution.value || "").trim();
  const resolutionCosts = selectedModelOption.value?.resolution_credit_costs || {};
  if (resolutionKey && Object.prototype.hasOwnProperty.call(resolutionCosts, resolutionKey)) {
    return Number(resolutionCosts[resolutionKey] || 0);
  }
  return Number(selectedModelOption.value?.credit_cost || 0);
});
const generationCreditCost = computed(() => Math.max(0, numImages.value * selectedModelCreditCost.value));
const generateButtonText = computed(() => {
  if (canvasReadOnly.value) return "只读模式";
  return generationCreditCost.value > 0 ? `生成 · ${generationCreditCost.value} 积分` : "生成";
});
const userCredits = computed(() => auth.user?.credits ?? 0);
const sizeOptions = computed(() => selectedModelOption.value?.aspect_ratio_options?.length ? selectedModelOption.value.aspect_ratio_options : DEFAULT_ASPECT_RATIO_OPTIONS);
const resolutionOptions = computed(() => selectedModelOption.value?.image_size_options?.length ? selectedModelOption.value.image_size_options : DEFAULT_IMAGE_SIZE_OPTIONS);
const canGenerate = computed(() => !canvasReadOnly.value && !!selectedCanvasProjectId.value && !!selectedModel.value && !!prompt.value.trim() && !textGenerateBlockedByReferences.value && !generating.value);
const taskCountOptions = Array.from({ length: 8 }, (_, index) => index + 1);
const activeTaskIds = computed(() => nodes.value
  .map((node) => node.task)
  .filter((task): task is TaskResult => !!task && !["success", "failed"].includes(task.status))
  .map((task) => task.id));
const selectedNode = computed(() => nodes.value.find((node) => node.id === selectedNodeId.value) || null);
const selectedNodeToolbarStyle = computed(() => {
  const node = selectedNode.value;
  if (!node) return {};
  return {
    left: `${viewport.value.x + node.x * viewport.value.zoom}px`,
    top: `${viewport.value.y + node.y * viewport.value.zoom - 24}px`,
    zIndex: node.z_index + 1000,
  };
});
const focusedCanvasNodeId = computed(() => {
  if (viewport.value.zoom <= 1) return null;
  const rect = canvasStageRef.value?.getBoundingClientRect();
  if (!rect) return null;
  const center = screenToWorld(rect.left + rect.width / 2, rect.top + rect.height / 2);
  const focusedNodes = nodes.value.filter((node) => {
    const hasImage = !!(node.task?.images || []).find((item) => item.status === "success" && (item.image_url || item.preview_url || item.thumb_url));
    if (!hasImage) return false;
    const width = Number(node.width || DEFAULT_NODE_WIDTH);
    const height = getNodeCardHeight(node);
    return center.x >= node.x && center.x <= node.x + width && center.y >= node.y && center.y <= node.y + height;
  });
  if (!focusedNodes.length) return null;
  return focusedNodes.sort((a, b) => Number(b.z_index || 0) - Number(a.z_index || 0))[0].id;
});
const modelOptions = computed(() => taskScenes.value.map((item) => ({
  label: item.display_name || item.scene_label || item.scene_key,
  value: item.scene_key,
})));
const nodeSearchResults = computed(() => {
  const query = nodeSearchQuery.value.trim().toLowerCase();
  return nodes.value
    .filter((node) => {
      if (isNodeTaskDeleted(node)) return false;
      if (!query) return true;
      return getNodeSearchText(node).includes(query);
    })
    .slice(0, 50);
});
const canvasReferenceOptions = computed<CanvasReferenceOption[]>(() => nodes.value.flatMap((node) => {
  if (node.node_type === "image" && node.image_url) {
    return [{
      id: `${node.id}-free-image`,
      imageUrl: node.image_url,
      displayUrl: node.image_url,
      sourceNodeId: node.id,
    }];
  }
  const task = node.task;
  if (!task || task.status !== "success") return [];
  return (task.images || [])
    .filter((image) => image.status === "success" && (image.image_url || image.preview_url || image.thumb_url))
    .map((image, index) => ({
      id: `${node.id}-${image.id || index}`,
      imageUrl: image.image_url || image.preview_url || image.thumb_url || "",
      displayUrl: getDisplayImageUrl(image),
      sourceNodeId: node.id,
    }));
}));
const nodeMap = computed(() => new Map(nodes.value.map((node) => [node.id, node])));
const edgesBySource = computed(() => {
  const groups = new Map<number, CanvasEdge[]>();
  edges.value.forEach((edge) => {
    if (!nodeMap.value.has(edge.source_node_id) || !nodeMap.value.has(edge.target_node_id)) return;
    const list = groups.get(edge.source_node_id) || [];
    list.push(edge);
    groups.set(edge.source_node_id, list);
  });
  return groups;
});

function canCollapseEdgeGroup(sourceNode: CanvasNode | undefined, group: CanvasEdge[]) {
  if (!sourceNode || !group.length) return false;
  return sourceNode.node_type === "text" || group.length > 1;
}

const collapsedSourceIds = computed(() => {
  const ids = new Set<number>();
  edgesBySource.value.forEach((group, sourceNodeId) => {
    const sourceNode = nodeMap.value.get(sourceNodeId);
    if (canCollapseEdgeGroup(sourceNode, group) && group.every((edge) => edge.is_collapsed)) ids.add(sourceNodeId);
  });
  return ids;
});
const visibleCanvasEdges = computed(() => edges.value.filter((edge) => {
  if (collapsedSourceIds.value.has(edge.source_node_id)) return false;
  return nodeMap.value.has(edge.source_node_id) && nodeMap.value.has(edge.target_node_id);
}));
const collapsedEdgeMarkers = computed(() => Array.from(collapsedSourceIds.value).map((sourceNodeId) => {
  const sourceNode = nodeMap.value.get(sourceNodeId);
  const group = edgesBySource.value.get(sourceNodeId) || [];
  if (!sourceNode || !group.length) return null;
  return {
    sourceNodeId,
    count: group.length,
    x: sourceNode.x + sourceNode.width + 12,
    y: sourceNode.y + getNodeCardHeight(sourceNode) / 2,
  };
}).filter((item): item is { sourceNodeId: number; count: number; x: number; y: number } => !!item));
const expandedEdgeGroupControls = computed(() => Array.from(edgesBySource.value.entries()).map(([sourceNodeId, group]) => {
  const sourceNode = nodeMap.value.get(sourceNodeId);
  if (!sourceNode || !canCollapseEdgeGroup(sourceNode, group) || collapsedSourceIds.value.has(sourceNodeId)) return null;
  return {
    sourceNodeId,
    count: group.length,
    x: sourceNode.x + sourceNode.width + 12,
    y: sourceNode.y + getNodeCardHeight(sourceNode) / 2,
  };
}).filter((item): item is { sourceNodeId: number; count: number; x: number; y: number } => !!item));

let panState: { pointerId: number; startX: number; startY: number; originX: number; originY: number } | null = null;
let dragState: { pointerId: number; nodeId: number; startX: number; startY: number; originX: number; originY: number } | null = null;
let resizeState: {
  pointerId: number;
  nodeId: number;
  startX: number;
  startY: number;
  originWidth: number;
  originHeight: number;
} | null = null;
let lastNodePointerDown: { nodeId: number; time: number } | null = null;
let lastNodeClick: { nodeId: number; time: number } | null = null;
let lastTextNodePointerDown: { nodeId: number; time: number } | null = null;
let localCanvasNodeId = -1;

function revokeObjectUrl(url?: string) {
  if (url) URL.revokeObjectURL(url);
}

function revokeLocalNodeObjectUrls() {
  nodes.value.forEach((node) => revokeObjectUrl(node.localObjectUrl));
}

function clampZoom(value: number) {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Number(value.toFixed(3))));
}

function scheduleViewportSave() {
  const projectId = selectedCanvasProjectId.value;
  if (canvasReadOnly.value) return;
  if (!projectId) return;
  if (viewportSaveTimer.value) clearTimeout(viewportSaveTimer.value);
  viewportSaveTimer.value = setTimeout(() => {
    const currentProjectId = selectedCanvasProjectId.value;
    if (!currentProjectId || canvasReadOnly.value) return;
    void updateCanvasViewport(currentProjectId, {
      viewport_x: viewport.value.x,
      viewport_y: viewport.value.y,
      zoom: viewport.value.zoom,
    }).catch(() => {});
  }, 500);
}

function screenToWorld(clientX: number, clientY: number) {
  const rect = canvasStageRef.value?.getBoundingClientRect();
  if (!rect) return { x: 0, y: 0 };
  return {
    x: (clientX - rect.left - viewport.value.x) / viewport.value.zoom,
    y: (clientY - rect.top - viewport.value.y) / viewport.value.zoom,
  };
}

function getViewportCenter() {
  const rect = canvasStageRef.value?.getBoundingClientRect();
  if (!rect) return { x: 0, y: 0 };
  return screenToWorld(rect.left + rect.width / 2, rect.top + rect.height / 2);
}

function nodeRectsOverlap(
  a: { x: number; y: number; width: number; height: number },
  b: { x: number; y: number; width: number; height: number },
  gap = 28
) {
  return !(
    a.x + a.width + gap <= b.x ||
    b.x + b.width + gap <= a.x ||
    a.y + a.height + gap <= b.y ||
    b.y + b.height + gap <= a.y
  );
}

function findNonOverlappingNodePosition(preferred: { x: number; y: number }, size: { width: number; height: number }) {
  const occupiedRects = nodes.value.map((node) => ({
    x: Number(node.x || 0),
    y: Number(node.y || 0),
    width: Number(node.width || DEFAULT_NODE_WIDTH),
    height: getNodeCardHeight(node),
  }));
  const fits = (candidate: { x: number; y: number }) => !occupiedRects.some((rect) => nodeRectsOverlap(
    { ...candidate, ...size },
    rect
  ));
  if (fits(preferred)) return preferred;

  const stepX = Math.max(180, Math.min(420, size.width * 0.65));
  const stepY = Math.max(180, Math.min(420, size.height * 0.65));
  for (let ring = 1; ring <= 18; ring += 1) {
    for (let dx = -ring; dx <= ring; dx += 1) {
      for (let dy = -ring; dy <= ring; dy += 1) {
        if (Math.max(Math.abs(dx), Math.abs(dy)) !== ring) continue;
        const candidate = {
          x: Math.round(preferred.x + dx * stepX),
          y: Math.round(preferred.y + dy * stepY),
        };
        if (fits(candidate)) return candidate;
      }
    }
  }
  return {
    x: Math.round(preferred.x + stepX * 19),
    y: Math.round(preferred.y),
  };
}

function getNodesBounds(sourceNodes = nodes.value) {
  if (!sourceNodes.length) return null;
  return sourceNodes.reduce((bounds, node) => {
    const x = Number(node.x || 0);
    const y = Number(node.y || 0);
    const width = Number(node.width || DEFAULT_NODE_WIDTH);
    const height = getNodeCardHeight(node);
    return {
      minX: Math.min(bounds.minX, x),
      minY: Math.min(bounds.minY, y),
      maxX: Math.max(bounds.maxX, x + width),
      maxY: Math.max(bounds.maxY, y + height),
    };
  }, {
    minX: Number.POSITIVE_INFINITY,
    minY: Number.POSITIVE_INFINITY,
    maxX: Number.NEGATIVE_INFINITY,
    maxY: Number.NEGATIVE_INFINITY,
  });
}

function resetViewport() {
  const rect = canvasStageRef.value?.getBoundingClientRect();
  const bounds = getNodesBounds();
  if (!rect || !bounds) {
    viewport.value = { x: 80, y: 70, zoom: 1 };
    scheduleViewportSave();
    return;
  }

  const boundsWidth = Math.max(1, bounds.maxX - bounds.minX);
  const boundsHeight = Math.max(1, bounds.maxY - bounds.minY);
  const padding = 180;
  const zoom = Math.min(
    1,
    clampZoom(Math.min(
      (rect.width - padding) / boundsWidth,
      (rect.height - padding) / boundsHeight
    ))
  );
  const centerX = bounds.minX + boundsWidth / 2;
  const centerY = bounds.minY + boundsHeight / 2;
  viewport.value = {
    zoom,
    x: rect.width / 2 - centerX * zoom,
    y: rect.height / 2 - centerY * zoom,
  };
  scheduleViewportSave();
}

function zoomAtCenter(delta: number) {
  selectedNodeId.value = null;
  const rect = canvasStageRef.value?.getBoundingClientRect();
  if (!rect) return;
  zoomAt(rect.left + rect.width / 2, rect.top + rect.height / 2, viewport.value.zoom + delta);
}

function zoomAt(clientX: number, clientY: number, nextZoomValue: number) {
  selectedNodeId.value = null;
  const rect = canvasStageRef.value?.getBoundingClientRect();
  if (!rect) return;
  const nextZoom = clampZoom(nextZoomValue);
  const before = screenToWorld(clientX, clientY);
  viewport.value = {
    zoom: nextZoom,
    x: clientX - rect.left - before.x * nextZoom,
    y: clientY - rect.top - before.y * nextZoom,
  };
  scheduleViewportSave();
}

function handleWheel(event: WheelEvent) {
  selectedNodeId.value = null;
  if (event.ctrlKey || event.metaKey || Math.abs(event.deltaY) > Math.abs(event.deltaX)) {
    event.preventDefault();
    const factor = event.deltaY > 0 ? 0.9 : 1.1;
    zoomAt(event.clientX, event.clientY, viewport.value.zoom * factor);
    return;
  }
  viewport.value = {
    ...viewport.value,
    x: viewport.value.x - event.deltaX,
    y: viewport.value.y - event.deltaY,
  };
  scheduleViewportSave();
}

function handleStagePointerDown(event: PointerEvent) {
  if (event.button !== 0) return;
  const target = event.target as HTMLElement;
  if (target.closest(".canvas-node") || target.closest(".canvas-panel")) return;
  selectedNodeId.value = null;
  composerPopover.value = null;
  if (!generatePanelCollapsed.value && !hasComposerDraftContent.value) {
    collapseGeneratePanel();
  }
  panState = {
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    originX: viewport.value.x,
    originY: viewport.value.y,
  };
  canvasStageRef.value?.setPointerCapture(event.pointerId);
}

function handleStagePointerMove(event: PointerEvent) {
  if (panState?.pointerId === event.pointerId) {
    viewport.value = {
      ...viewport.value,
      x: panState.originX + event.clientX - panState.startX,
      y: panState.originY + event.clientY - panState.startY,
    };
    return;
  }
  if (resizeState?.pointerId === event.pointerId) {
    const dx = (event.clientX - resizeState.startX) / viewport.value.zoom;
    const dy = (event.clientY - resizeState.startY) / viewport.value.zoom;
    const targetNode = nodes.value.find((node) => node.id === resizeState?.nodeId);
    if (!targetNode) return;
    let nextWidth = Math.max(160, Math.min(1200, resizeState.originWidth + dx));
    let nextHeight = Math.max(160, Math.min(1600, resizeState.originHeight + dy));
    if (targetNode.node_type !== "text") {
      const ratio = getNodeAspectRatioValue(targetNode);
      if (Math.abs(dx) >= Math.abs(dy)) {
        nextHeight = Math.max(160, Math.min(1600, nextWidth / ratio));
      } else {
        nextWidth = Math.max(160, Math.min(1200, nextHeight * ratio));
      }
    }
    targetNode.width = Math.round(nextWidth);
    targetNode.height = Math.round(nextHeight);
    return;
  }
  if (!dragState || dragState.pointerId !== event.pointerId) return;
  const dx = (event.clientX - dragState.startX) / viewport.value.zoom;
  const dy = (event.clientY - dragState.startY) / viewport.value.zoom;
  const targetNode = nodes.value.find((node) => node.id === dragState?.nodeId);
  if (!targetNode) return;
  targetNode.x = dragState.originX + dx;
  targetNode.y = dragState.originY + dy;
}

function handleStagePointerUp(event: PointerEvent) {
  if (panState?.pointerId === event.pointerId) {
    panState = null;
    scheduleViewportSave();
  }
  if (dragState?.pointerId === event.pointerId) {
    const node = nodes.value.find((item) => item.id === dragState?.nodeId);
    dragState = null;
    const projectId = selectedCanvasProjectId.value;
    if (node && projectId && !canvasReadOnly.value) {
      void updateCanvasNode(projectId, node.id, { x: node.x, y: node.y }).catch(() => {
        message.error("保存节点位置失败");
      });
    }
  }
  if (resizeState?.pointerId === event.pointerId) {
    const node = nodes.value.find((item) => item.id === resizeState?.nodeId);
    resizeState = null;
    const projectId = selectedCanvasProjectId.value;
    if (node && projectId && !canvasReadOnly.value) {
      void updateCanvasNode(projectId, node.id, { width: node.width, height: node.height }).catch(() => {
        message.error("保存节点尺寸失败");
      });
    }
  }
}

function startNodeDrag(event: PointerEvent, node: CanvasNode) {
  if (event.button !== 0) return;
  event.stopPropagation();
  selectedNodeId.value = node.id;
  const now = Date.now();
  if (lastNodePointerDown?.nodeId === node.id && now - lastNodePointerDown.time < 500) {
    lastNodePointerDown = null;
    handleNodeDoubleClick(node);
    return;
  }
  lastNodePointerDown = { nodeId: node.id, time: now };
  if (canvasReadOnly.value) return;
  dragState = {
    pointerId: event.pointerId,
    nodeId: node.id,
    startX: event.clientX,
    startY: event.clientY,
    originX: node.x,
    originY: node.y,
  };
  canvasStageRef.value?.setPointerCapture(event.pointerId);
}

function handleTextNodePointerDown(event: PointerEvent, node: CanvasNode) {
  if (event.button !== 0) return;
  event.stopPropagation();
  selectedNodeId.value = node.id;
  const now = Date.now();
  if (lastTextNodePointerDown?.nodeId === node.id && now - lastTextNodePointerDown.time < 600) {
    lastTextNodePointerDown = null;
    event.preventDefault();
    openTextNodeEditor(node);
    return;
  }
  lastTextNodePointerDown = { nodeId: node.id, time: now };
  if (canvasReadOnly.value) return;
  dragState = {
    pointerId: event.pointerId,
    nodeId: node.id,
    startX: event.clientX,
    startY: event.clientY,
    originX: node.x,
    originY: node.y,
  };
  canvasStageRef.value?.setPointerCapture(event.pointerId);
}

function startNodeResize(event: PointerEvent, node: CanvasNode) {
  if (event.button !== 0) return;
  event.stopPropagation();
  if (canvasReadOnly.value) return;
  selectedNodeId.value = node.id;
  dragState = null;
  resizeState = {
    pointerId: event.pointerId,
    nodeId: node.id,
    startX: event.clientX,
    startY: event.clientY,
    originWidth: Number(node.width || DEFAULT_NODE_WIDTH),
    originHeight: getNodeCardHeight(node),
  };
  canvasStageRef.value?.setPointerCapture(event.pointerId);
}

async function loadSceneConfig() {
  sceneConfigLoading.value = true;
  try {
    taskScenes.value = await getTaskScenes();
  } catch {
    taskScenes.value = [];
    message.error("加载模型配置失败");
  } finally {
    sceneConfigLoading.value = false;
  }
}

async function loadCanvasList(preferredProjectId?: string | null) {
  const res = await listCanvases();
  canvases.value = res.items;
  const preferredCanvas = preferredProjectId ? res.items.find((item) => item.project_id === preferredProjectId) : null;
  if (preferredProjectId && !preferredCanvas) {
    await loadCanvasDetail(preferredProjectId);
    if (selectedCanvas.value) return;
  }
  if (!res.items.length) {
    await handleCreateCanvas(undefined, { silent: true });
    return;
  }
  const nextCanvas = preferredCanvas
    || (selectedCanvasId.value ? res.items.find((item) => item.id === selectedCanvasId.value) : null)
    || res.items[0];
  await selectCanvas(nextCanvas, { replaceRoute: !props.projectId || !preferredCanvas });
}

async function selectCanvas(canvas: UserCanvasSummary, options: { replaceRoute?: boolean } = {}) {
  canvasReadOnlyState.value = canvas.is_readonly === true;
  selectedCanvasId.value = canvas.id;
  const nextPath = `/canvas/${canvas.project_id}`;
  if (options.replaceRoute) {
    await router.replace(nextPath);
  } else if (route.path !== nextPath) {
    await router.push(nextPath);
  }
  await loadCanvasDetail(canvas.project_id);
}

async function handleCanvasSelect(canvas: UserCanvasSummary) {
  if (canvasReadOnly.value) return;
  if (!canvas.project_id || canvas.id === selectedCanvasId.value) return;
  canvasMenuOpen.value = false;
  selectedNodeId.value = null;
  await selectCanvas(canvas);
}

function toggleCanvasMenu() {
  if (canvasReadOnly.value) {
    canvasMenuOpen.value = false;
    return;
  }
  canvasMenuOpen.value = !canvasMenuOpen.value;
}

async function openReadonlyOwnerDialog() {
  if (!canvasReadOnly.value) return;
  const fallback = readonlyCanvasOwnerFallback.value;
  if (!fallback) return;
  selectedReadonlyOwner.value = adminUsers.value.find((user) => user.id === fallback.id) || fallback;
  readonlyOwnerDialogOpen.value = true;
  if (adminUsers.value.length) return;
  try {
    adminUsers.value = await listUsers();
    selectedReadonlyOwner.value = adminUsers.value.find((user) => user.id === fallback.id) || selectedReadonlyOwner.value;
  } catch {
    message.error("获取用户信息失败");
  }
}

function handleDocumentPointerDown(event: PointerEvent) {
  const target = event.target as HTMLElement | null;
  if (target && !target.closest(".canvas-node") && !target.closest(".canvas-node-toolbar")) {
    selectedNodeId.value = null;
  }
  if (canvasSettingsOpen.value && !target?.closest(".canvas-settings")) {
    canvasSettingsOpen.value = false;
  }
  if (uploadMenuOpen.value && !target?.closest(".composer-upload-entry")) {
    uploadMenuOpen.value = false;
  }
  if (freeNodeMenuOpen.value && !target?.closest(".canvas-side-toolbox-wrap")) {
    freeNodeMenuOpen.value = false;
  }
  if (!canvasMenuOpen.value) return;
  if (target && projectSwitcherRef.value?.contains(target)) return;
  canvasMenuOpen.value = false;
}

async function loadCanvasDetail(projectId = selectedCanvasProjectId.value) {
  if (!projectId) return;
  loading.value = true;
  try {
    const detail = await getCanvas(projectId);
    selectedCanvasId.value = detail.id;
    canvasReadOnlyState.value = detail.is_readonly === true;
    if (!canvasReadOnlyState.value) {
      readonlyOwnerDialogOpen.value = false;
      selectedReadonlyOwner.value = null;
    }
    viewport.value = {
      x: Number(detail.viewport_x || 0),
      y: Number(detail.viewport_y || 0),
      zoom: clampZoom(Number(detail.zoom || 1)),
    };
    revokeLocalNodeObjectUrls();
    nodes.value = detail.nodes || [];
    edges.value = detail.edges || [];
    promptSourceNodeId.value = null;
    const detailSummary = { ...detail, node_count: detail.node_count };
    canvases.value = canvases.value.some((item) => item.id === detail.id)
      ? canvases.value.map((item) => item.id === detail.id ? { ...item, ...detailSummary } : item)
      : [detailSummary, ...canvases.value];
    syncTaskPolling();
  } catch {
    message.error("加载画布失败");
  } finally {
    loading.value = false;
  }
}

async function handleCreateCanvas(name?: string, options: { silent?: boolean } = {}) {
  if (creatingCanvas.value) return;
  creatingCanvas.value = true;
  try {
    const canvas = await createCanvas(name);
    canvases.value = [canvas, ...canvases.value];
    if (!options.silent) message.success("画布已创建");
    await selectCanvas(canvas);
  } catch {
    message.error("创建画布失败");
  } finally {
    creatingCanvas.value = false;
  }
}

async function handleCreateCanvasFromMenu() {
  canvasMenuOpen.value = false;
  await handleCreateCanvas();
}

function handleRenameCurrentCanvas() {
  if (!selectedCanvas.value) return;
  if (canvasReadOnly.value) return;
  canvasMenuOpen.value = false;
  handleRenameCanvas(selectedCanvas.value);
}

function expandGeneratePanel() {
  panState = null;
  dragState = null;
  resizeState = null;
  generatePanelCollapsed.value = false;
}

function collapseGeneratePanel() {
  composerPopover.value = null;
  generatePanelCollapsed.value = true;
}

function toggleComposerPopover(target: ComposerPopover) {
  composerPopover.value = composerPopover.value === target ? null : target;
}

function switchCanvasMode(mode: CanvasMode) {
  if (canvasMode.value === mode) return;
  composerModeSwitching.value = true;
  canvasMode.value = mode;
  composerPopover.value = null;
  window.setTimeout(() => {
    composerModeSwitching.value = false;
  }, 0);
}

function setCanvasBackgroundMode(mode: CanvasBackgroundMode) {
  canvasBackgroundMode.value = mode;
}

function handleRenameCanvas(canvas: UserCanvasSummary) {
  let nextName = canvas.name;
  Modal.confirm({
    title: "重命名画布",
    wrapClassName: "canvas-rename-modal-wrap",
    centered: true,
    content: () => h("input", {
      class: "ant-input canvas-rename-input",
      value: nextName,
      maxlength: 100,
      placeholder: "请输入画布名称",
      onInput: (event: Event) => {
        nextName = (event.target as HTMLInputElement).value;
      },
    }),
    okText: "保存",
    cancelText: "取消",
    async onOk() {
      const normalized = nextName.trim();
      if (!normalized) {
        message.warning("画布名称不能为空");
        return Promise.reject();
      }
      const updated = await updateCanvas(canvas.project_id, { name: normalized });
      canvases.value = canvases.value.map((item) => item.id === updated.id ? updated : item);
      message.success("画布已重命名");
    },
  });
}

function triggerReferenceUpload() {
  uploadMenuOpen.value = false;
  canvasReferenceSelectMode.value = false;
  referenceInputRef.value?.click();
}

function toggleReferenceUploadMenu(anchor: UploadMenuAnchor) {
  if (!referenceSlotsRemaining.value) {
    message.warning(`当前模型最多支持 ${maxReferenceImages.value} 张参考图`);
    return;
  }
  uploadMenuOpen.value = uploadMenuAnchor.value === anchor ? !uploadMenuOpen.value : true;
  uploadMenuAnchor.value = anchor;
}

function openCanvasReferencePicker() {
  uploadMenuOpen.value = false;
  if (!referenceSlotsRemaining.value) {
    message.warning(`当前模型最多支持 ${maxReferenceImages.value} 张参考图`);
    return;
  }
  if (!canvasReferenceOptions.value.length) {
    message.info("当前画布暂无可选择的图片");
    return;
  }
  selectedNodeId.value = null;
  canvasReferenceSelectMode.value = true;
}

function addCanvasReference(option: CanvasReferenceOption) {
  if (!referenceSlotsRemaining.value) {
    message.warning(`当前模型最多支持 ${maxReferenceImages.value} 张参考图`);
    canvasReferenceSelectMode.value = false;
    return;
  }
  if (referenceItems.value.some((item) => item.remoteUrl === option.imageUrl)) {
    message.info("这张图片已在参考图中");
    return;
  }
  referenceItems.value = [...referenceItems.value, {
    id: `canvas-${option.id}-${Date.now()}`,
    localUrl: option.displayUrl,
    remoteUrl: option.imageUrl,
    status: "success",
      sourceNodeId: option.sourceNodeId,
  }];
  if (referenceSlotsRemaining.value <= 0) {
    canvasReferenceSelectMode.value = false;
    message.info(`已达到当前模型参考图上限：${maxReferenceImages.value} 张`);
  }
}

function getNodeReferenceOption(node: CanvasNode): CanvasReferenceOption | null {
  if (node.node_type === "image" && node.image_url) {
    return {
      id: `${node.id}-free-image`,
      imageUrl: node.image_url,
      displayUrl: node.image_url,
      sourceNodeId: node.id,
    };
  }
  const task = node.task;
  if (!task || task.status !== "success") return null;
  const image = (task.images || []).find((item) => item.status === "success" && (item.image_url || item.preview_url || item.thumb_url));
  if (!image) return null;
  return {
    id: `${node.id}-${image.id || 0}`,
    imageUrl: image.image_url || image.preview_url || image.thumb_url || "",
    displayUrl: getDisplayImageUrl(image),
    sourceNodeId: node.id,
  };
}

function isCanvasReferenceSelected(node: CanvasNode) {
  const option = getNodeReferenceOption(node);
  return !!option && referenceItems.value.some((item) => item.remoteUrl === option.imageUrl);
}

function removeCanvasReference(option: CanvasReferenceOption) {
  referenceItems.value = referenceItems.value.filter((item) => item.remoteUrl !== option.imageUrl);
}

function selectCanvasNodeAsReference(node: CanvasNode) {
  const option = getNodeReferenceOption(node);
  if (!option) return;
  if (isCanvasReferenceSelected(node)) {
    removeCanvasReference(option);
    return;
  }
  addCanvasReference(option);
}

async function handleReferenceChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  input.value = "";
  await processReferenceFiles(files);
}

function isReferenceImageFile(file: File) {
  if (file.type.startsWith("image/")) return true;
  return /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(file.name);
}

async function processReferenceFiles(files: File[]) {
  const imageFiles = files.filter(isReferenceImageFile);
  if (!imageFiles.length) {
    if (files.length) message.warning("请上传图片文件");
    return;
  }
  const acceptedFiles = imageFiles.slice(0, referenceSlotsRemaining.value);
  if (!acceptedFiles.length) {
    message.warning(`当前模型最多上传 ${maxReferenceImages.value} 张参考图`);
    return;
  }
  if (acceptedFiles.length < imageFiles.length) {
    message.warning(`当前模型最多支持 ${maxReferenceImages.value} 张参考图，已自动截断`);
  }
  await Promise.all(acceptedFiles.map(uploadReference));
}

function handleReferenceDragEnter(event: DragEvent) {
  event.preventDefault();
  referenceDragCounter.value += 1;
  referenceDragActive.value = true;
}

function handleReferenceDragOver(event: DragEvent) {
  event.preventDefault();
}

function handleReferenceDragLeave() {
  referenceDragCounter.value = Math.max(0, referenceDragCounter.value - 1);
  if (referenceDragCounter.value === 0) {
    referenceDragActive.value = false;
  }
}

async function handleReferenceDrop(event: DragEvent) {
  referenceDragCounter.value = 0;
  referenceDragActive.value = false;
  const files = Array.from(event.dataTransfer?.files || []);
  await processReferenceFiles(files);
}

async function uploadReference(file: File) {
  const objectUrl = URL.createObjectURL(file);
  const item: ReferenceItem = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    localUrl: objectUrl,
    remoteUrl: "",
    status: "uploading",
    objectUrl,
  };
  referenceItems.value = [...referenceItems.value, item];
  try {
    const res = await uploadReferenceImage(file, "ref");
    revokeObjectUrl(objectUrl);
    referenceItems.value = referenceItems.value.map((current) => current.id === item.id ? {
      ...current,
      localUrl: res.url,
      remoteUrl: res.url,
      status: "success",
      objectUrl: undefined,
    } : current);
  } catch {
    referenceItems.value = referenceItems.value.map((current) => current.id === item.id ? { ...current, status: "failed" } : current);
    message.error(`${file.name} 上传失败`);
  }
}

function removeReference(item: ReferenceItem) {
  revokeObjectUrl(item.objectUrl);
  referenceItems.value = referenceItems.value.filter((current) => current.id !== item.id);
}

function resolveTaskType(task?: TaskResult | null) {
  if (!task) return "text_generate" as const;
  if (task.mode === "inpaint") return "inpaint" as const;
  const scene = taskScenes.value.find((item) => item.scene_key === task.model);
  return scene?.scene_type === "image_edit" ? "image_edit" as const : "text_generate" as const;
}

function convertNodeToHistoryCard(node: CanvasNode): UserHistoryCard | null {
  const task = node.task;
  if (!task) return null;
  const primaryImage = task.images?.[0];
  return {
    item_type: "task",
    task_id: task.id,
    image_id: primaryImage?.id ?? null,
    display_id: task.id,
    is_pinned: false,
    image_url: primaryImage?.image_url || "",
    preview_url: primaryImage?.preview_url || "",
    thumb_url: primaryImage?.thumb_url || "",
    status: task.status,
    image_format: primaryImage?.image_format || "",
    image_size_bytes: primaryImage?.image_size_bytes || 0,
    task_type: resolveTaskType(task),
    model: task.model,
    source: task.source,
    mode: task.mode,
    prompt: task.prompt,
    reference_images: task.reference_images || [],
    reference_image_thumbs: task.reference_image_thumbs || [],
    source_image: task.source_image || "",
    source_image_thumb: task.source_image_thumb || "",
    mask_image: task.mask_image || "",
    mask_image_thumb: task.mask_image_thumb || "",
    num_images: task.num_images,
    size: task.size,
    resolution: task.resolution,
    custom_size: task.custom_size,
    credit_cost: task.credit_cost,
    credit_refunded: Boolean(task.credit_refunded),
    created_at: task.created_at,
    error_message: task.error_message || primaryImage?.error_message || "",
    images: task.images || [],
  };
}

function selectNode(node: CanvasNode) {
  selectedNodeId.value = node.id;
}

function handleNodeClick(event: MouseEvent, node: CanvasNode) {
  const now = Date.now();
  if (event.detail >= 2 || (lastNodeClick?.nodeId === node.id && now - lastNodeClick.time < 500)) {
    lastNodeClick = null;
    handleNodeDoubleClick(node);
    return;
  }
  lastNodeClick = { nodeId: node.id, time: now };
  selectNode(node);
}

function openNodeDetail(node: CanvasNode) {
  const item = convertNodeToHistoryCard(node);
  if (!item) {
    message.warning("当前任务暂无详情");
    return;
  }
  detailItem.value = item;
  detailOpen.value = true;
}

function openNodeFeedback(node: CanvasNode) {
  if (!node.task?.id) {
    message.warning("当前任务暂不支持反馈");
    return;
  }
  feedbackTarget.value = node.task;
  feedbackDialogOpen.value = true;
}

function openCanvasFeedback() {
  canvasFeedbackOpen.value = true;
}

function refillGenerateConfigFromNode(node: CanvasNode) {
  const task = node.task;
  if (!task) {
    message.warning("当前任务暂无可回填参数");
    return;
  }
  generatePanelCollapsed.value = false;
  canvasMode.value = (task.reference_images || []).length ? "imageEdit" : "textGenerate";
  selectedModel.value = task.model || selectedModel.value;
  prompt.value = task.prompt || "";
  numImages.value = Math.min(8, Math.max(1, Number(task.num_images || 1)));
  size.value = task.size || size.value;
  resolution.value = task.resolution || resolution.value;
  customSize.value = task.custom_size || "";
  promptSourceNodeId.value = null;
  referenceItems.value.forEach((item) => revokeObjectUrl(item.objectUrl));
  referenceItems.value = (task.reference_images || []).map((url, index) => ({
    id: `refill-${node.id}-${index}`,
    localUrl: (task.reference_image_thumbs || [])[index] || url,
    remoteUrl: url,
    status: "success" as const,
  }));
  selectedNodeId.value = null;
  message.success("已回填到生图配置");
}

function useFreeNodeForGeneration(node: CanvasNode) {
  generatePanelCollapsed.value = false;
  selectedNodeId.value = null;
  if (node.node_type === "text") {
    canvasMode.value = "textGenerate";
    prompt.value = node.content || "";
    promptSourceNodeId.value = node.id;
    message.success("已回填文本到提示词");
    return;
  }
  if (node.node_type === "image" && node.image_url) {
    canvasMode.value = "imageEdit";
    const beforeCount = referenceItems.value.length;
    addCanvasReference({
      id: `${node.id}-free-image`,
      imageUrl: node.image_url,
      displayUrl: node.image_url,
    });
    if (referenceItems.value.length > beforeCount) {
      message.success("已添加为参考图");
    }
  }
}

function useNodeImageForEditing(node: CanvasNode) {
  const option = getNodeReferenceOption(node);
  if (!option) {
    message.warning("当前节点暂无可编辑图片");
    return;
  }
  generatePanelCollapsed.value = false;
  selectedNodeId.value = null;
  canvasMode.value = "imageEdit";
  const beforeCount = referenceItems.value.length;
  addCanvasReference(option);
  if (referenceItems.value.length > beforeCount) {
    message.success("已添加为参考图");
  }
}

function openTextNodeEditor(node: CanvasNode) {
  if (node.node_type !== "text") return;
  if (canvasReadOnly.value) {
    message.warning("只读模式下不能编辑文本节点");
    return;
  }
  textNodeEditTarget.value = node;
  textNodeEditContent.value = node.content || "";
  focusCanvasNode(node, 1);
  void nextTick(() => {
    const editor = canvasStageRef.value?.querySelector<HTMLTextAreaElement>(`[data-text-node-editor="${node.id}"]`);
    editor?.focus();
    editor?.select();
  });
}

async function saveTextNodeContent() {
  const node = textNodeEditTarget.value;
  const projectId = selectedCanvasProjectId.value;
  if (!node || !projectId) return;
  if (canvasReadOnly.value) {
    message.warning("只读模式下不能保存文本节点");
    textNodeEditTarget.value = null;
    return;
  }
  const nextContent = textNodeEditContent.value;
  if (nextContent === (node.content || "")) {
    textNodeEditTarget.value = null;
    return;
  }
  textNodeEditSaving.value = true;
  try {
    const updated = await updateCanvasNode(projectId, node.id, { content: nextContent });
    nodes.value = nodes.value.map((item) => item.id === updated.id ? updated : item);
    selectedNodeId.value = updated.id;
    textNodeEditTarget.value = null;
    message.success("文本节点已更新");
  } catch (err: any) {
    message.error(err.response?.data?.detail || "更新文本节点失败");
  } finally {
    textNodeEditSaving.value = false;
  }
}

function cancelTextNodeEdit() {
  textNodeEditTarget.value = null;
  textNodeEditContent.value = "";
}

function handleTextNodeEditorKeydown(event: KeyboardEvent) {
  if (event.key === "Escape") {
    event.preventDefault();
    cancelTextNodeEdit();
    return;
  }
  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
    event.preventDefault();
    void saveTextNodeContent();
  }
}

function deleteNode(node: CanvasNode) {
  if (canvasReadOnly.value) {
    message.warning("只读模式下不能删除节点");
    return;
  }
  const localNode = node as CanvasWorkbenchNode;
  if (localNode.localObjectUrl || node.id < 0) {
    revokeObjectUrl(localNode.localObjectUrl);
    nodes.value = nodes.value.filter((item) => item.id !== node.id);
    edges.value = edges.value.filter((edge) => edge.source_node_id !== node.id && edge.target_node_id !== node.id);
    if (selectedNodeId.value === node.id) selectedNodeId.value = null;
    message.success("删除成功");
    return;
  }
  if (!node.task_id) {
    const projectId = selectedCanvasProjectId.value;
    if (!projectId) return;
    Modal.confirm({
      title: "删除节点",
      content: "删除后会从画布移除该自由节点。",
      okText: "删除",
      cancelText: "取消",
      okButtonProps: { danger: true },
      async onOk() {
        await deleteCanvasNode(projectId, node.id);
        nodes.value = nodes.value.filter((item) => item.id !== node.id);
        edges.value = edges.value.filter((edge) => edge.source_node_id !== node.id && edge.target_node_id !== node.id);
        if (selectedNodeId.value === node.id) selectedNodeId.value = null;
        canvases.value = canvases.value.map((item) => item.id === selectedCanvasId.value ? {
          ...item,
          node_count: Math.max(0, item.node_count - 1),
        } : item);
        message.success("删除成功");
      },
    });
    return;
  }
  Modal.confirm({
    title: "删除任务",
    content: "删除后会从画布移除该任务及生成结果。",
    okText: "删除",
    cancelText: "取消",
    okButtonProps: { danger: true },
    async onOk() {
      await deleteHistoryTask(node.task_id);
      nodes.value = nodes.value.filter((item) => item.id !== node.id);
      edges.value = edges.value.filter((edge) => edge.source_node_id !== node.id && edge.target_node_id !== node.id);
      if (selectedNodeId.value === node.id) selectedNodeId.value = null;
      canvases.value = canvases.value.map((item) => item.id === selectedCanvasId.value ? {
        ...item,
        node_count: Math.max(0, item.node_count - 1),
      } : item);
      message.success("删除成功");
    },
  });
}

async function handleGenerate() {
  if (canvasReadOnly.value) {
    message.warning("只读模式下不能提交生成任务");
    return;
  }
  if (!auth.isLoggedIn) {
    message.warning("请先登录");
    return;
  }
  const projectId = selectedCanvasProjectId.value;
  if (!projectId) return;
  if (textGenerateBlockedByReferences.value) {
    message.warning("当前存在参考图，请切回图编辑后再生成");
    return;
  }
  if (!canGenerate.value) return;
  if (isImageEditMode.value && referenceItems.value.some((item) => item.status === "uploading")) {
    message.warning("参考图仍在上传中，请稍候");
    return;
  }
  if (isImageEditMode.value && referenceItems.value.some((item) => item.status === "failed")) {
    message.warning("请先移除上传失败的参考图");
    return;
  }
  if (!auth.isSuperAdmin && userCredits.value < generationCreditCost.value) {
    showInsufficientCreditsPurchase(`积分不足，需要 ${generationCreditCost.value} 积分，当前余额 ${userCredits.value}`);
    return;
  }
  const center = getViewportCenter();
  const taskGroupCount = Math.max(1, Number(numImages.value || 1));
  const taskGroupWidth = DEFAULT_NODE_WIDTH + (taskGroupCount - 1) * 360;
  const taskGroupHeight = DEFAULT_NODE_HEIGHT;
  const taskPosition = findNonOverlappingNodePosition(
    { x: center.x - taskGroupWidth / 2, y: center.y - taskGroupHeight / 2 },
    { width: taskGroupWidth, height: taskGroupHeight }
  );
  const sourceNodeIds = Array.from(new Set([
    ...referenceItems.value.map((item) => item.sourceNodeId).filter((id): id is number => typeof id === "number"),
    ...(promptSourceNodeId.value ? [promptSourceNodeId.value] : []),
  ]));
  generating.value = true;
  try {
    const res = await createCanvasTask(projectId, {
      mode: "generate",
      model: selectedModel.value,
      prompt: prompt.value,
      num_images: numImages.value,
      size: size.value,
      resolution: resolution.value,
      custom_size: customSize.value,
      reference_images: isImageEditMode.value ? referenceItems.value.map((item) => item.remoteUrl).filter(Boolean) : [],
      source_node_ids: sourceNodeIds,
      x: taskPosition.x,
      y: taskPosition.y,
      width: DEFAULT_NODE_WIDTH,
      height: DEFAULT_NODE_HEIGHT,
    });
    nodes.value = [...nodes.value, ...res.nodes];
    if (res.nodes.length) {
      focusCanvasNodesAtCurrentZoom(res.nodes);
    }
    prompt.value = "";
    promptSourceNodeId.value = null;
    getCanvas(projectId).then((detail) => {
      if (detail.project_id !== selectedCanvasProjectId.value) return;
      nodes.value = detail.nodes || nodes.value;
      edges.value = detail.edges || [];
    }).catch(() => {});
    if (res.nodes.length) {
      canvases.value = canvases.value.map((item) => item.id === selectedCanvasId.value ? { ...item, node_count: item.node_count + res.nodes.length } : item);
    }
    message.success("任务已提交到画布");
    syncTaskPolling();
    getMe().then((user) => auth.updateUser(user)).catch(() => {});
  } catch (err: any) {
    const detail = err.response?.data?.detail || "";
    if (isInsufficientCreditsError(err)) {
      showInsufficientCreditsPurchase(detail);
      return;
    }
    message.error(err.response?.data?.detail || "提交任务失败");
  } finally {
    generating.value = false;
  }
}

async function refreshActiveTasks() {
  const taskIds = activeTaskIds.value;
  if (!taskIds.length) {
    stopTaskPolling();
    return;
  }
  if (pollingInFlight.value) return;
  pollingInFlight.value = true;
  try {
    if (canvasReadOnly.value) {
      const projectId = selectedCanvasProjectId.value;
      if (!projectId) return;
      const detail = await getCanvas(projectId);
      if (detail.project_id !== selectedCanvasProjectId.value) return;
      canvasReadOnlyState.value = detail.is_readonly === true;
      nodes.value = detail.nodes || [];
      edges.value = detail.edges || [];
      const detailSummary = { ...detail, node_count: detail.node_count };
      canvases.value = canvases.value.some((item) => item.id === detail.id)
        ? canvases.value.map((item) => item.id === detail.id ? { ...item, ...detailSummary } : item)
        : [detailSummary, ...canvases.value];
      return;
    }
    const tasks = await getTasks(taskIds);
    const taskMap = new Map(tasks.map((task) => [task.id, task]));
    nodes.value = nodes.value.map((node) => {
      const task = node.task_id ? taskMap.get(node.task_id) : null;
      return task ? { ...node, task } : node;
    });
  } catch {
    // Keep visible nodes; the next poll can recover.
  } finally {
    pollingInFlight.value = false;
    syncTaskPolling();
  }
}

function stopTaskPolling() {
  if (!taskPollTimer.value) return;
  clearInterval(taskPollTimer.value);
  taskPollTimer.value = null;
}

function syncTaskPolling() {
  if (!activeTaskIds.value.length) {
    stopTaskPolling();
    return;
  }
  if (taskPollTimer.value) return;
  taskPollTimer.value = setInterval(() => {
    void refreshActiveTasks();
  }, 5000);
}

function openPreview(node: CanvasNode) {
  if (node.node_type === "image" && getNodeImageUrl(node)) {
    previewCurrent.value = getNodeImageUrl(node);
    previewVisible.value = true;
    return;
  }
  const image = node.task?.images?.find((item) => item.status === "success") || node.task?.images?.[0];
  const url = getPreviewImageUrl(image);
  if (!url) return;
  previewCurrent.value = url;
  previewVisible.value = true;
}

function handleNodeDoubleClick(node: CanvasNode) {
  if (node.node_type === "text") {
    openTextNodeEditor(node);
    return;
  }
  selectedNodeId.value = node.id;
  focusCanvasNode(node, 1.5);
}

function downloadNode(node: CanvasNode) {
  const image = node.task?.images?.find((item) => item.status === "success");
  if (!image) return;
  const a = document.createElement("a");
  a.href = getDownloadUrl(image.id, image.image_url, image.preview_url);
  a.download = `banana_${image.id}.png`;
  a.click();
}

function handleDetailDownload(item: UserHistoryCard) {
  const image = item.images.find((img) => img.status === "success") || item.images[0];
  if (!image) return;
  const a = document.createElement("a");
  a.href = getDownloadUrl(image.id, image.image_url, image.preview_url);
  a.download = `banana_${image.id}.png`;
  a.click();
}

function goCanvasList() {
  router.push({ path: "/canvas", query: { fromWorkbench: "1" } });
}

function handleCanvasSideTool(action: "freeNode" | "searchNode" | "historyTasks") {
  if (action === "freeNode") {
    if (canvasReadOnly.value) {
      message.warning("只读模式下不能创建自由节点");
      return;
    }
    freeNodeMenuOpen.value = !freeNodeMenuOpen.value;
    return;
  }
  if (action === "searchNode") {
    nodeSearchOpen.value = true;
    nodeSearchKeyword.value = nodeSearchQuery.value;
    return;
  }
  const labels = {
    freeNode: "自由节点",
    searchNode: "搜索节点",
    historyTasks: "历史任务",
  };
  message.info(`${labels[action]}功能即将开放`);
}

async function arrangeCanvasNodes() {
  const projectId = selectedCanvasProjectId.value;
  if (!projectId || !nodes.value.length) return;
  if (canvasReadOnly.value) {
    message.warning("只读模式下不能整理并保存节点");
    return;
  }
  Modal.confirm({
    title: "确认一键整理？",
    content: "一键整理会重新排列并重组当前画布已有布局，确认后将保存新的节点位置。",
    okText: "确认整理",
    cancelText: "取消",
    centered: true,
    async onOk() {
      await executeArrangeCanvasNodes(projectId);
    },
  });
}

async function executeArrangeCanvasNodes(projectId: string) {
  const nodeById = new Map(nodes.value.map((node) => [node.id, node]));
  const adjacency = new Map<number, Set<number>>();
  const incomingCounts = new Map<number, number>();
  const outgoingCounts = new Map<number, number>();
  edges.value.forEach((edge) => {
    if (!nodeById.has(edge.source_node_id) || !nodeById.has(edge.target_node_id)) return;
    if (!adjacency.has(edge.source_node_id)) adjacency.set(edge.source_node_id, new Set());
    if (!adjacency.has(edge.target_node_id)) adjacency.set(edge.target_node_id, new Set());
    adjacency.get(edge.source_node_id)?.add(edge.target_node_id);
    adjacency.get(edge.target_node_id)?.add(edge.source_node_id);
    outgoingCounts.set(edge.source_node_id, (outgoingCounts.get(edge.source_node_id) || 0) + 1);
    incomingCounts.set(edge.target_node_id, (incomingCounts.get(edge.target_node_id) || 0) + 1);
  });

  const visited = new Set<number>();
  const relatedGroups: CanvasNode[][] = [];
  nodes.value.forEach((node) => {
    if (visited.has(node.id) || !adjacency.has(node.id)) return;
    const queue = [node.id];
    const componentIds: number[] = [];
    visited.add(node.id);
    while (queue.length) {
      const currentId = queue.shift()!;
      componentIds.push(currentId);
      adjacency.get(currentId)?.forEach((nextId) => {
        if (visited.has(nextId)) return;
        visited.add(nextId);
        queue.push(nextId);
      });
    }
    if (componentIds.length <= 1) return;
    relatedGroups.push(componentIds
      .map((id) => nodeById.get(id))
      .filter((item): item is CanvasWorkbenchNode => !!item)
      .sort((a, b) => {
        const aScore = (outgoingCounts.get(a.id) || 0) - (incomingCounts.get(a.id) || 0);
        const bScore = (outgoingCounts.get(b.id) || 0) - (incomingCounts.get(b.id) || 0);
        if (aScore !== bScore) return bScore - aScore;
        return Number(a.z_index || 0) - Number(b.z_index || 0);
      }));
  });

  const relatedNodeIds = new Set(relatedGroups.flatMap((group) => group.map((node) => node.id)));
  const standaloneNodes = nodes.value.filter((node) => !relatedNodeIds.has(node.id));
  const groups = [
    ...relatedGroups,
    standaloneNodes.filter((node) => node.node_type === "text"),
    standaloneNodes.filter((node) => node.node_type === "image"),
    standaloneNodes.filter((node) => !node.node_type || node.node_type === "task"),
  ];
  const visibleGroups = groups.filter((group) => group.length);
  if (!visibleGroups.length) return;

  const rowWidths = visibleGroups.map((group) => group.reduce((total, node, index) => (
    total + Number(node.width || DEFAULT_NODE_WIDTH) + (index > 0 ? CANVAS_ARRANGE_COLUMN_GAP : 0)
  ), 0));
  const rowHeights = visibleGroups.map((group) => Math.max(...group.map((node) => getNodeCardHeight(node))));
  const maxWidth = Math.max(...rowWidths);
  const totalHeight = rowHeights.reduce((total, height) => total + height, 0) + CANVAS_ARRANGE_ROW_GAP * Math.max(0, visibleGroups.length - 1);
  const center = getViewportCenter();
  const startX = center.x - maxWidth / 2;
  const startY = center.y - totalHeight / 2;

  const nextPositions = new Map<number, Pick<CanvasNode, "x" | "y" | "z_index">>();
  let currentY = startY;
  let nextZIndex = 1;
  visibleGroups.forEach((group, rowIndex) => {
    let currentX = startX;
    group.forEach((node) => {
      nextPositions.set(node.id, {
        x: Math.round(currentX),
        y: Math.round(currentY),
        z_index: nextZIndex,
      });
      currentX += Number(node.width || DEFAULT_NODE_WIDTH) + CANVAS_ARRANGE_COLUMN_GAP;
      nextZIndex += 1;
    });
    currentY += rowHeights[rowIndex] + CANVAS_ARRANGE_ROW_GAP;
  });

  nodes.value = nodes.value.map((node) => {
    const position = nextPositions.get(node.id);
    return position ? { ...node, ...position } : node;
  });
  selectedNodeId.value = null;

  try {
    const updates = Array.from(nextPositions.entries()).map(([id, position]) => ({ id, ...position }));
    const res = await updateCanvasNodesBatch(projectId, updates);
    nodes.value = nodes.value.map((node) => res.nodes.find((item) => item.id === node.id) || node);
    message.success(relatedGroups.length ? "画布节点已按关系整理" : "画布节点已按类型整理");
  } catch {
    message.warning("节点位置保存失败，请稍后重试");
  }
}

async function createFreeTextNode() {
  const projectId = selectedCanvasProjectId.value;
  if (!projectId) return;
  if (canvasReadOnly.value) {
    message.warning("只读模式下不能创建自由节点");
    return;
  }
  freeNodeMenuOpen.value = false;
  const center = getViewportCenter();
  const nodeSize = { width: 280, height: 160 };
  const position = findNonOverlappingNodePosition(
    { x: center.x - nodeSize.width / 2, y: center.y - nodeSize.height / 2 },
    nodeSize
  );
  try {
    const node = await createCanvasNode(projectId, {
      node_type: "text",
      content: "双击编辑文本",
      x: position.x,
      y: position.y,
      width: nodeSize.width,
      height: nodeSize.height,
    });
    nodes.value = [...nodes.value, node];
    focusCanvasNode(node);
    canvases.value = canvases.value.map((item) => item.id === selectedCanvasId.value ? { ...item, node_count: item.node_count + 1 } : item);
  } catch (err: any) {
    message.error(err.response?.data?.detail || "创建文本节点失败");
  }
}

function triggerFreeImageUpload() {
  if (canvasReadOnly.value) {
    message.warning("只读模式下不能上传图片节点");
    return;
  }
  freeNodeMenuOpen.value = false;
  freeNodeImageInputRef.value?.click();
}

function readImageDimensions(file: File): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const objectUrl = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      const dimensions = { width: image.naturalWidth || 1, height: image.naturalHeight || 1 };
      URL.revokeObjectURL(objectUrl);
      resolve(dimensions);
    };
    image.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      reject(new Error("读取图片尺寸失败"));
    };
    image.src = objectUrl;
  });
}

async function handleFreeImageUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  input.value = "";
  if (canvasReadOnly.value) {
    message.warning("只读模式下不能上传图片节点");
    return;
  }
  if (!files.length) return;
  const imageFiles = files.filter(isReferenceImageFile);
  if (!imageFiles.length) {
    message.warning("请上传图片文件");
    return;
  }
  if (imageFiles.length < files.length) {
    message.warning("已跳过非图片文件");
  }
  const projectId = selectedCanvasProjectId.value;
  if (!projectId) return;
  const center = getViewportCenter();
  const nodeWidth = 320;
  const nodeGap = 34;
  const columns = Math.min(4, imageFiles.length);
  try {
    const items = await Promise.all(imageFiles.map(async (file) => {
      const dimensions = await readImageDimensions(file);
      return {
        file,
        width: nodeWidth,
        height: Math.min(1600, Math.max(120, Math.round((nodeWidth * dimensions.height) / dimensions.width))),
      };
    }));
    const rowHeights = items.reduce<number[]>((rows, item, index) => {
      const row = Math.floor(index / columns);
      rows[row] = Math.max(rows[row] || 0, item.height);
      return rows;
    }, []);
    const totalWidth = columns * nodeWidth + (columns - 1) * nodeGap;
    const totalHeight = rowHeights.reduce((sum, height) => sum + height, 0) + Math.max(0, rowHeights.length - 1) * nodeGap;
    const rowTopOffsets = rowHeights.reduce<number[]>((offsets, height, index) => {
      offsets[index] = index === 0 ? 0 : offsets[index - 1] + rowHeights[index - 1] + nodeGap;
      return offsets;
    }, []);
    const groupPosition = findNonOverlappingNodePosition(
      { x: center.x - totalWidth / 2, y: center.y - totalHeight / 2 },
      { width: totalWidth, height: totalHeight }
    );
    const pendingNodes: CanvasWorkbenchNode[] = items.map((item, index) => {
      const row = Math.floor(index / columns);
      const column = index % columns;
      return {
        id: localCanvasNodeId--,
        canvas_id: selectedCanvasId.value || 0,
        task_id: "",
        node_type: "image",
        content: "",
        image_url: "",
        x: groupPosition.x + column * (nodeWidth + nodeGap),
        y: groupPosition.y + rowTopOffsets[row] + (rowHeights[row] - item.height) / 2,
        width: item.width,
        height: item.height,
        z_index: Math.max(1, ...nodes.value.map((node) => Number(node.z_index || 0))) + index + 1,
        uploadStatus: "uploading",
        localObjectUrl: URL.createObjectURL(item.file),
      };
    });
    nodes.value = [...nodes.value, ...pendingNodes];
    focusCanvasNode(pendingNodes[0]);

    let successCount = 0;
    let failedCount = 0;
    for (const [index, item] of items.entries()) {
      const pendingNode = pendingNodes[index];
      try {
        const uploaded = await uploadReferenceImage(item.file, "misc");
        const node = await createCanvasNode(projectId, {
          node_type: "image",
          image_url: uploaded.url,
          x: pendingNode.x,
          y: pendingNode.y,
          width: item.width,
          height: item.height,
        });
        const stillVisible = nodes.value.some((current) => current.id === pendingNode.id);
        if (!stillVisible) {
          void deleteCanvasNode(projectId, node.id).catch(() => {});
          revokeObjectUrl(pendingNode.localObjectUrl);
          continue;
        }
        revokeObjectUrl(pendingNode.localObjectUrl);
        nodes.value = nodes.value.map((current) => current.id === pendingNode.id ? node : current);
        if (selectedNodeId.value === pendingNode.id) selectedNodeId.value = node.id;
        successCount += 1;
      } catch (err: any) {
        failedCount += 1;
        nodes.value = nodes.value.map((current) => current.id === pendingNode.id ? {
          ...current,
          uploadStatus: "failed",
          uploadError: err.response?.data?.detail || "上传失败",
        } : current);
      }
    }
    if (successCount) {
      canvases.value = canvases.value.map((item) => item.id === selectedCanvasId.value ? { ...item, node_count: item.node_count + successCount } : item);
      message.success(successCount > 1 ? `已上传 ${successCount} 张图片节点` : "图片节点已上传");
    }
    if (failedCount) {
      message.warning(`${failedCount} 张图片上传失败`);
    }
  } catch (err: any) {
    message.error(err.response?.data?.detail || "上传图片节点失败");
  }
}

function submitNodeSearch() {
  nodeSearchQuery.value = nodeSearchKeyword.value.trim();
}

function getNodeSearchText(node: CanvasNode) {
  const task = node.task;
  return [
    node.id,
    node.node_type,
    node.content,
    node.image_url,
    node.task_id,
    task?.id,
    task?.prompt,
    task?.model,
    task?.status,
    task?.size,
    task?.resolution,
  ].filter(Boolean).join(" ").toLowerCase();
}

function isNodeTaskDeleted(node: CanvasNode) {
  const task = node.task as (TaskResult & { task_is_deleted?: boolean; is_deleted?: boolean; is_soft_deleted?: boolean }) | undefined;
  if (!task) return false;
  if (task.task_is_deleted || task.is_deleted || task.is_soft_deleted) return true;
  return (task.images || []).every((image) => image.is_deleted);
}

function getNodeSearchTitle(node: CanvasNode) {
  if (node.node_type === "text") return node.content || "文本节点";
  if (node.node_type === "image") return "上传图片节点";
  const promptText = node.task?.prompt?.trim();
  return promptText || `任务 ${node.task_id || node.id}`;
}

function getNodeSearchMeta(node: CanvasNode) {
  if (node.node_type === "text") return "自由节点 · 文本";
  if (node.node_type === "image") return "自由节点 · 图片";
  const task = node.task;
  return [
    getNodeStatusText(node),
    task?.model,
    task?.size,
    task?.resolution,
  ].filter(Boolean).join(" · ");
}

function getNodeSearchThumbUrl(node: CanvasNode) {
  if (node.node_type === "image") return getNodeImageUrl(node);
  const image = node.task?.images?.find((item) => item.status === "success") || node.task?.images?.[0];
  return getDisplayImageUrl(image);
}

function focusCanvasNode(node: CanvasNode, targetZoom = 1) {
  const rect = canvasStageRef.value?.getBoundingClientRect();
  if (!rect) return;
  const zoom = clampZoom(targetZoom);
  const nodeCenterX = node.x + Number(node.width || DEFAULT_NODE_WIDTH) / 2;
  const nodeCenterY = node.y + getNodeCardHeight(node) / 2;
  viewport.value = {
    zoom,
    x: rect.width / 2 - nodeCenterX * zoom,
    y: rect.height / 2 - nodeCenterY * zoom,
  };
  selectedNodeId.value = node.id;
  nodeSearchOpen.value = false;
  scheduleViewportSave();
}

function focusCanvasNodesAtCurrentZoom(targetNodes: CanvasNode[]) {
  const rect = canvasStageRef.value?.getBoundingClientRect();
  const bounds = getNodesBounds(targetNodes);
  if (!rect || !bounds) return;
  const zoom = viewport.value.zoom;
  const centerX = (bounds.minX + bounds.maxX) / 2;
  const centerY = (bounds.minY + bounds.maxY) / 2;
  viewport.value = {
    zoom,
    x: rect.width / 2 - centerX * zoom,
    y: rect.height / 2 - centerY * zoom,
  };
  selectedNodeId.value = targetNodes[0]?.id ?? null;
  nodeSearchOpen.value = false;
  scheduleViewportSave();
}

function getNodeImageUrl(node: CanvasNode) {
  if (node.node_type === "image") return (node as CanvasWorkbenchNode).localObjectUrl || node.image_url;
  const image = node.task?.images?.find((item) => item.status === "success") || node.task?.images?.[0];
  const previewUrl = getPreviewImageUrl(image);
  if (previewUrl && (node.id === focusedCanvasNodeId.value || loadedWebpImageUrls.value.has(previewUrl))) {
    return previewUrl;
  }
  return getDisplayImageUrl(image);
}

function handleNodeImageLoad(node: CanvasNode) {
  if (node.id !== focusedCanvasNodeId.value) return;
  const image = node.task?.images?.find((item) => item.status === "success") || node.task?.images?.[0];
  const previewUrl = getPreviewImageUrl(image);
  if (!previewUrl || loadedWebpImageUrls.value.has(previewUrl)) return;
  const nextLoadedUrls = new Set(loadedWebpImageUrls.value);
  nextLoadedUrls.add(previewUrl);
  loadedWebpImageUrls.value = nextLoadedUrls;
}

function getNodeStatusText(node: CanvasNode) {
  const status = node.task?.status || "pending";
  if (status === "success") return "已完成";
  if (status === "failed") return "生成失败";
  if (status === "processing") return "生成中";
  if (status === "queued") return "排队中";
  return "等待提交";
}

function getNodeFailureMessage(node: CanvasNode) {
  const task = node.task;
  const failedImage = task?.images?.find((item) => item.status === "failed") || task?.images?.[0];
  return getTaskImageFailureMessage(task, failedImage);
}

function isNodeGenerating(node: CanvasNode) {
  return ["pending", "queued", "processing"].includes(node.task?.status || "pending");
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

function parseRatioParts(value?: string) {
  if (!value) return null;
  const normalized = value.trim();
  const ratioMatch = normalized.match(/^(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)$/);
  if (ratioMatch) {
    return { width: Number(ratioMatch[1]), height: Number(ratioMatch[2]) };
  }
  const sizeMatch = normalized.match(/^(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)$/);
  if (sizeMatch) {
    return { width: Number(sizeMatch[1]), height: Number(sizeMatch[2]) };
  }
  return null;
}

function formatRatioOptionLabel(option: { label: string; value: string }) {
  const parts = parseRatioParts(option.value);
  if (!parts) return option.label.trim() || option.value;
  return option.value.includes(":") ? `${parts.width}:${parts.height}` : `${parts.width} x ${parts.height}`;
}

function getRatioPreviewStyle(value: string, maxSize = 28) {
  const parts = parseRatioParts(value);
  if (!parts || parts.width <= 0 || parts.height <= 0) {
    return { width: `${maxSize}px`, height: `${maxSize}px` };
  }
  if (parts.width >= parts.height) {
    return {
      width: `${maxSize}px`,
      height: `${Math.max(4, Math.round((maxSize * parts.height) / parts.width))}px`,
    };
  }
  return {
    height: `${maxSize}px`,
    width: `${Math.max(4, Math.round((maxSize * parts.width) / parts.height))}px`,
  };
}

function getNodeAspectRatio(node: CanvasNode) {
  if (node.node_type === "text" || node.node_type === "image") {
    return `${Number(node.width || DEFAULT_NODE_WIDTH)} / ${Number(node.height || DEFAULT_NODE_HEIGHT)}`;
  }
  return parseAspectRatio(node.task?.custom_size) || parseAspectRatio(node.task?.size) || "1 / 1";
}

function getNodeAspectRatioValue(node: CanvasNode) {
  const ratio = getNodeAspectRatio(node);
  const [widthText, heightText] = ratio.split("/").map((item) => item.trim());
  const width = Number(widthText);
  const height = Number(heightText);
  if (!width || !height) return 1;
  return width / height;
}

function getNodeCardHeight(node: CanvasNode) {
  if (node.node_type === "text" || node.node_type === "image") {
    return Number(node.height || DEFAULT_NODE_HEIGHT);
  }
  const imageHeight = Number(node.width || DEFAULT_NODE_WIDTH) / getNodeAspectRatioValue(node);
  return Math.max(160, imageHeight);
}

type CanvasEdgeAnchor = "top" | "right" | "bottom" | "left";

function getAutoEdgeAnchors(source: CanvasNode, target: CanvasNode): { source: CanvasEdgeAnchor; target: CanvasEdgeAnchor } {
  const sourceCenter = {
    x: source.x + Number(source.width || DEFAULT_NODE_WIDTH) / 2,
    y: source.y + getNodeCardHeight(source) / 2,
  };
  const targetCenter = {
    x: target.x + Number(target.width || DEFAULT_NODE_WIDTH) / 2,
    y: target.y + getNodeCardHeight(target) / 2,
  };
  const dx = targetCenter.x - sourceCenter.x;
  const dy = targetCenter.y - sourceCenter.y;
  if (Math.abs(dx) >= Math.abs(dy)) {
    return dx >= 0 ? { source: "right", target: "left" } : { source: "left", target: "right" };
  }
  return dy >= 0 ? { source: "bottom", target: "top" } : { source: "top", target: "bottom" };
}

function getAnchorPoint(node: CanvasNode, anchor: CanvasEdgeAnchor) {
  const width = Number(node.width || DEFAULT_NODE_WIDTH);
  const height = getNodeCardHeight(node);
  if (anchor === "top") return { x: node.x + width / 2, y: node.y };
  if (anchor === "right") return { x: node.x + width, y: node.y + height / 2 };
  if (anchor === "bottom") return { x: node.x + width / 2, y: node.y + height };
  return { x: node.x, y: node.y + height / 2 };
}

function getEdgePath(edge: CanvasEdge) {
  const source = nodeMap.value.get(edge.source_node_id);
  const target = nodeMap.value.get(edge.target_node_id);
  if (!source || !target) return "";
  const autoAnchors = getAutoEdgeAnchors(source, target);
  const sourceAnchor = edge.source_anchor === "auto" ? autoAnchors.source : edge.source_anchor;
  const targetAnchor = edge.target_anchor === "auto" ? autoAnchors.target : edge.target_anchor;
  const start = getAnchorPoint(source, sourceAnchor);
  const end = getAnchorPoint(target, targetAnchor);
  const distance = Math.hypot(end.x - start.x, end.y - start.y);
  const handle = Math.max(80, Math.min(220, distance * 0.35));
  const sourceVector = sourceAnchor === "left" ? { x: -handle, y: 0 } : sourceAnchor === "right" ? { x: handle, y: 0 } : sourceAnchor === "top" ? { x: 0, y: -handle } : { x: 0, y: handle };
  const targetVector = targetAnchor === "left" ? { x: -handle, y: 0 } : targetAnchor === "right" ? { x: handle, y: 0 } : targetAnchor === "top" ? { x: 0, y: -handle } : { x: 0, y: handle };
  return `M ${start.x} ${start.y} C ${start.x + sourceVector.x} ${start.y + sourceVector.y}, ${end.x + targetVector.x} ${end.y + targetVector.y}, ${end.x} ${end.y}`;
}

async function setSourceEdgesCollapsed(sourceNodeId: number, collapsed: boolean) {
  const group = edgesBySource.value.get(sourceNodeId) || [];
  if (!group.length) return;
  edges.value = edges.value.map((edge) => edge.source_node_id === sourceNodeId ? { ...edge, is_collapsed: collapsed } : edge);
  if (canvasReadOnly.value) return;
  const projectId = selectedCanvasProjectId.value;
  if (!projectId) return;
  try {
    const updatedEdges = await Promise.all(group.map((edge) => updateCanvasEdge(projectId, edge.id, { is_collapsed: collapsed })));
    const updatedMap = new Map(updatedEdges.map((edge) => [edge.id, edge]));
    edges.value = edges.value.map((edge) => updatedMap.get(edge.id) || edge);
  } catch (err: any) {
    message.error(err.response?.data?.detail || "保存连线状态失败");
  }
}

watch(generationModels, (models) => {
  if (!models.length) {
    selectedModel.value = "";
    return;
  }
  if (!models.some((item) => item.scene_key === selectedModel.value)) {
    selectedModel.value = models[0].scene_key;
  }
}, { immediate: true });

watch(sizeOptions, (options) => {
  if (options.length && !options.some((item) => item.value === size.value)) {
    size.value = options[0].value;
  }
}, { immediate: true });

watch(resolutionOptions, (options) => {
  if (options.length && !options.some((item) => item.value === resolution.value)) {
    resolution.value = options[0].value;
  }
}, { immediate: true });

watch(maxReferenceImages, (limit) => {
  if (!isImageEditMode.value) {
    canvasReferenceSelectMode.value = false;
    return;
  }
  if (referenceItems.value.length > limit) {
    referenceItems.value.slice(limit).forEach((item) => revokeObjectUrl(item.objectUrl));
    referenceItems.value = referenceItems.value.slice(0, limit);
  }
  if (!referenceSlotsRemaining.value) {
    canvasReferenceSelectMode.value = false;
  }
});

watch(canvasMode, (mode) => {
  if (mode !== "imageEdit") {
    canvasReferenceSelectMode.value = false;
    uploadMenuOpen.value = false;
  }
});

watch(canvasBackgroundMode, (mode) => {
  localStorage.setItem(CANVAS_BACKGROUND_STORAGE_KEY, mode);
});

watch(() => props.projectId, async (projectId) => {
  if (!projectId || projectId === selectedCanvasProjectId.value) return;
  canvasReferenceSelectMode.value = false;
  const canvas = canvases.value.find((item) => item.project_id === projectId);
  if (canvas) {
    await selectCanvas(canvas);
    return;
  }
  await loadCanvasList(projectId);
});

onMounted(async () => {
  document.addEventListener("pointerdown", handleDocumentPointerDown);
  await Promise.all([loadSceneConfig(), loadCanvasList(props.projectId || null)]);
});

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", handleDocumentPointerDown);
  stopTaskPolling();
  if (viewportSaveTimer.value) clearTimeout(viewportSaveTimer.value);
  referenceItems.value.forEach((item) => revokeObjectUrl(item.objectUrl));
  revokeLocalNodeObjectUrls();
});
</script>

<template>
  <div class="canvas-page" :class="{ 'config-collapsed': generatePanelCollapsed }">
    <main
      ref="canvasStageRef"
      class="canvas-stage"
      :class="{ panning: !!panState, 'background-solid': canvasBackgroundMode === 'solid' }"
      @wheel="handleWheel"
      @pointerdown="handleStagePointerDown"
      @pointermove="handleStagePointerMove"
      @pointerup="handleStagePointerUp"
      @pointercancel="handleStagePointerUp"
    >
      <div ref="projectSwitcherRef" class="canvas-project-switcher" @pointerdown.stop @click.stop>
        <template v-if="canvasReadOnly && readonlyCanvasOwnerFallback">
          <div class="canvas-project-trigger canvas-readonly-project-name" :title="selectedCanvas?.name || '当前画布'">
            <span>{{ selectedCanvas?.name || "当前画布" }}</span>
          </div>
          <button
            type="button"
            class="canvas-project-trigger canvas-owner-trigger"
            title="查看用户信息"
            @click="openReadonlyOwnerDialog"
          >
            <a-avatar :size="22" :src="withApiBaseUrl(readonlyCanvasOwnerFallback.avatar_url) || undefined" class="canvas-owner-avatar">
              {{ readonlyCanvasOwnerFallback.username?.charAt(0)?.toUpperCase() }}
            </a-avatar>
            <span>{{ readonlyCanvasOwnerFallback.username }}</span>
          </button>
        </template>
        <template v-else>
          <button
            type="button"
            class="canvas-project-trigger"
            :class="{ active: canvasMenuOpen }"
            title="切换画布"
            @click="toggleCanvasMenu"
          >
            <span>{{ selectedCanvas?.name || "选择画布" }}</span>
            <DownOutlined class="canvas-project-trigger-icon" />
          </button>
        </template>

        <div v-if="canvasMenuOpen && !canvasReadOnly" class="canvas-project-menu canvas-panel">
          <div class="canvas-project-menu-title">Projects</div>
          <div class="canvas-project-list">
            <button
              v-for="canvas in canvases"
              :key="canvas.id"
              type="button"
              class="canvas-project-item"
              :class="{ active: canvas.id === selectedCanvasId }"
              @click="handleCanvasSelect(canvas)"
            >
              <span class="canvas-project-thumb">{{ canvas.name.slice(0, 1).toUpperCase() }}</span>
              <span class="canvas-project-copy">
                <span class="canvas-project-name">{{ canvas.name }}</span>
                <span class="canvas-project-meta">{{ canvas.node_count }} 个节点</span>
              </span>
            </button>
          </div>
          <div class="canvas-project-actions">
            <button type="button" @click="handleRenameCurrentCanvas">
              <EditOutlined />
              <span>重命名画布</span>
            </button>
            <button type="button" :disabled="creatingCanvas" @click="handleCreateCanvasFromMenu">
              <PlusOutlined />
              <span>新建画布</span>
            </button>
          </div>
        </div>
      </div>

      <div class="canvas-guide" @pointerdown.stop @click.stop>
        <button type="button" class="canvas-guide-trigger canvas-panel" @click="guideOpen = !guideOpen">
          <InfoCircleOutlined />
          <span>操作指南</span>
        </button>
        <div v-if="guideOpen" class="canvas-guide-card canvas-panel">
          <button type="button" class="canvas-guide-close" title="关闭操作指南" @click="guideOpen = false">
            ×
          </button>
          <div class="canvas-guide-title">Windows 操作</div>
          <div class="canvas-guide-list">
            <div>
              <kbd>左键拖拽空白</kbd>
              <span>移动画布视野</span>
            </div>
            <div>
              <kbd>鼠标滚轮</kbd>
              <span>以鼠标位置为中心缩放画布</span>
            </div>
            <div>
              <kbd>Ctrl + 滚轮</kbd>
              <span>缩放画布</span>
            </div>
            <div>
              <kbd>触控板双指滑动</kbd>
              <span>平移或缩放画布</span>
            </div>
            <div>
              <kbd>拖拽图片卡片</kbd>
              <span>调整图片在画布中的位置</span>
            </div>
            <div>
              <kbd>单击图片</kbd>
              <span>打开重新生成、详情、下载、反馈、删除</span>
            </div>
            <div>
              <kbd>双击图片</kbd>
              <span>预览大图</span>
            </div>
          </div>
        </div>
      </div>

      <div class="canvas-settings" @pointerdown.stop @click.stop>
        <button
          type="button"
          class="canvas-settings-trigger canvas-panel"
          title="画布设置"
          @click="canvasSettingsOpen = !canvasSettingsOpen"
        >
          <SettingOutlined />
        </button>
        <div v-if="canvasSettingsOpen" class="canvas-settings-card canvas-panel">
          <div class="canvas-settings-title">画布设置</div>
          <div class="canvas-settings-field">
            <span>画布背景</span>
            <div class="canvas-background-options">
              <button
                type="button"
                :class="{ active: canvasBackgroundMode === 'grid' }"
                @click="setCanvasBackgroundMode('grid')"
              >
                网格
              </button>
              <button
                type="button"
                :class="{ active: canvasBackgroundMode === 'solid' }"
                @click="setCanvasBackgroundMode('solid')"
              >
                纯色
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="canvas-side-toolbox-wrap" @pointerdown.stop @click.stop>
        <div class="canvas-side-toolbox canvas-panel">
          <a-tooltip :title="canvasReadOnly ? '只读模式下不可创建自由节点' : '自由节点'" placement="right">
            <button type="button" :disabled="canvasReadOnly" @click="handleCanvasSideTool('freeNode')">
              <PlusOutlined />
            </button>
          </a-tooltip>
          <a-tooltip title="搜索节点" placement="right">
            <button type="button" @click="handleCanvasSideTool('searchNode')">
              <SearchOutlined />
            </button>
          </a-tooltip>
          <span class="canvas-side-toolbox-divider"></span>
          <a-tooltip title="历史任务" placement="right">
            <button type="button" @click="handleCanvasSideTool('historyTasks')">
              <HistoryOutlined />
            </button>
          </a-tooltip>
          <span class="canvas-side-toolbox-divider"></span>
          <a-tooltip :title="canvasReadOnly ? '只读模式下不可整理并保存节点' : '一键整理'" placement="right">
            <button type="button" :disabled="canvasReadOnly" @click="arrangeCanvasNodes">
              <ClearOutlined />
            </button>
          </a-tooltip>
        </div>
        <div v-if="freeNodeMenuOpen" class="canvas-free-node-menu canvas-panel">
          <button type="button" @click="createFreeTextNode">文本节点</button>
          <button type="button" @click="triggerFreeImageUpload">上传图片</button>
        </div>
        <input ref="freeNodeImageInputRef" type="file" accept="image/*" multiple hidden @change="handleFreeImageUpload" />
      </div>

      <div class="canvas-workbench-actions" @pointerdown.stop @click.stop>
        <button type="button" class="canvas-feedback-btn" @click="openCanvasFeedback">
          反馈
        </button>
        <button type="button" class="canvas-brand-link" title="返回画布列表" @click="goCanvasList">
          <span class="canvas-brand-mark">
            <img src="/香蕉.svg" alt="80AI" />
          </span>
          <span class="canvas-brand-copy">
            <span class="canvas-brand-name">80AI</span>
            <span class="canvas-brand-sub">画布列表</span>
          </span>
        </button>
      </div>

      <div class="canvas-toolbar canvas-panel">
        <a-button shape="circle" class="canvas-toolbar-icon-btn" @click="zoomAtCenter(-0.12)"><template #icon><MinusOutlined /></template></a-button>
        <span>{{ Math.round(viewport.zoom * 100) }}%</span>
        <a-button shape="circle" class="canvas-toolbar-icon-btn" @click="zoomAtCenter(0.12)"><template #icon><PlusOutlined /></template></a-button>
        <a-button class="canvas-toolbar-action-btn" @click="resetViewport"><template #icon><AimOutlined /></template>复位</a-button>
        <a-button class="canvas-toolbar-action-btn" :loading="loading" @click="loadCanvasDetail()"><template #icon><ReloadOutlined /></template>刷新</a-button>
      </div>

      <section
        class="canvas-composer-shell canvas-panel"
        :class="{
          collapsed: generatePanelCollapsed,
          expanded: !generatePanelCollapsed,
          'mode-text-generate': !isImageEditMode,
          'mode-image-edit': isImageEditMode,
          'no-mode-transition': composerModeSwitching,
        }"
        @pointerdown.stop
        @wheel.stop
        @click.stop="generatePanelCollapsed ? expandGeneratePanel() : (composerPopover = null)"
      >
        <Transition name="canvas-composer-content" mode="out-in">
          <div v-if="generatePanelCollapsed" key="collapsed" class="canvas-prompt-collapsed-content">
            <input
              v-model="prompt"
              type="text"
              placeholder="每个伟大的想法都始于一个念头..."
              @focus="expandGeneratePanel"
            />
          </div>

          <div v-else key="expanded" class="canvas-bottom-composer-content">
            <button type="button" class="canvas-composer-close" title="收起配置" @click.stop="collapseGeneratePanel">
              ×
            </button>
            <input ref="referenceInputRef" type="file" accept="image/*" multiple hidden @change="handleReferenceChange" />

            <div
              v-if="isImageEditMode"
              class="composer-reference-strip"
              :class="{ dragover: referenceDragActive }"
              @dragenter.stop.prevent="handleReferenceDragEnter"
              @dragover.stop.prevent="handleReferenceDragOver"
              @dragleave.stop.prevent="handleReferenceDragLeave"
              @drop.stop.prevent="handleReferenceDrop"
            >
              <div class="composer-reference-uploader composer-upload-entry">
                <button
                  type="button"
                  class="composer-reference-placeholder"
                  :disabled="referenceItems.length >= maxReferenceImages"
                  @click="toggleReferenceUploadMenu('reference')"
                >
                  <PictureOutlined />
                </button>
                <div v-if="uploadMenuOpen && uploadMenuAnchor === 'reference'" class="composer-upload-menu composer-upload-menu-reference">
                  <button type="button" @click="triggerReferenceUpload">
                    <UploadOutlined />
                    <span>本地上传</span>
                  </button>
                  <button type="button" @click="openCanvasReferencePicker">
                    <AimOutlined />
                    <span>从画布选择</span>
                  </button>
                </div>
              </div>
              <div v-for="item in referenceItems" :key="item.id" class="composer-reference-item">
                <img :src="item.localUrl" alt="reference" />
                <span v-if="item.status !== 'success'" class="reference-status">{{ item.status === 'uploading' ? '上传中' : '失败' }}</span>
                <button type="button" @click="removeReference(item)">
                  <DeleteOutlined />
                </button>
              </div>
            </div>

            <textarea
              v-model="prompt"
              class="composer-prompt-input"
              :maxlength="5000"
              placeholder="描述你希望如何编辑这张图片..."
            ></textarea>

            <div class="composer-footer">
              <div class="composer-mode-switch" aria-label="生成模式">
                <button type="button" :class="{ active: isImageEditMode }" @click="switchCanvasMode('imageEdit')">
                  图编辑
                </button>
                <button type="button" :class="{ active: !isImageEditMode }" @click="switchCanvasMode('textGenerate')">
                  文生图
                </button>
              </div>
              <div class="composer-setting-wrap">
                <div v-if="composerPopover" class="composer-popover-card" @pointerdown.stop @click.stop>
                  <div class="composer-options-grid">
                    <div class="composer-option-field">
                      <label>模型</label>
                      <a-select v-model:value="selectedModel" :loading="sceneConfigLoading" placeholder="请选择模型">
                        <a-select-option v-for="model in generationModels" :key="model.scene_key" :value="model.scene_key">
                          {{ model.display_name || model.scene_label || model.scene_key }}
                        </a-select-option>
                      </a-select>
                    </div>
                    <div class="composer-option-field">
                      <label>质量</label>
                      <a-select v-model:value="resolution">
                        <a-select-option v-for="item in resolutionOptions" :key="item.value" :value="item.value">{{ item.label }}</a-select-option>
                      </a-select>
                    </div>
                  </div>
                  <div class="composer-ratio-section">
                    <label>宽高比</label>
                    <div class="composer-ratio-list">
                      <button
                        v-for="item in sizeOptions"
                        :key="item.value"
                        type="button"
                        class="composer-ratio-item"
                        :class="{ active: size === item.value }"
                        @click="size = item.value"
                      >
                        <span class="composer-ratio-preview-shell">
                          <span class="composer-ratio-preview" :style="getRatioPreviewStyle(item.value, 18)"></span>
                        </span>
                        <span class="composer-ratio-label">{{ formatRatioOptionLabel(item) }}</span>
                      </button>
                    </div>
                  </div>
                </div>
                <button type="button" class="composer-setting-group" @click.stop="toggleComposerPopover('model')">
                  <span class="composer-setting-model-text">{{ selectedModelOption?.display_name || selectedModelOption?.scene_label || selectedModel || '选择模型' }}</span>
                  <span class="composer-chip-divider"></span>
                  <span>{{ size }}</span>
                  <span class="composer-chip-divider"></span>
                  <span>{{ resolution }}</span>
                </button>
              </div>
              <a-select v-model:value="numImages" class="composer-count-select" popup-class-name="composer-count-dropdown" :bordered="false">
                <a-select-option v-for="count in taskCountOptions" :key="count" :value="count">
                  {{ count }}x
                </a-select-option>
              </a-select>
              <a-button type="primary" class="composer-generate-btn" :loading="generating" :disabled="!canGenerate" @click="handleGenerate">
                <template #icon><ThunderboltOutlined /></template>
                {{ generateButtonText }}
              </a-button>
            </div>
          </div>
        </Transition>
      </section>

      <div v-if="!nodes.length && !loading" class="canvas-empty canvas-panel">
        <h3>开始你的第一张画布作品</h3>
        <p>在底部配置区输入提示词并提交，任务会出现在当前视口中心。拖拽空白处移动画布，滚轮缩放查看细节。</p>
      </div>

      <div v-if="canvasReferenceSelectMode" class="canvas-reference-select-tip canvas-panel">
        <span>点击画布图片添加为参考图（{{ referenceItems.length }} / {{ maxReferenceImages }}）</span>
        <button type="button" @click="canvasReferenceSelectMode = false">完成选择</button>
      </div>

      <div
        v-if="selectedNode"
        class="canvas-node-toolbar"
        :style="selectedNodeToolbarStyle"
        @pointerdown.stop
        @pointerup.stop
        @click.stop
      >
        <template v-if="!selectedNode.node_type || selectedNode.node_type === 'task'">
          <a-tooltip title="重新生成">
            <button type="button" @click="refillGenerateConfigFromNode(selectedNode)">
              <ReloadOutlined />
            </button>
          </a-tooltip>
          <a-tooltip title="编辑图片">
            <button type="button" @click="useNodeImageForEditing(selectedNode)">
              <EditOutlined />
            </button>
          </a-tooltip>
          <a-tooltip title="下载">
            <button type="button" @click="downloadNode(selectedNode)">
              <DownloadOutlined />
            </button>
          </a-tooltip>
          <span class="canvas-node-toolbar-divider"></span>
          <a-tooltip title="详细信息">
            <button type="button" @click="openNodeDetail(selectedNode)">
              <InfoCircleOutlined />
            </button>
          </a-tooltip>
          <a-tooltip title="反馈">
            <button type="button" @click="openNodeFeedback(selectedNode)">
              <MessageOutlined />
            </button>
          </a-tooltip>
        </template>
        <template v-else>
          <a-tooltip v-if="selectedNode.node_type === 'text'" title="编辑文本">
            <button type="button" @click="openTextNodeEditor(selectedNode)">
              <EditOutlined />
            </button>
          </a-tooltip>
          <a-tooltip :title="selectedNode.node_type === 'image' && selectedNode.uploadStatus === 'uploading' ? '图片上传中' : selectedNode.node_type === 'image' ? '编辑图片' : '生成图片'">
            <button
              type="button"
              :disabled="selectedNode.node_type === 'image' && selectedNode.uploadStatus !== 'success' && !selectedNode.image_url"
              @click="selectedNode.node_type === 'image' ? useNodeImageForEditing(selectedNode) : useFreeNodeForGeneration(selectedNode)"
            >
              <EditOutlined v-if="selectedNode.node_type === 'image'" />
              <ThunderboltOutlined v-else />
            </button>
          </a-tooltip>
        </template>
        <a-tooltip v-if="!canvasReadOnly" title="删除">
          <button type="button" class="danger" @click="deleteNode(selectedNode)">
            <DeleteOutlined />
          </button>
        </a-tooltip>
      </div>

      <div
        class="canvas-world"
        :style="{ transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})` }"
      >
        <svg class="canvas-edge-layer" aria-hidden="true">
          <defs>
            <marker id="canvas-edge-arrow" markerWidth="8" markerHeight="8" refX="6.8" refY="4" orient="auto" markerUnits="strokeWidth">
              <path d="M 0 0 L 8 4 L 0 8 z" class="canvas-edge-arrow" />
            </marker>
          </defs>
          <path
            v-for="edge in visibleCanvasEdges"
            :key="edge.id"
            class="canvas-edge-path"
            :d="getEdgePath(edge)"
            marker-end="url(#canvas-edge-arrow)"
          />
        </svg>
        <button
          v-for="marker in expandedEdgeGroupControls"
          :key="`expanded-${marker.sourceNodeId}`"
          type="button"
          class="canvas-edge-marker canvas-edge-marker-compact"
          :style="{ transform: `translate(${marker.x}px, ${marker.y}px)` }"
          @pointerdown.stop
          @click.stop="setSourceEdgesCollapsed(marker.sourceNodeId, true)"
        >
          收起 {{ marker.count }}
        </button>
        <button
          v-for="marker in collapsedEdgeMarkers"
          :key="`collapsed-${marker.sourceNodeId}`"
          type="button"
          class="canvas-edge-marker"
          :style="{ transform: `translate(${marker.x}px, ${marker.y}px)` }"
          @pointerdown.stop
          @click.stop="setSourceEdgesCollapsed(marker.sourceNodeId, false)"
        >
          {{ marker.count }} 条关联
        </button>
        <article
          v-for="node in nodes"
          :key="node.id"
          class="canvas-node"
          :class="{
            failed: node.task?.status === 'failed',
            selected: node.id === selectedNodeId,
            'reference-selecting': canvasReferenceSelectMode && getNodeReferenceOption(node),
            'reference-selected': canvasReferenceSelectMode && isCanvasReferenceSelected(node),
            'uploading': node.uploadStatus === 'uploading',
            'upload-failed': node.uploadStatus === 'failed',
          }"
          :style="{
            transform: `translate(${node.x}px, ${node.y}px)`,
            width: `${node.width}px`,
            height: `${getNodeCardHeight(node)}px`,
            zIndex: node.z_index,
          }"
          @pointerdown="startNodeDrag($event, node)"
          @click.stop="handleNodeClick($event, node)"
        >
          <div
            class="node-preview"
            :style="{ aspectRatio: getNodeAspectRatio(node) }"
          >
            <template v-if="node.node_type === 'text'">
              <textarea
                v-if="textNodeEditTarget?.id === node.id"
                v-model="textNodeEditContent"
                class="canvas-free-text-editor"
                :data-text-node-editor="node.id"
                :maxlength="5000"
                placeholder="请输入文本内容"
                @pointerdown.stop
                @click.stop
                @keydown="handleTextNodeEditorKeydown"
                @blur="saveTextNodeContent"
              ></textarea>
              <div
                v-else
                class="canvas-free-text-node"
                @pointerdown="handleTextNodePointerDown($event, node)"
                @click.stop="selectNode(node)"
                @dblclick.stop.prevent="openTextNodeEditor(node)"
              >
                {{ node.content || '双击编辑文本' }}
              </div>
            </template>
            <span v-else-if="node.node_type === 'image'" class="canvas-free-image-badge">
              {{ node.uploadStatus === 'uploading' ? '上传中' : node.uploadStatus === 'failed' ? '失败' : '上传' }}
            </span>
            <img
              v-if="node.node_type !== 'text' && getNodeImageUrl(node)"
              :class="{ 'canvas-free-image': node.node_type === 'image' }"
              :src="getNodeImageUrl(node)"
              alt="generated"
              draggable="false"
              @load="handleNodeImageLoad(node)"
            />
            <div v-if="node.node_type === 'image' && node.uploadStatus && node.uploadStatus !== 'success'" class="node-upload-mask" :class="{ error: node.uploadStatus === 'failed' }">
              <a-spin v-if="node.uploadStatus === 'uploading'" :indicator="h(LoadingOutlined, { style: neutralIndicatorStyle })" />
              <span>{{ node.uploadStatus === 'uploading' ? '上传中...' : (node.uploadError || '上传失败') }}</span>
            </div>
            <div v-if="node.node_type !== 'text' && !getNodeImageUrl(node)" class="node-placeholder">
              <template v-if="isNodeGenerating(node)">
                <img :src="generateEmptyStateAsset" alt="生成中" class="node-placeholder-image" draggable="false" />
                <div class="node-placeholder-mask">
                  <a-spin :indicator="h(LoadingOutlined, { style: neutralIndicatorStyle })" />
                  <span>{{ getNodeStatusText(node) }}</span>
                </div>
              </template>
              <template v-else-if="node.task?.status === 'failed'">
                <img :src="failedResultAsset" alt="生成失败" class="node-failed-image" draggable="false" />
                <div class="node-placeholder-mask error">
                  <span>{{ getNodeFailureMessage(node) }}</span>
                </div>
              </template>
              <span v-else>{{ node.task?.error_message || '生成失败' }}</span>
            </div>
            <button
              v-if="canvasReferenceSelectMode && getNodeReferenceOption(node)"
              type="button"
              class="canvas-reference-node-picker"
              :class="{ selected: isCanvasReferenceSelected(node) }"
              :disabled="!isCanvasReferenceSelected(node) && !referenceSlotsRemaining"
              @pointerdown.stop
              @click.stop="selectCanvasNodeAsReference(node)"
            >
              <span>{{ isCanvasReferenceSelected(node) ? '取消' : '+' }}</span>
            </button>
          </div>
          <button
            v-if="!canvasReadOnly"
            type="button"
            class="canvas-node-resize-handle"
            title="拖拽调整大小"
            @pointerdown.stop.prevent="startNodeResize($event, node)"
          ></button>
        </article>
      </div>
    </main>

    <a-image
      v-if="previewCurrent"
      :width="0"
      :style="{ display: 'none' }"
      :src="previewCurrent"
      :preview="{ visible: previewVisible, onVisibleChange: (visible: boolean) => { previewVisible = visible; } }"
    />
    <HistoryDetailDialog
      v-model:open="detailOpen"
      :item="detailItem"
      :model-options="modelOptions"
      show-actions
      @download="handleDetailDownload"
    />
    <FeedbackDialog
      v-model:open="feedbackDialogOpen"
      :task-id="feedbackTarget?.id"
      :model="feedbackTarget?.model"
      :prompt="feedbackTarget?.prompt"
      :created-at="feedbackTarget?.created_at"
    />
    <FeedbackDialog
      v-model:open="canvasFeedbackOpen"
      title="问题反馈"
      context-title="反馈场景"
      prompt="无限画布"
      :require-task="false"
      :append-content="canvasFeedbackAppendContent"
    />
    <AdminUserInfoDialog
      v-model:open="readonlyOwnerDialogOpen"
      :user="selectedReadonlyOwner"
    />
    <a-modal
      v-model:open="nodeSearchOpen"
      title="搜索节点"
      :footer="null"
      width="640px"
      centered
    >
      <div class="node-search-dialog">
        <a-input-search
          v-model:value="nodeSearchKeyword"
          placeholder="输入任务 ID、提示词、模型或状态"
          enter-button="搜索"
          allow-clear
          @search="submitNodeSearch"
        />
        <div class="node-search-summary">
          {{ nodeSearchQuery ? `匹配到 ${nodeSearchResults.length} 个任务` : `当前画布共 ${nodeSearchResults.length} 个任务` }}
        </div>
        <div v-if="nodeSearchResults.length" class="node-search-results">
          <button
            v-for="node in nodeSearchResults"
            :key="node.id"
            type="button"
            class="node-search-result"
            @click="focusCanvasNode(node)"
          >
            <span class="node-search-thumb">
              <img v-if="getNodeSearchThumbUrl(node)" :src="getNodeSearchThumbUrl(node)" alt="任务缩略图" />
              <PictureOutlined v-else />
            </span>
            <span class="node-search-copy">
              <span class="node-search-title">{{ getNodeSearchTitle(node) }}</span>
              <span class="node-search-meta">{{ getNodeSearchMeta(node) }}</span>
            </span>
          </button>
        </div>
        <a-empty v-else description="没有匹配到任务" />
      </div>
    </a-modal>
  </div>
</template>

<style scoped lang="scss">
@property --collapsed-prompt-border-angle {
  syntax: "<angle>";
  inherits: false;
  initial-value: 0deg;
}

.canvas-page {
  position: relative;
  display: block;
  height: 100vh;
  min-height: 100vh;
}

.canvas-panel {
  border: 1px solid var(--theme-panel-border);
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-soft));
  box-shadow: 0 16px 34px var(--theme-card-shadow);
}

.node-search-dialog {
  display: grid;
  gap: 10px;
}

.node-search-summary {
  color: var(--theme-text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.node-search-results {
  display: grid;
  gap: 8px;
  max-height: min(520px, 58vh);
  overflow-y: auto;
  padding-right: 4px;
}

.node-search-result {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px;
  border: 1px solid var(--theme-panel-border);
  border-radius: 14px;
  background: var(--theme-panel-bg-muted);
  color: var(--theme-title);
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    transform 0.18s ease;
}

.node-search-result:hover {
  border-color: var(--theme-accent);
  box-shadow: 0 12px 24px color-mix(in srgb, var(--theme-accent) 18%, transparent);
  transform: translateY(-1px);
}

.node-search-thumb {
  overflow: hidden;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: var(--theme-empty-bg);
  color: var(--theme-text-secondary);
  font-size: 20px;
}

.node-search-thumb img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.node-search-copy {
  min-width: 0;
  display: grid;
  gap: 3px;
}

.node-search-title {
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  color: var(--theme-title);
  font-size: 13px;
  font-weight: 900;
  line-height: 1.3;
}

.node-search-meta {
  overflow: hidden;
  color: var(--theme-text-secondary);
  font-size: 11px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.canvas-composer-shell {
  position: absolute;
  left: 50%;
  z-index: 48;
  box-sizing: border-box;
  transform: translateX(-50%);
  isolation: isolate;
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  overflow: hidden;
  transition:
    bottom 0.34s cubic-bezier(0.4, 0, 0.2, 1),
    width 0.34s cubic-bezier(0.4, 0, 0.2, 1),
    min-width 0.34s cubic-bezier(0.4, 0, 0.2, 1),
    height 0.34s cubic-bezier(0.4, 0, 0.2, 1),
    padding 0.34s cubic-bezier(0.4, 0, 0.2, 1),
    border-radius 0.34s cubic-bezier(0.4, 0, 0.2, 1),
    box-shadow 0.34s ease-in-out;
  will-change: bottom, width, height, padding, border-radius;
}

.canvas-composer-shell.collapsed {
  bottom: 22px;
  width: min(600px, 38vw);
  min-width: 400px;
  height: 50px;
  border-radius: 24px;
  padding: 0 20px;
  cursor: text;
}

.canvas-composer-shell.expanded {
  bottom: 18px;
  width: min(660px, 42vw);
  min-width: 470px;
  border-radius: 20px;
  padding: 13px;
  cursor: default;
  overflow: visible;
}

.canvas-composer-shell.expanded.mode-text-generate {
  height: 150px;
}

.canvas-composer-shell.expanded.mode-image-edit {
  height: 210px;
}

.canvas-composer-shell.no-mode-transition {
  transition: none;
}

.canvas-composer-shell.collapsed::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 0;
  border-radius: inherit;
  border: 1px solid transparent;
  background:
    linear-gradient(var(--theme-panel-bg), var(--theme-panel-bg-soft)) padding-box,
    conic-gradient(
      from var(--collapsed-prompt-border-angle, 0deg),
      transparent 0deg,
      transparent 250deg,
      color-mix(in srgb, var(--theme-accent) 24%, transparent) 286deg,
      color-mix(in srgb, var(--theme-accent) 86%, #ffffff 14%) 316deg,
      color-mix(in srgb, var(--theme-accent) 24%, transparent) 346deg,
      transparent 360deg
    ) border-box;
  box-shadow:
    inset 0 0 18px color-mix(in srgb, var(--theme-accent) 8%, transparent),
    0 0 24px color-mix(in srgb, var(--theme-accent) 16%, transparent);
  opacity: 1;
  pointer-events: none;
  transition: opacity 0.18s ease-in-out;
  animation: collapsedPromptBorderSpin 3.2s linear infinite;
}

.canvas-composer-shell.expanded::before {
  opacity: 0;
}

.canvas-prompt-collapsed-content,
.canvas-bottom-composer-content {
  width: 100%;
  height: 100%;
  min-width: 0;
}

.canvas-prompt-collapsed-content {
  display: flex;
  align-items: center;
}

.canvas-bottom-composer-content {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow: visible;
}

.canvas-composer-content-enter-active,
.canvas-composer-content-leave-active {
  transition:
    opacity 0.14s ease-in-out,
    transform 0.14s ease-in-out;
}

.canvas-composer-content-enter-from,
.canvas-composer-content-leave-to {
  opacity: 0;
  transform: translateY(4px);
}

.canvas-composer-content-enter-to,
.canvas-composer-content-leave-from {
  opacity: 1;
  transform: translateY(0);
}

.canvas-prompt-collapsed-content input {
  position: relative;
  z-index: 1;
  width: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--theme-title);
  font-size: 14px;
  font-weight: 600;
}

.canvas-prompt-collapsed-content input::placeholder {
  color: var(--theme-text-secondary);
}

@keyframes collapsedPromptBorderSpin {
  to {
    --collapsed-prompt-border-angle: 360deg;
  }
}

@media (prefers-reduced-motion: reduce) {
  .canvas-composer-shell,
  .canvas-composer-content-enter-active,
  .canvas-composer-content-leave-active {
    transition: opacity 0.01s linear;
  }
}

.canvas-composer-close {
  position: absolute;
  top: 0;
  right: 0;
  width: 22px;
  height: 22px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--theme-text-secondary);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}

.canvas-composer-close:hover {
  background: var(--theme-panel-bg-muted);
  color: var(--theme-title);
}

.composer-prompt-input {
  width: 100%;
  min-height: 70px;
  flex: 1 1 auto;
  border: 0;
  outline: 0;
  resize: none;
  background: transparent;
  color: var(--theme-title);
  font-size: 13px;
  line-height: 1.5;
}

.composer-prompt-input::placeholder {
  color: var(--theme-text-secondary);
}

.composer-reference-strip {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  overflow: visible;
  padding-right: 30px;
  padding-block: 3px;
  border-radius: 14px;
  transition:
    background 0.18s ease,
    box-shadow 0.18s ease;
}

.composer-reference-strip.dragover {
  background: color-mix(in srgb, var(--theme-accent) 10%, transparent);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--theme-accent) 38%, transparent);
}

.composer-reference-uploader {
  position: relative;
  flex: 0 0 auto;
}

.composer-reference-placeholder {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border: 1px solid var(--theme-panel-border);
  border-radius: 12px;
  background: var(--theme-panel-bg-muted);
  color: var(--theme-text-secondary);
  font-size: 20px;
  cursor: pointer;
}

.composer-reference-placeholder:hover {
  border-color: var(--theme-border-strong);
  color: var(--theme-title);
}

.composer-reference-placeholder:disabled {
  cursor: not-allowed;
  opacity: 0.48;
}

.composer-reference-item {
  position: relative;
  flex: 0 0 auto;
  width: 48px;
  height: 48px;
  overflow: hidden;
  border-radius: 10px;
  background: var(--theme-panel-bg);
  border: 1px solid var(--theme-panel-border);
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    transform 0.18s ease;
}

.composer-reference-item:hover {
  border-color: var(--theme-accent);
  box-shadow: 0 10px 20px color-mix(in srgb, var(--theme-accent) 20%, transparent);
  transform: translateY(-1px);
}

.composer-reference-item img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
  transition: transform 0.22s ease;
}

.composer-reference-item:hover img {
  transform: scale(1.04);
}

.composer-reference-item button {
  position: absolute;
  top: 4px;
  right: 4px;
  border: 0;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.48);
  color: #fff;
  opacity: 0;
  pointer-events: none;
  cursor: pointer;
  transition: opacity 0.18s ease;
}

.composer-reference-item:hover button {
  opacity: 1;
  pointer-events: auto;
}

.reference-status {
  position: absolute;
  inset: auto 4px 4px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.58);
  color: #fff;
  font-size: 10px;
  text-align: center;
}

.composer-popover-card {
  position: absolute;
  bottom: calc(100% + 10px);
  left: 50%;
  z-index: 6;
  width: min(440px, calc(66.666vw - 32px));
  display: grid;
  gap: 10px;
  padding: 12px;
  border-radius: 16px;
  border: 1px solid var(--theme-panel-border);
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-soft));
  box-shadow: 0 18px 36px var(--theme-card-shadow-strong);
  transform: translateX(-50%);
}

.composer-popover-card::after {
  content: "";
  position: absolute;
  bottom: -7px;
  left: 50%;
  width: 14px;
  height: 14px;
  border-right: 1px solid var(--theme-panel-border);
  border-bottom: 1px solid var(--theme-panel-border);
  background: var(--theme-panel-bg-soft);
  transform: translateX(-50%) rotate(45deg);
}

.composer-option-field,
.composer-ratio-section {
  display: grid;
  gap: 6px;
}

.composer-option-field > label,
.composer-ratio-section > label {
  color: var(--theme-text-secondary);
  font-size: 12px;
  font-weight: 800;
}

.composer-options-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(140px, 0.45fr);
  gap: 12px;
}

.composer-ratio-item {
  min-height: 36px;
  padding: 4px;
  border: 1px solid var(--theme-panel-border);
  border-radius: 10px;
  background: var(--theme-panel-bg);
  color: var(--theme-text-secondary);
  font-weight: 800;
  cursor: pointer;
}

.composer-ratio-item.active {
  background: var(--theme-accent);
  color: var(--theme-accent-contrast);
  border-color: transparent;
}

.composer-ratio-list {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 6px;
}

.composer-ratio-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
}

.composer-ratio-preview-shell {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 16px;
  flex: 0 0 auto;
}

.composer-ratio-preview {
  display: block;
  border: 1.4px solid currentColor;
  border-radius: 3px;
  background: color-mix(in srgb, currentColor 12%, transparent);
}

.composer-ratio-label {
  font-size: 10px;
  line-height: 1.1;
}

.composer-footer {
  margin-top: auto;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.composer-icon-btn {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: 1px solid var(--theme-panel-border);
  border-radius: 999px;
  background: var(--theme-panel-bg-muted);
  color: var(--theme-title);
  cursor: pointer;
}

.composer-icon-btn:disabled {
  cursor: not-allowed;
  opacity: 0.48;
}

.composer-upload-menu {
  position: absolute;
  bottom: calc(100% + 10px);
  left: 0;
  z-index: 5;
  min-width: 160px;
  padding: 8px;
  border: 1px solid var(--theme-panel-border);
  border-radius: 14px;
  background: var(--theme-panel-bg);
  box-shadow: 0 18px 36px var(--theme-card-shadow-strong);
}

.composer-upload-menu button {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  height: 34px;
  padding: 0 9px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--theme-title);
  font-size: 12px;
  font-weight: 800;
  text-align: left;
  cursor: pointer;
}

.composer-upload-menu button:hover {
  background: var(--theme-panel-bg-muted);
}

.composer-upload-menu-reference {
  top: calc(100% + 8px);
  bottom: auto;
}

.composer-mode-switch {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  height: 34px;
  padding: 2px;
  border: 1px solid var(--theme-panel-border);
  border-radius: 12px;
  background: var(--theme-panel-bg-muted);
}

.composer-mode-switch button {
  height: 28px;
  padding: 0 10px;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: var(--theme-text-secondary);
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
  cursor: pointer;
}

.composer-mode-switch button.active {
  background: var(--theme-accent);
  color: var(--theme-accent-contrast);
  box-shadow: 0 8px 16px color-mix(in srgb, var(--theme-accent) 28%, transparent);
}

.composer-setting-wrap {
  position: relative;
  flex: 0 1 auto;
  min-width: 0;
  max-width: min(340px, calc(100% - 270px));
}

.composer-setting-group {
  width: fit-content;
  max-width: 100%;
  min-width: 0;
  flex: 0 1 auto;
  display: inline-flex;
  align-items: center;
  gap: 0;
  height: 34px;
  padding: 0 9px;
  border: 1px solid var(--theme-panel-border);
  border-radius: 12px;
  background: var(--theme-panel-bg-muted);
  color: var(--theme-title);
  font-weight: 800;
  font: inherit;
  cursor: pointer;
  white-space: nowrap;
}

.composer-setting-group:hover {
  border-color: var(--theme-border-strong);
  background: var(--theme-panel-bg-soft);
}

.composer-setting-model-text {
  min-width: 0;
  max-width: 190px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.composer-chip-divider {
  width: 1px;
  height: 14px;
  flex: 0 0 auto;
  margin: 0 8px;
  background: var(--theme-panel-border);
}

.composer-count-select {
  margin-left: auto;
  flex: 0 0 66px;
  height: 34px;
  border-radius: 12px;
  background: var(--theme-panel-bg-muted);
  border: 1px solid var(--theme-panel-border);
  overflow: hidden;
  display: inline-flex;
  align-items: center;

  :deep(.ant-select-selector) {
    width: 100% !important;
    height: 100% !important;
    padding: 0 28px 0 12px !important;
    border: 0 !important;
    border-radius: 12px !important;
    background: transparent !important;
    box-shadow: none !important;
    display: flex !important;
    align-items: center !important;
  }

  :deep(.ant-select-selection-item) {
    display: inline-flex !important;
    align-items: center !important;
    color: var(--theme-title) !important;
    font-size: 12px;
    font-weight: 800;
    line-height: 1 !important;
  }

  :deep(.ant-select-arrow) {
    right: 9px;
    color: var(--theme-title);
  }
}

.composer-generate-btn {
  flex: 0 0 auto;
  height: 34px !important;
  min-width: 92px;
  border-radius: 12px !important;
  font-size: 12px !important;
  font-weight: 800 !important;
}

.canvas-stage {
  position: relative;
  z-index: 1;
  overflow: hidden;
  width: 100%;
  height: 100%;
  min-width: 0;
  border-radius: 0;
  border: 0;
  background:
    radial-gradient(circle at center, rgba(255, 171, 39, 0.08), transparent 32%),
    linear-gradient(90deg, rgba(130, 108, 83, 0.08) 1px, transparent 1px),
    linear-gradient(0deg, rgba(130, 108, 83, 0.08) 1px, transparent 1px),
    var(--theme-page-gradient);
  background-size: auto, 36px 36px, 36px 36px, auto;
  cursor: grab;

  &.panning {
    cursor: grabbing;
  }

  &.background-solid {
    background: var(--theme-page-base);
    background-size: auto;
  }
}

.canvas-project-switcher {
  position: absolute;
  top: 16px;
  left: 16px;
  z-index: 40;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  max-width: calc(100vw - 32px);
}

.canvas-guide {
  position: absolute;
  top: 58px;
  left: 56px;
  z-index: 39;
}

.canvas-settings {
  position: absolute;
  top: 58px;
  left: 16px;
  z-index: 39;
}

.canvas-settings-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 999px;
  color: var(--theme-title);
  font-size: 14px;
  cursor: pointer;
  transition:
    color 0.2s ease,
    background 0.2s ease,
    transform 0.2s ease;
}

.canvas-settings-trigger:hover {
  color: var(--theme-accent-text-hover);
  background: var(--theme-nav-hover-bg);
  transform: translateY(-1px);
}

.canvas-settings-card {
  position: absolute;
  top: 42px;
  left: 0;
  width: 248px;
  padding: 14px;
  border-radius: 18px;
}

.canvas-settings-title {
  margin-bottom: 12px;
  color: var(--theme-title);
  font-size: 14px;
  font-weight: 900;
}

.canvas-settings-field {
  display: grid;
  gap: 10px;
  color: var(--theme-text-secondary);
  font-size: 13px;
  font-weight: 800;
}

.canvas-background-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  padding: 4px;
  border: 1px solid var(--theme-panel-border);
  border-radius: 14px;
  background: var(--theme-panel-bg-muted);

  button {
    height: 34px;
    border: 0;
    border-radius: 10px;
    background: transparent;
    color: var(--theme-text-secondary);
    font-weight: 900;
    cursor: pointer;
  }

  button:hover,
  button.active {
    background: var(--theme-accent);
    color: var(--theme-accent-contrast);
    box-shadow: 0 8px 16px var(--theme-nav-active-shadow);
  }
}

.canvas-guide-trigger {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 34px;
  padding: 0 11px;
  border-radius: 999px;
  color: var(--theme-title);
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.canvas-guide-card {
  position: absolute;
  top: 40px;
  left: 0;
  width: min(360px, calc(100vw - 40px));
  padding: 14px;
  border-radius: 18px;
}

.canvas-guide-close {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 26px;
  height: 26px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--theme-text-secondary);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
}

.canvas-guide-close:hover {
  background: var(--theme-panel-bg-muted);
  color: var(--theme-title);
}

.canvas-guide-title {
  padding-right: 30px;
  margin-bottom: 10px;
  color: var(--theme-title);
  font-size: 14px;
  font-weight: 900;
}

.canvas-guide-list {
  display: grid;
  gap: 8px;
}

.canvas-guide-list div {
  display: grid;
  grid-template-columns: 112px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  color: var(--theme-text-secondary);
  font-size: 12px;
  line-height: 1.45;
}

.canvas-guide-list kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 26px;
  padding: 0 8px;
  border: 1px solid var(--theme-panel-border);
  border-radius: 9px;
  background: var(--theme-panel-bg-muted);
  color: var(--theme-title);
  font-family: inherit;
  font-size: 11px;
  font-weight: 900;
  white-space: nowrap;
}

.canvas-side-toolbox-wrap {
  position: absolute;
  top: 50%;
  left: 16px;
  z-index: 38;
  transform: translateY(-50%);
}

.canvas-side-toolbox {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 7px;
  padding: 8px 7px;
  border-radius: 22px;
}

.canvas-side-toolbox button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: 0;
  border-radius: 12px;
  background: transparent;
  color: var(--theme-title);
  font-size: 17px;
  cursor: pointer;
  transition:
    background 0.18s ease,
    color 0.18s ease,
    transform 0.18s ease;
}

.canvas-side-toolbox button:hover {
  background: var(--theme-panel-bg-muted);
  color: var(--theme-accent-text-hover);
  transform: translateY(-1px);
}

.canvas-side-toolbox-divider {
  width: 19px;
  height: 1px;
  background: var(--theme-panel-border);
}

.canvas-free-node-menu {
  position: absolute;
  top: 0;
  left: calc(100% + 10px);
  display: grid;
  gap: 6px;
  width: 144px;
  padding: 12px;
  border-radius: 20px;
}

.canvas-free-node-menu button {
  height: 36px;
  border: 0;
  border-radius: 12px;
  background: transparent;
  color: var(--theme-title);
  font-size: 13px;
  font-weight: 900;
  cursor: pointer;
}

.canvas-free-node-menu button:hover {
  background: var(--theme-panel-bg-muted);
}

.canvas-workbench-actions {
  position: absolute;
  top: 12px;
  right: 14px;
  z-index: 42;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: calc(100vw - 32px);
}

.canvas-feedback-btn {
  flex: 0 0 auto;
  height: 34px;
  padding: 0 12px;
  border: 0;
  border-radius: 999px;
  background: var(--theme-pill-bg);
  color: var(--theme-pill-text);
  font-size: 12px;
  font-weight: 900;
  cursor: pointer;
  transition:
    background 0.2s ease,
    color 0.2s ease,
    transform 0.2s ease;
}

.canvas-feedback-btn:hover {
  background: var(--theme-nav-hover-bg);
  color: var(--theme-accent-text-hover);
  transform: translateY(-1px);
}

.canvas-brand-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 38px;
  padding: 4px 10px 4px 5px;
  border: 1px solid transparent;
  border-radius: 999px;
  background: transparent;
  color: var(--theme-title);
  cursor: pointer;
}

.canvas-brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 11px;
  background: rgb(255, 171, 39);
  box-shadow: 0 8px 16px var(--theme-brand-shadow);
  overflow: hidden;

  img {
    width: 60%;
    height: 60%;
    object-fit: contain;
    display: block;
  }
}

.canvas-brand-copy {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
  line-height: 1.1;
}

.canvas-brand-name {
  font-size: 13px;
  font-weight: 900;
  color: var(--theme-title);
}

.canvas-brand-sub {
  font-size: 10px;
  font-weight: 700;
  color: var(--theme-text-secondary);
}

.canvas-project-trigger {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  max-width: 260px;
  height: 36px;
  padding: 0 12px 0 14px;
  border: 1px solid var(--theme-pill-border);
  border-radius: 999px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.72), rgba(255, 246, 225, 0.92)),
    var(--theme-pill-bg);
  color: var(--theme-title);
  box-shadow:
    inset 0 1px 0 var(--theme-panel-inset),
    0 10px 22px var(--theme-card-shadow);
  font-size: 13px;
  font-weight: 900;
  cursor: pointer;
  transition:
    background 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    color 0.2s ease,
    transform 0.2s ease;

  span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: 900;
  }

  &:hover,
  &.active {
    border-color: var(--theme-border-strong);
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.82), rgba(255, 237, 202, 0.96)),
      var(--theme-nav-hover-bg);
    color: var(--theme-accent-text-hover);
    box-shadow:
      inset 0 1px 0 var(--theme-panel-inset),
      0 14px 28px var(--theme-card-shadow-strong);
    transform: translateY(-1px);
  }

  &:active {
    transform: translateY(0);
  }

  &.readonly {
    cursor: default;
  }

  &.readonly:hover {
    border-color: var(--theme-pill-border);
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.72), rgba(255, 246, 225, 0.92)),
      var(--theme-pill-bg);
    color: var(--theme-title);
    box-shadow:
      inset 0 1px 0 var(--theme-panel-inset),
      0 10px 22px var(--theme-card-shadow);
    transform: none;
  }
}

.canvas-project-trigger-icon {
  flex: 0 0 auto;
  color: var(--theme-text-secondary);
  font-size: 10px;
  transition:
    color 0.2s ease,
    transform 0.2s ease;
}

.canvas-project-trigger:hover .canvas-project-trigger-icon,
.canvas-project-trigger.active .canvas-project-trigger-icon {
  color: var(--theme-accent-text-hover);
}

.canvas-project-trigger.active .canvas-project-trigger-icon {
  transform: rotate(180deg);
}

.canvas-readonly-project-name {
  cursor: default;
}

.canvas-readonly-project-name:hover {
  border-color: var(--theme-pill-border);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.72), rgba(255, 246, 225, 0.92)),
    var(--theme-pill-bg);
  color: var(--theme-title);
  box-shadow:
    inset 0 1px 0 var(--theme-panel-inset),
    0 10px 22px var(--theme-card-shadow);
  transform: none;
}

.canvas-owner-trigger {
  cursor: pointer;
}

.canvas-owner-avatar {
  flex: 0 0 auto;
  background: var(--theme-accent);
  color: var(--theme-accent-contrast);
  font-size: 12px;
  font-weight: 800;
}

.canvas-project-menu {
  position: absolute;
  top: 42px;
  left: 0;
  width: min(336px, calc(100vw - 40px));
  max-height: min(480px, calc(100vh - 170px));
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 16px;
  padding: 10px;
}

.canvas-project-menu-title {
  padding: 2px 8px 8px;
  color: var(--theme-subtitle);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.canvas-project-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow: hidden auto;
  padding-right: 2px;
}

.canvas-project-item {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 50px;
  padding: 7px 9px;
  border: 1px solid transparent;
  border-radius: 12px;
  background: transparent;
  color: var(--theme-title);
  text-align: left;
  cursor: pointer;

  &:hover,
  &.active {
    background: var(--theme-panel-bg-muted);
    border-color: var(--theme-panel-border);
    box-shadow: inset 0 0 0 1px var(--theme-panel-inset);
  }
}

.canvas-project-thumb {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: var(--theme-accent);
  color: var(--theme-accent-contrast);
  font-size: 14px;
  font-weight: 900;
  box-shadow: 0 8px 14px var(--theme-nav-active-shadow);
}

.canvas-project-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.canvas-project-name {
  overflow: hidden;
  color: var(--theme-title);
  font-size: 14px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.canvas-project-meta {
  color: var(--theme-text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.canvas-project-actions {
  display: grid;
  gap: 4px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--theme-panel-border);

  button {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    height: 34px;
    padding: 0 9px;
    border: 0;
    border-radius: 10px;
    background: transparent;
    color: var(--theme-text-secondary);
    font-size: 12px;
    font-weight: 800;
    cursor: pointer;
  }

  button:hover:not(:disabled) {
    background: var(--theme-panel-bg-muted);
    color: var(--theme-title);
  }

  button:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }
}

.canvas-toolbar {
  position: absolute;
  top: 14px;
  left: 50%;
  z-index: 30;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px;
  border-radius: 999px;
  transform: translateX(-50%);

  span {
    min-width: 40px;
    color: var(--theme-title);
    font-size: 12px;
    font-weight: 800;
    text-align: center;
  }
}

.canvas-toolbar-icon-btn,
.canvas-toolbar-action-btn {
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  line-height: 1 !important;
  border: 1px solid var(--theme-panel-border-strong) !important;
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-strong)) !important;
  color: var(--theme-title) !important;
  box-shadow:
    inset 0 1px 0 var(--theme-panel-inset),
    0 8px 18px var(--theme-card-shadow) !important;
  font-weight: 800 !important;
  transition:
    color 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;

  &:hover,
  &:focus {
    border-color: var(--theme-border-strong) !important;
    background: linear-gradient(180deg, var(--theme-panel-bg-soft), var(--theme-panel-bg-strong)) !important;
    color: var(--theme-accent-text-hover) !important;
    box-shadow:
      inset 0 1px 0 var(--theme-panel-inset),
      0 12px 24px var(--theme-card-shadow-strong) !important;
    transform: translateY(-1px);
  }

  &:active {
    transform: translateY(0);
  }
}

.canvas-toolbar-icon-btn {
  width: 30px !important;
  height: 30px !important;
}

.canvas-toolbar-action-btn {
  height: 30px !important;
  padding-inline: 8px !important;
  border-radius: 10px !important;
  font-size: 12px !important;

  :deep(.ant-btn-icon) {
    display: inline-flex;
    align-items: center;
    margin-inline-end: 2px;
  }

  :deep(.anticon + span) {
    margin-inline-start: 2px !important;
  }

  :deep(span:not(.ant-btn-icon)) {
    display: inline-flex;
    align-items: center;
    line-height: 1;
  }
}

.canvas-empty {
  position: absolute;
  top: 50%;
  left: 50%;
  z-index: 20;
  width: min(420px, calc(100% - 48px));
  transform: translate(-50%, -50%);
  padding: 24px;
  border-radius: 24px;
  text-align: center;
  pointer-events: none;

  h3 {
    margin: 0 0 8px;
    color: var(--theme-title);
  }

  p {
    margin: 0;
    color: var(--theme-text-secondary);
    line-height: 1.7;
  }
}

.canvas-reference-select-tip {
  position: absolute;
  bottom: 236px;
  left: 50%;
  z-index: 50;
  display: inline-flex;
  align-items: center;
  gap: 12px;
  padding: 8px 10px 8px 14px;
  border-radius: 999px;
  color: var(--theme-title);
  font-size: 13px;
  font-weight: 800;
  transform: translateX(-50%);
}

.canvas-reference-select-tip button {
  height: 30px;
  padding: 0 12px;
  border: 0;
  border-radius: 999px;
  background: var(--theme-accent);
  color: var(--theme-accent-contrast);
  font-weight: 800;
  cursor: pointer;
}

.canvas-world {
  position: absolute;
  top: 0;
  left: 0;
  width: 1px;
  height: 1px;
  transform-origin: 0 0;
}

.canvas-edge-layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 1px;
  height: 1px;
  overflow: visible;
  pointer-events: none;
  z-index: 1;
}

.canvas-edge-path {
  fill: none;
  stroke: rgba(255, 171, 39, 0.78);
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 8 8;
  filter: drop-shadow(0 5px 10px rgba(124, 82, 25, 0.18));
}

.canvas-edge-arrow {
  fill: rgba(255, 171, 39, 0.9);
}

.canvas-edge-marker {
  position: absolute;
  z-index: 22;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 76px;
  height: 28px;
  padding: 0 10px;
  border: 1px solid rgba(255, 171, 39, 0.36);
  border-radius: 999px;
  background: rgba(var(--theme-surface-strong-rgb), 0.94);
  color: var(--theme-title);
  box-shadow: 0 10px 24px rgba(90, 61, 28, 0.16);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  pointer-events: auto;
  white-space: nowrap;
  translate: 0 -50%;
  transition:
    transform 0.18s ease,
    border-color 0.18s ease,
    color 0.18s ease;
}

.canvas-edge-marker:hover {
  border-color: rgba(255, 171, 39, 0.68);
  color: var(--theme-accent-text);
  transform: translateY(-1px);
}

.canvas-edge-marker-compact {
  min-width: 58px;
  height: 24px;
  opacity: 0.72;
  font-size: 11px;
}

.canvas-node-toolbar {
  position: absolute;
  z-index: 52;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px;
  border-radius: 14px;
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-strong));
  border: 1px solid var(--theme-panel-border-strong);
  box-shadow: 0 12px 24px var(--theme-card-shadow-strong);
  transform: translateY(-100%);

  :deep(.ant-tooltip-open),
  :deep(.ant-tooltip-disabled-compatible-wrapper) {
    display: inline-flex;
  }

  button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    border: 0;
    border-radius: 10px;
    background: transparent;
    color: var(--theme-title);
    cursor: pointer;
    transition:
      background 0.2s ease,
      color 0.2s ease,
      transform 0.2s ease;
  }

  button:hover:not(:disabled) {
    background: var(--theme-panel-bg-muted);
    color: var(--theme-accent-text-hover);
    transform: translateY(-1px);
  }

  button:disabled {
    cursor: not-allowed;
    opacity: 0.48;
  }

  button.danger {
    color: #c85a49;
  }

  button.danger:hover {
    background: rgba(200, 90, 73, 0.12);
    color: #b84b3b;
  }
}

.canvas-node-toolbar-divider {
  width: 1px;
  height: 20px;
  background: var(--theme-panel-border);
}

.canvas-node {
  position: absolute;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 0;
  border-radius: 22px;
  border: 1px solid rgba(255, 171, 39, 0.32);
  background: rgba(var(--theme-surface-strong-rgb), 0.92);
  box-shadow: 0 18px 42px rgba(90, 61, 28, 0.18);
  cursor: grab;
  user-select: none;
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease;

  &:active {
    cursor: grabbing;
  }

  &:hover {
    border-color: var(--theme-accent);
    box-shadow:
      0 20px 46px rgba(90, 61, 28, 0.2),
      0 0 0 3px color-mix(in srgb, var(--theme-accent) 16%, transparent);
  }

  &.failed {
    border-color: rgba(220, 72, 62, 0.45);
  }

  &.uploading {
    border-color: rgba(255, 171, 39, 0.58);
  }

  &.upload-failed {
    border-color: rgba(220, 72, 62, 0.58);
  }

  &.selected {
    border-color: var(--theme-accent);
    box-shadow:
      0 18px 42px rgba(90, 61, 28, 0.18),
      0 0 0 3px rgba(255, 171, 39, 0.2);
  }
}

.canvas-node::after {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 4;
  border-radius: inherit;
  border: 3px solid var(--theme-accent);
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.34),
    inset 0 0 28px color-mix(in srgb, var(--theme-accent) 20%, transparent);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.18s ease;
}

.canvas-node:hover::after,
.canvas-node.selected::after {
  opacity: 1;
}

.canvas-node-resize-handle {
  position: absolute;
  right: 8px;
  bottom: 8px;
  z-index: 5;
  width: 18px;
  height: 18px;
  border: 0;
  border-right: 3px solid rgba(255, 255, 255, 0.86);
  border-bottom: 3px solid rgba(255, 255, 255, 0.86);
  border-radius: 0 0 6px 0;
  background: transparent;
  opacity: 0;
  cursor: nwse-resize;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.28));
  transition: opacity 0.18s ease;
}

.canvas-node:hover .canvas-node-resize-handle,
.canvas-node.selected .canvas-node-resize-handle {
  opacity: 1;
}

.node-preview {
  position: relative;
  width: 100%;
  overflow: hidden;
  flex: 0 0 auto;
  min-height: 0;
  border-radius: 0;
  background: var(--theme-empty-bg);

  img {
    width: 100%;
    height: 100%;
    min-height: 0;
    display: block;
    object-fit: cover;
  }
}

.canvas-free-image-badge {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 2;
  display: inline-flex;
  align-items: center;
  height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(var(--theme-surface-strong-rgb), 0.82);
  color: var(--theme-title);
  font-size: 12px;
  font-weight: 900;
  box-shadow: 0 8px 16px var(--theme-card-shadow);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.canvas-node.uploading .canvas-free-image-badge {
  background: rgba(255, 171, 39, 0.92);
  color: #fff;
}

.canvas-node.upload-failed .canvas-free-image-badge {
  background: rgba(201, 73, 60, 0.92);
  color: #fff;
}

.node-upload-mask {
  position: absolute;
  inset: 0;
  z-index: 3;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 18px;
  background: rgba(255, 250, 242, 0.58);
  color: var(--theme-title);
  font-size: 13px;
  font-weight: 900;
  text-align: center;
  backdrop-filter: blur(5px);
  -webkit-backdrop-filter: blur(5px);
}

.node-upload-mask.error {
  background: rgba(255, 232, 226, 0.72);
  color: #c9493c;
}

.canvas-free-text-node {
  width: 100%;
  height: 100%;
  padding: 18px;
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
  color: var(--theme-title);
  font-size: 15px;
  font-weight: 800;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-soft));
}

.canvas-free-text-editor {
  width: 100%;
  height: 100%;
  padding: 18px;
  border: 0;
  outline: 0;
  resize: none;
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-soft));
  color: var(--theme-title);
  font: inherit;
  font-size: 15px;
  font-weight: 800;
  line-height: 1.55;
  white-space: pre-wrap;
}

.canvas-node.reference-selecting {
  cursor: default;
}

.canvas-node.reference-selecting .node-preview img {
  filter: brightness(0.58);
}

.canvas-reference-node-picker {
  position: absolute;
  inset: 0;
  z-index: 3;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  border: 0;
  background: rgba(0, 0, 0, 0.18);
  cursor: pointer;
}

.canvas-reference-node-picker span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 88px;
  height: 88px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.88);
  color: #111;
  font-size: 50px;
  font-weight: 300;
  line-height: 0;
  padding-bottom: 6px;
  box-shadow: 0 18px 34px rgba(0, 0, 0, 0.18);
}

.canvas-reference-node-picker.selected span {
  width: auto;
  min-width: 88px;
  padding: 0 22px;
  background: var(--theme-accent);
  color: var(--theme-accent-contrast);
  font-size: 18px;
  font-weight: 900;
}

.canvas-reference-node-picker:disabled {
  cursor: not-allowed;
}

.canvas-reference-node-picker:disabled span {
  opacity: 0.5;
}

.node-placeholder {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 0;
  height: 100%;
  padding: 18px;
  color: var(--theme-text-secondary);
  text-align: center;
}

.node-placeholder-image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.55;
}

.node-failed-image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  padding: 28px;
  background: linear-gradient(180deg, #fff2ef, #ffdcd5);
  opacity: 0.96;
}

.node-placeholder-mask {
  position: relative;
  z-index: 1;
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 16px 18px;
  border-radius: 18px;
  background: rgba(var(--theme-surface-strong-rgb), 0.68);
  color: var(--theme-text-secondary);
  font-size: 13px;
  font-weight: 700;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.node-placeholder-mask.error {
  max-width: calc(100% - 36px);
  background: linear-gradient(180deg, rgba(255, 233, 228, 0.42), rgba(255, 221, 214, 0.92));
  color: #c9493c;
  line-height: 1.45;
}

@media (max-width: 720px) {
  .canvas-page {
    height: 100vh;
    min-height: 100vh;
  }

  .canvas-stage {
    min-height: 100vh;
  }

  .canvas-workbench-actions {
    top: 58px;
    right: 12px;
    gap: 5px;
  }

  .canvas-project-switcher {
    gap: 6px;
  }

  .canvas-readonly-project-name {
    max-width: min(220px, 44vw);
  }

  .canvas-owner-trigger {
    max-width: min(180px, 38vw);
  }

  .canvas-settings {
    top: 58px;
    left: 12px;
  }

  .canvas-guide {
    left: 52px;
  }

  .canvas-settings-card {
    width: min(248px, calc(100vw - 24px));
  }

  .canvas-feedback-btn {
    height: 30px;
    padding-inline: 9px;
    font-size: 11px;
  }

  .canvas-brand-link {
    height: 32px;
    padding-right: 7px;
  }

  .canvas-brand-mark {
    width: 24px;
    height: 24px;
    border-radius: 9px;
  }

  .canvas-brand-sub {
    display: none;
  }

  .canvas-toolbar {
    top: 104px;
    left: 50%;
    right: auto;
    max-width: calc(100% - 24px);
  }

  .canvas-guide {
    top: 56px;
    left: 12px;
  }

  .canvas-guide-card {
    width: calc(100vw - 24px);
  }

  .canvas-guide-list div {
    grid-template-columns: 104px minmax(0, 1fr);
  }

  .canvas-side-toolbox-wrap {
    left: 12px;
  }

  .canvas-side-toolbox {
    padding: 7px 6px;
    border-radius: 20px;
  }

  .canvas-side-toolbox button {
    width: 32px;
    height: 32px;
    border-radius: 12px;
    font-size: 16px;
  }

  .canvas-composer-shell {
    bottom: 12px;
    left: 50%;
    width: calc(100% - 24px);
    min-width: 0;
  }

  .canvas-composer-shell.expanded {
    padding: 10px;
  }

  .canvas-composer-shell.expanded.mode-image-edit {
    height: min(210px, calc(100% - 156px));
  }

  .canvas-composer-shell.expanded.mode-text-generate {
    height: 150px;
  }

  .canvas-reference-select-tip {
    bottom: 156px;
    width: calc(100% - 24px);
    justify-content: space-between;
  }

  .composer-footer {
    flex-wrap: wrap;
  }

  .composer-options-grid {
    grid-template-columns: 1fr;
  }

  .composer-popover-card {
    left: 50%;
    width: min(420px, calc(100vw - 44px));
  }

  .composer-popover-card::after {
    left: 50%;
  }

  .composer-ratio-list {
    grid-template-columns: repeat(auto-fit, minmax(64px, 1fr));
  }

  .composer-setting-wrap {
    order: -1;
    max-width: 100%;
  }

  .composer-setting-group {
    width: 100%;
    max-width: 100%;
  }

  .composer-generate-btn {
    flex: 1 1 auto;
  }
}
</style>

<style lang="scss">
.composer-count-dropdown {
  .ant-select-item {
    border-radius: 10px;
    font-weight: 700;
  }

  .ant-select-item-option-selected {
    background: var(--theme-accent) !important;
    color: var(--theme-accent-contrast) !important;
  }
}

.canvas-rename-modal-wrap {
  .ant-modal-confirm .ant-modal-body {
    padding: 20px 22px;
  }

  .ant-modal-confirm-body {
    align-items: flex-start;
  }

  .ant-modal-confirm-title {
    font-size: 15px;
    line-height: 1.4;
  }

  .ant-modal-confirm-content {
    max-width: none;
    margin-top: 10px;
  }

  .ant-modal-confirm-btns {
    margin-top: 16px;
  }

  .ant-modal-confirm-btns .ant-btn {
    height: 32px;
    padding-inline: 12px;
    border-radius: 10px;
    font-size: 12px;
    font-weight: 700;
  }

  .canvas-rename-input.ant-input {
    width: 100%;
    height: 36px;
    margin-top: 2px;
    padding: 0 12px;
    border: 1px solid var(--theme-panel-border-strong) !important;
    border-radius: 12px !important;
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.78), rgba(255, 246, 225, 0.92)),
      var(--theme-panel-bg) !important;
    color: var(--theme-title) !important;
    box-shadow:
      inset 0 1px 0 var(--theme-panel-inset),
      0 6px 14px var(--theme-card-shadow) !important;
    font-size: 13px;
    font-weight: 700;
    line-height: 36px;
    outline: none;
    transition:
      border-color 0.2s ease,
      box-shadow 0.2s ease,
      background 0.2s ease;
  }

  .canvas-rename-input.ant-input:hover,
  .canvas-rename-input.ant-input:focus {
    border-color: var(--theme-border-strong) !important;
    background: var(--theme-panel-bg) !important;
    box-shadow:
      0 0 0 2px rgba(255, 171, 39, 0.14),
      0 8px 18px var(--theme-card-shadow) !important;
  }

  .canvas-rename-input.ant-input::placeholder {
    color: var(--theme-text-muted);
  }
}
</style>
