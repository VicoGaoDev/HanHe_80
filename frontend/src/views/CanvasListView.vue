<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { message, Modal } from "ant-design-vue";
import dayjs from "dayjs";
import { useRoute, useRouter } from "vue-router";
import {
  AppstoreOutlined,
  DeleteOutlined,
  EditOutlined,
  MoreOutlined,
  PlusOutlined,
  SearchOutlined,
} from "@ant-design/icons-vue";
import { createCanvas, deleteCanvas, listCanvases, updateCanvas } from "@/api/canvases";
import type { UserCanvasSummary } from "@/types";

const router = useRouter();
const route = useRoute();
const loading = ref(false);
const creating = ref(false);
const canvases = ref<UserCanvasSummary[]>([]);
const canvasSearchKeyword = ref("");
const renameDialogOpen = ref(false);
const renameSaving = ref(false);
const renameTarget = ref<UserCanvasSummary | null>(null);
const renameName = ref("");

const filteredCanvases = computed(() => {
  const keyword = canvasSearchKeyword.value.trim().toLowerCase();
  if (!keyword) return canvases.value;
  return canvases.value.filter((canvas) => canvas.name.toLowerCase().includes(keyword));
});

function formatCanvasTime(value?: string | null) {
  if (!value) return "暂无更新";
  const target = dayjs(value);
  const diffDays = dayjs().diff(target, "day");
  if (diffDays <= 0) return "今天";
  if (diffDays < 7) return `${diffDays}天前`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}周前`;
  return target.format("YYYY-MM-DD");
}

async function loadCanvases(options: { autoOpenSingle?: boolean } = {}) {
  loading.value = true;
  try {
    canvases.value = (await listCanvases()).items;
    if (options.autoOpenSingle && canvases.value.length === 1) {
      openCanvas(canvases.value[0]);
    }
  } catch {
    message.error("获取画布列表失败");
  } finally {
    loading.value = false;
  }
}

function openCanvas(canvas: UserCanvasSummary) {
  router.push(`/canvas/${canvas.project_id}`);
}

async function handleCreateCanvas() {
  if (creating.value) return;
  creating.value = true;
  try {
    const canvas = await createCanvas();
    canvases.value = [canvas, ...canvases.value];
    message.success("画布已创建");
    openCanvas(canvas);
  } catch {
    message.error("创建画布失败");
  } finally {
    creating.value = false;
  }
}

function openRenameDialog(canvas: UserCanvasSummary) {
  renameTarget.value = canvas;
  renameName.value = canvas.name;
  renameDialogOpen.value = true;
}

async function submitRenameCanvas() {
  const target = renameTarget.value;
  if (!target) return;
  const nextName = renameName.value.trim();
  if (!nextName) {
    message.warning("画布名称不能为空");
    return;
  }
  if (nextName === target.name) {
    renameDialogOpen.value = false;
    return;
  }
  renameSaving.value = true;
  try {
    await updateCanvas(target.project_id, { name: nextName });
    message.success("画布已重命名");
    renameDialogOpen.value = false;
    await loadCanvases();
  } catch {
    message.error("重命名失败");
  } finally {
    renameSaving.value = false;
  }
}

function handleDeleteCanvas(canvas: UserCanvasSummary) {
  Modal.confirm({
    title: `删除画布「${canvas.name}」？`,
    content: "删除后，该画布和其中的任务会从画布列表移除。",
    centered: true,
    okText: "删除",
    okType: "danger",
    cancelText: "取消",
    async onOk() {
      try {
        await deleteCanvas(canvas.project_id);
        message.success("画布已删除");
        await loadCanvases();
      } catch {
        message.error("删除画布失败");
      }
    },
  });
}

function lockCanvasCardLeaveSize(el: Element) {
  const element = el as HTMLElement;
  const { width, height } = element.getBoundingClientRect();
  element.style.width = `${width}px`;
  element.style.height = `${height}px`;
}

onMounted(() => loadCanvases({ autoOpenSingle: route.query.fromWorkbench !== "1" }));
</script>

<template>
  <div class="warm-page canvas-list-page">
    <div class="canvas-list-topbar">
      <div class="warm-page-heading">
        <div class="warm-page-icon canvas-list-topbar-icon">
          <AppstoreOutlined />
        </div>
        <div>
          <div class="warm-page-title canvas-list-topbar-title">画布列表</div>
          <div class="warm-page-desc">选择一个画布进入工作台，继续创作和整理你的生成任务。</div>
        </div>
      </div>
      <div class="canvas-list-topbar-actions">
        <a-input
          v-model:value="canvasSearchKeyword"
          class="canvas-list-search"
          placeholder="搜索画布名称"
          allow-clear
        >
          <template #prefix>
            <SearchOutlined />
          </template>
        </a-input>
        <div class="canvas-list-topbar-meta">
          共 {{ canvases.length }} 个画布
        </div>
      </div>
    </div>

    <a-spin :spinning="loading">
      <TransitionGroup
        name="canvas-card-list"
        tag="div"
        class="canvas-list-grid"
        @before-leave="lockCanvasCardLeaveSize"
      >
        <button
          key="create"
          class="canvas-list-card canvas-list-card-create warm-card"
          type="button"
          :disabled="creating"
          @click="handleCreateCanvas"
        >
          <div class="canvas-list-create-icon">
            <PlusOutlined />
          </div>
          <div class="canvas-list-card-title">新建画布</div>
          <div class="canvas-list-card-desc">创建一个新的无限画布空间</div>
        </button>

        <article
          v-for="canvas in filteredCanvases"
          :key="canvas.project_id"
          class="canvas-list-card warm-card"
          @click="openCanvas(canvas)"
        >
          <div class="canvas-list-preview" :class="{ empty: !canvas.preview_urls.length }">
            <template v-if="canvas.preview_urls.length">
              <img class="canvas-list-preview-main" :src="canvas.preview_urls[0]" alt="" />
              <div class="canvas-list-preview-side">
                <img v-if="canvas.preview_urls[1]" :src="canvas.preview_urls[1]" alt="" />
                <img v-if="canvas.preview_urls[2]" :src="canvas.preview_urls[2]" alt="" />
              </div>
            </template>
            <template v-else>
              <div class="canvas-list-preview-skeleton canvas-list-preview-skeleton-main"></div>
              <div class="canvas-list-preview-skeleton-side">
                <div class="canvas-list-preview-skeleton"></div>
                <div class="canvas-list-preview-skeleton"></div>
              </div>
            </template>
          </div>

          <div class="canvas-list-card-body">
            <div class="canvas-list-card-heading">
              <div>
                <div class="canvas-list-card-title">{{ canvas.name }}</div>
                <div class="canvas-list-card-desc">{{ canvas.node_count }} 个节点 · {{ formatCanvasTime(canvas.updated_at) }}</div>
              </div>
              <a-dropdown trigger="click" @click.stop>
                <button class="canvas-list-more-btn" type="button" @click.stop>
                  <MoreOutlined />
                </button>
                <template #overlay>
                  <a-menu>
                    <a-menu-item key="rename" @click="openRenameDialog(canvas)">
                      <EditOutlined /> 重命名
                    </a-menu-item>
                    <a-menu-item key="delete" danger @click="handleDeleteCanvas(canvas)">
                      <DeleteOutlined /> 删除
                    </a-menu-item>
                  </a-menu>
                </template>
              </a-dropdown>
            </div>
          </div>
        </article>
      </TransitionGroup>
    </a-spin>

    <a-modal
      v-model:open="renameDialogOpen"
      title="重命名画布"
      centered
      :confirm-loading="renameSaving"
      ok-text="保存"
      cancel-text="取消"
      @ok="submitRenameCanvas"
    >
      <a-input
        v-model:value="renameName"
        placeholder="请输入画布名称"
        :maxlength="100"
        show-count
        @press-enter="submitRenameCanvas"
      />
    </a-modal>
  </div>
</template>

<style scoped lang="scss">
.canvas-list-page {
  padding-bottom: 42px;
}

.canvas-list-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 18px;
}

.canvas-list-topbar-icon {
  background: linear-gradient(135deg, var(--theme-panel-bg-soft), var(--theme-panel-bg-strong));
  color: var(--theme-accent-text);
}

.canvas-list-topbar-title {
  font-size: 19px;
  line-height: 1.3;
}

.canvas-list-topbar-actions {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.canvas-list-search {
  width: 220px;
}

.canvas-list-search :deep(.ant-input-affix-wrapper) {
  border-color: var(--theme-control-border);
}

.canvas-list-topbar-meta {
  color: var(--theme-text-secondary);
  font-size: 13px;
  white-space: nowrap;
}

.canvas-list-grid {
  position: relative;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 18px;
}

.canvas-card-list-move,
.canvas-card-list-enter-active,
.canvas-card-list-leave-active {
  transition:
    transform 0.28s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.22s ease,
    box-shadow 0.18s ease;
}

.canvas-card-list-enter-from,
.canvas-card-list-leave-to {
  opacity: 0;
  transform: scale(0.96) translateY(8px);
}

.canvas-card-list-leave-active {
  position: absolute;
  z-index: 0;
  pointer-events: none;
}

.canvas-list-card {
  aspect-ratio: 1 / 1;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--theme-panel-border);
  border-radius: 14px;
  padding: 0;
  overflow: hidden;
  background: var(--theme-panel-bg);
  text-align: left;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.canvas-list-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 18px 42px var(--theme-card-shadow-strong);
}

.canvas-list-card-create {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 12px;
  border: 1px dashed var(--theme-panel-border-strong);
  background: var(--theme-panel-bg-soft);
}

.canvas-list-card-create:disabled {
  cursor: wait;
  opacity: 0.7;
}

.canvas-list-create-icon {
  width: 54px;
  height: 54px;
  display: grid;
  place-items: center;
  border-radius: 18px;
  margin-bottom: 14px;
  color: var(--theme-accent-text);
  background: var(--theme-control-hover-bg);
  font-size: 24px;
}

.canvas-list-preview {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr 74px;
  gap: 3px;
  overflow: hidden;
  border-radius: 13px 13px 0 0;
  background: var(--theme-panel-bg-muted);
}

.canvas-list-preview.empty {
  display: grid;
  grid-template-columns: 1fr 74px;
  gap: 3px;
  background: var(--theme-empty-bg);
}

.canvas-list-preview-skeleton {
  min-width: 0;
  min-height: 0;
  border: 0.5px solid var(--theme-panel-border);
  background: var(--theme-panel-bg);
}

.canvas-list-preview-skeleton-main {
  height: 100%;
}

.canvas-list-preview-skeleton-side {
  display: grid;
  grid-template-rows: 1fr 1fr;
  gap: 3px;
}

.canvas-list-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.canvas-list-preview-side {
  display: grid;
  grid-template-rows: 1fr 1fr;
  gap: 3px;
}

.canvas-list-card-body {
  flex: 0 0 auto;
  padding: 10px 12px 11px;
}

.canvas-list-card-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.canvas-list-card-title {
  color: var(--theme-title);
  font-size: 14px;
  line-height: 1.35;
  font-weight: 800;
}

.canvas-list-card-desc {
  margin-top: 3px;
  color: var(--theme-text-secondary);
  font-size: 12px;
  line-height: 1.35;
}

.canvas-list-more-btn {
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 50%;
  color: var(--theme-text-secondary);
  background: transparent;
  cursor: pointer;
  font-size: 16px;
}

.canvas-list-more-btn:hover {
  background: var(--theme-control-hover-bg);
}

@media (max-width: 720px) {
  .canvas-list-topbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .canvas-list-topbar-actions {
    width: 100%;
    align-items: stretch;
    flex-direction: column;
  }

  .canvas-list-search {
    width: 100%;
  }
}
</style>
