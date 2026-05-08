<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ArrowLeftOutlined, LoadingOutlined, MessageOutlined } from "@ant-design/icons-vue";
import { message } from "ant-design-vue";
import dayjs from "dayjs";
import { getDisplayImageUrl, getPreviewImageUrl } from "@/api/images";
import { getGenerationModels } from "@/api/config";
import { getMyFeedbackDetail } from "@/api/feedback";
import type { FeedbackDetail, FeedbackStatus, GenerationModelOption, ImageResult } from "@/types";

const route = useRoute();
const router = useRouter();
const loading = ref(false);
const detail = ref<FeedbackDetail | null>(null);
const previewVisible = ref(false);
const previewSrc = ref("");
const generationModels = ref<GenerationModelOption[]>([]);

const feedbackId = computed(() => String(route.params.feedbackId || ""));
const taskImages = computed(() => detail.value?.task.images || []);

function statusLabel(status: FeedbackStatus) {
  return {
    pending: "待处理",
    processing: "处理中",
    completed: "已完成",
  }[status];
}

function statusColor(status: FeedbackStatus) {
  return {
    pending: "gold",
    processing: "blue",
    completed: "green",
  }[status];
}

function formatTime(value?: string | null) {
  return value ? dayjs(value).format("YYYY-MM-DD HH:mm:ss") : "-";
}

function getModelLabel(model?: string) {
  if (!model) return "未设置";
  const matched = generationModels.value.find((item) => item.model_key === model);
  return matched?.model_label || matched?.display_name || model;
}

function getTaskImageSrc(image: ImageResult) {
  return getDisplayImageUrl(image);
}

function getTaskPreviewSrc(image: ImageResult) {
  return getPreviewImageUrl(image);
}

function openPreview(url: string) {
  if (!url) return;
  previewSrc.value = url;
  previewVisible.value = true;
}

async function load() {
  if (!feedbackId.value) return;
  loading.value = true;
  try {
    detail.value = await getMyFeedbackDetail(feedbackId.value);
  } catch {
    message.error("获取反馈详情失败");
  } finally {
    loading.value = false;
  }
}

async function loadGenerationModels() {
  try {
    generationModels.value = await getGenerationModels();
  } catch {
    generationModels.value = [];
  }
}

watch(feedbackId, () => {
  void load();
});

onMounted(() => {
  void load();
  void loadGenerationModels();
});
</script>

<template>
  <div class="warm-page motion-page-enter">
    <div class="warm-page-header motion-fade-up" style="--motion-delay: 40ms">
      <div class="warm-page-heading">
        <div class="warm-page-icon">
          <MessageOutlined />
        </div>
        <div>
          <div class="warm-page-title">反馈详情</div>
          <div class="warm-page-desc">查看反馈原文、当前处理进度和最终结果。</div>
        </div>
      </div>
      <a-button class="back-btn" @click="router.push('/feedbacks')">
        <template #icon><ArrowLeftOutlined /></template>
        返回列表
      </a-button>
    </div>

    <a-spin :spinning="loading">
      <template v-if="detail">
        <div class="detail-grid">
          <div class="warm-card detail-main motion-fade-up motion-card-lift" style="--motion-delay: 120ms">
            <div class="section-title-row">
              <h3>反馈信息</h3>
              <a-tag class="warm-tag" :color="statusColor(detail.status)">{{ statusLabel(detail.status) }}</a-tag>
            </div>
            <div class="meta-grid">
              <div><span>反馈编号</span><strong>{{ detail.feedback_id }}</strong></div>
              <div><span>任务 ID</span><strong>{{ detail.task_id }}</strong></div>
              <div><span>提交时间</span><strong>{{ formatTime(detail.created_at) }}</strong></div>
              <div><span>更新时间</span><strong>{{ formatTime(detail.updated_at) }}</strong></div>
              <div><span>处理人</span><strong>{{ detail.handler_name || "-" }}</strong></div>
              <div><span>处理时间</span><strong>{{ formatTime(detail.handled_at) }}</strong></div>
            </div>

            <div class="detail-block">
              <div class="detail-label">反馈内容</div>
              <div class="detail-text detail-text-emphasis">{{ detail.content || "-" }}</div>
            </div>

            <div class="note-grid">
              <div class="detail-block note-card">
                <div class="detail-label">处理进度</div>
                <div class="detail-text">{{ detail.process_note || "暂未更新处理进度" }}</div>
              </div>

              <div class="detail-block note-card">
                <div class="detail-label">处理结果</div>
                <div class="detail-text detail-text-result">{{ detail.result_note || "暂未填写处理结果" }}</div>
              </div>
            </div>
          </div>

          <div class="warm-card detail-side motion-fade-up motion-card-lift" style="--motion-delay: 180ms">
            <div class="section-title-row">
              <h3>关联任务</h3>
            </div>
            <div class="task-meta-list">
              <div><span>模型</span><strong>{{ getModelLabel(detail.task.model) }}</strong></div>
              <div><span>类型</span><strong>{{ detail.task.mode || "-" }}</strong></div>
              <div><span>来源</span><strong>{{ detail.task.source || "-" }}</strong></div>
              <div><span>任务状态</span><strong>{{ detail.task.status || "-" }}</strong></div>
              <div><span>任务时间</span><strong>{{ formatTime(detail.task.created_at) }}</strong></div>
              <div><span>结果数量</span><strong>{{ taskImages.length || 0 }} 张</strong></div>
            </div>
            <div class="detail-block" style="margin-top: 18px">
              <div class="detail-label">任务提示词</div>
              <div class="detail-text">{{ detail.task.prompt || "-" }}</div>
            </div>

            <div class="detail-block task-result-block">
              <div class="detail-label detail-label-inline">
                <span>任务结果图</span>
                <small>{{ taskImages.length ? "点击缩略图可放大" : "" }}</small>
              </div>
              <div v-if="taskImages.length" class="task-result-grid task-result-grid-compact">
                <button
                  v-for="(image, index) in taskImages"
                  :key="image.id"
                  type="button"
                  class="task-result-thumb"
                  :class="{
                    clickable: !!getTaskPreviewSrc(image),
                    pending: !getTaskImageSrc(image) && image.status !== 'failed',
                    failed: image.status === 'failed',
                  }"
                  @click="getTaskPreviewSrc(image) && openPreview(getTaskPreviewSrc(image))"
                >
                  <img
                    v-if="getTaskImageSrc(image)"
                    :src="getTaskImageSrc(image)"
                    :alt="`任务结果图 ${index + 1}`"
                    loading="lazy"
                  />
                  <div v-else-if="image.status === 'failed'" class="task-result-state task-result-state-failed compact">
                    <LoadingOutlined />
                  </div>
                  <div v-else class="task-result-state compact">
                    <a-spin size="small" />
                  </div>
                </button>
              </div>
              <a-empty v-else description="任务结果图暂未生成或已不可用" />
            </div>
          </div>
        </div>
      </template>
    </a-spin>

    <div v-if="previewVisible" style="display: none">
      <a-image
        :src="previewSrc"
        :preview="{ visible: previewVisible, onVisibleChange: (v: boolean) => (previewVisible = v) }"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.back-btn {
  border-radius: 12px;
  border-color: var(--theme-panel-border-strong);
  background: var(--theme-panel-bg-strong);
  color: var(--theme-accent-text);
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(300px, 0.7fr);
  gap: 16px;
}

.detail-main,
.detail-side {
  padding: 20px;
}

.section-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;

  h3 {
    margin: 0;
    color: var(--theme-title);
    font-size: 18px;
  }
}

.meta-grid,
.task-meta-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;

  > div {
    padding: 12px 14px;
    border-radius: 14px;
    background: var(--theme-panel-bg-soft);
    border: 1px solid var(--theme-panel-border);
  }

  span {
    display: block;
    margin-bottom: 6px;
    color: var(--text-secondary);
    font-size: 12px;
  }

  strong {
    color: var(--theme-title);
    word-break: break-word;
  }
}

.detail-block {
  margin-top: 18px;
}

.note-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 18px;
}

.note-card {
  margin-top: 0;
}

.detail-label {
  margin-bottom: 8px;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
}

.detail-label-inline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;

  small {
    color: var(--theme-text-secondary);
    font-size: 12px;
    font-weight: 500;
  }
}

.detail-text {
  padding: 14px 16px;
  border-radius: 16px;
  background: var(--theme-panel-bg-soft);
  border: 1px solid var(--theme-panel-border);
  color: var(--theme-title);
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}

.detail-text-emphasis {
  background: linear-gradient(180deg, var(--theme-panel-bg-soft), var(--theme-panel-bg-strong));
}

.detail-text-result {
  background: linear-gradient(180deg, rgba(255, 245, 222, 0.88), rgba(255, 239, 199, 0.94));
  border-color: rgba(219, 176, 81, 0.22);
}

.warm-tag {
  border-radius: 999px;
  font-weight: 600;
}

.task-result-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.task-result-grid-compact {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.task-result-thumb {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 96px;
  padding: 0;
  border: 1px solid var(--theme-panel-border);
  border-radius: 14px;
  background: var(--theme-panel-bg-soft);
  overflow: hidden;
  transition:
    transform var(--motion-duration-fast) var(--motion-ease-soft),
    border-color var(--motion-duration-fast) var(--motion-ease-soft);

  &.clickable {
    cursor: zoom-in;
  }

  &.clickable:hover {
    transform: translateY(-2px);
    border-color: var(--theme-panel-border-strong);
  }

  img {
    width: 100%;
    aspect-ratio: 1 / 1;
    object-fit: cover;
    border-radius: 0;
    background: var(--theme-empty-bg);
  }
}

.task-result-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 96px;
  width: 100%;
  padding: 12px;
  border-radius: 0;
  background: var(--theme-empty-bg);
  color: var(--theme-text-secondary);
  text-align: center;
  line-height: 1.6;
}

.task-result-state.compact {
  min-height: 96px;
  padding: 8px;
}

.task-result-state-failed {
  color: #b85d47;
}

@media (max-width: 900px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .meta-grid,
  .task-meta-list,
  .note-grid {
    grid-template-columns: 1fr;
  }

  .task-result-grid-compact {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .task-result-grid-compact {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
