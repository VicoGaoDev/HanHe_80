<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { message, Modal } from "ant-design-vue";
import dayjs from "dayjs";
import { useRouter } from "vue-router";
import {
  AppstoreOutlined,
  DeleteOutlined,
  EditOutlined,
  MoreOutlined,
  PlusOutlined,
  SearchOutlined,
} from "@ant-design/icons-vue";
import { createCanvas, deleteCanvas, listCanvases, updateCanvas } from "@/api/canvases";
import { getAdminCanvases, listUsers } from "@/api/admin";
import { withApiBaseUrl } from "@/lib/assets";
import type { AdminUser, UserCanvasSummary } from "@/types";

const props = withDefaults(defineProps<{
  adminCanvases?: boolean;
}>(), {
  adminCanvases: false,
});

const router = useRouter();
const loading = ref(false);
const creating = ref(false);
const canvases = ref<UserCanvasSummary[]>([]);
const users = ref<AdminUser[]>([]);
const canvasSearchKeyword = ref("");
const userFilter = ref<string | undefined>(undefined);
const renameDialogOpen = ref(false);
const renameSaving = ref(false);
const renameTarget = ref<UserCanvasSummary | null>(null);
const renameName = ref("");
const isAdminCanvasView = computed(() => props.adminCanvases);

const filteredCanvases = computed(() => {
  const keyword = canvasSearchKeyword.value.trim().toLowerCase();
  return canvases.value.filter((canvas) => {
    if (isAdminCanvasView.value && userFilter.value && canvas.owner_user_id !== userFilter.value) {
      return false;
    }
    if (!keyword) return true;
    return canvas.name.toLowerCase().includes(keyword);
  });
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

async function loadCanvases(options: { autoCreateWhenEmpty?: boolean } = {}) {
  loading.value = true;
  try {
    canvases.value = isAdminCanvasView.value
      ? (await getAdminCanvases()).items
      : (await listCanvases()).items;
    if (!isAdminCanvasView.value && options.autoCreateWhenEmpty && canvases.value.length === 0) {
      await handleCreateCanvas({ onboarding: true });
    }
  } catch {
    message.error(isAdminCanvasView.value ? "获取用户画布失败" : "获取画布列表失败");
  } finally {
    loading.value = false;
  }
}

async function loadAdminUsers() {
  if (!isAdminCanvasView.value) return;
  try {
    users.value = await listUsers();
  } catch {
    message.error("获取用户列表失败");
  }
}

function openCanvas(canvas: UserCanvasSummary, options: { onboarding?: boolean } = {}) {
  router.push({
    path: isAdminCanvasView.value ? `/admin/user-canvases/${canvas.project_id}` : `/canvas/${canvas.project_id}`,
    query: options.onboarding ? { onboarding: "1" } : undefined,
  });
}

async function handleCreateCanvas(options: { onboarding?: boolean } = {}) {
  if (creating.value) return;
  creating.value = true;
  try {
    const canvas = await createCanvas();
    canvases.value = [canvas, ...canvases.value];
    message.success("画布已创建");
    openCanvas(canvas, options);
  } catch {
    message.error("创建画布失败");
  } finally {
    creating.value = false;
  }
}

function handleCreateCanvasClick() {
  void handleCreateCanvas();
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

onMounted(async () => {
  await Promise.all([
    loadCanvases({ autoCreateWhenEmpty: !isAdminCanvasView.value }),
    loadAdminUsers(),
  ]);
});
</script>

<template>
  <div class="warm-page canvas-list-page">
    <div class="canvas-list-topbar">
      <div class="warm-page-heading">
        <div class="warm-page-icon canvas-list-topbar-icon">
          <AppstoreOutlined />
        </div>
        <div>
          <div class="warm-page-title canvas-list-topbar-title">{{ isAdminCanvasView ? "用户画布" : "画布列表" }}</div>
          <div class="warm-page-desc">
            {{ isAdminCanvasView ? "管理员可查看所有用户的画布项目，并进入只读工作台查看画布内容。" : "选择一个画布进入工作台，继续创作和整理你的生成任务。" }}
          </div>
        </div>
      </div>
      <div class="canvas-list-topbar-actions">
        <a-select
          v-if="isAdminCanvasView"
          v-model:value="userFilter"
          class="canvas-list-user-filter"
          placeholder="全部用户"
          allow-clear
          show-search
          option-filter-prop="label"
        >
          <a-select-option
            v-for="user in users"
            :key="user.id"
            :value="user.id"
            :label="user.username"
          >
            {{ user.username }}
          </a-select-option>
        </a-select>
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
          v-if="!isAdminCanvasView"
          key="create"
          class="canvas-list-card canvas-list-card-create warm-card"
          type="button"
          :disabled="creating"
          @click="handleCreateCanvasClick"
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
          :class="{ 'is-soft-deleted': !!canvas.is_deleted }"
          @click="openCanvas(canvas)"
        >
          <div v-if="isAdminCanvasView" class="canvas-list-owner-badge" :title="canvas.owner_username || '未知用户'">
            <a-avatar :size="22" :src="withApiBaseUrl(canvas.owner_avatar_url) || undefined" class="canvas-list-owner-avatar">
              {{ canvas.owner_username?.charAt(0)?.toUpperCase() }}
            </a-avatar>
            <span class="canvas-list-owner-name">{{ canvas.owner_username || "未知用户" }}</span>
          </div>
          <div v-if="isAdminCanvasView && canvas.is_deleted" class="canvas-list-soft-deleted-badge">
            已软删
          </div>
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
              <a-dropdown v-if="!isAdminCanvasView" trigger="click" @click.stop>
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

.canvas-list-user-filter {
  width: 180px;
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
  position: relative;
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

.canvas-list-card.is-soft-deleted {
  border-color: rgba(180, 92, 78, 0.38);
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

.canvas-list-owner-badge {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 2;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: calc(100% - 24px);
  height: 34px;
  padding: 0 12px 0 7px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 999px;
  background: rgba(35, 27, 20, 0.74);
  color: #fff7eb;
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.18);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.canvas-list-owner-avatar {
  flex: 0 0 auto;
  background: var(--theme-accent);
  color: var(--theme-accent-contrast);
}

.canvas-list-owner-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 800;
}

.canvas-list-soft-deleted-badge {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 2;
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 8px;
  border: 1px solid rgba(255, 224, 220, 0.22);
  border-radius: 999px;
  background: rgba(166, 60, 47, 0.62);
  color: #fff3ef;
  font-size: 11px;
  font-weight: 800;
  box-shadow: 0 10px 20px rgba(96, 31, 22, 0.22);
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
