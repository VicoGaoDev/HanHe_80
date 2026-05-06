<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ArrowLeftOutlined, MessageOutlined } from "@ant-design/icons-vue";
import { message } from "ant-design-vue";
import dayjs from "dayjs";
import { getAdminFeedbackDetail, updateAdminFeedback } from "@/api/admin";
import type { FeedbackDetail, FeedbackStatus } from "@/types";

const route = useRoute();
const router = useRouter();
const loading = ref(false);
const saving = ref(false);
const detail = ref<FeedbackDetail | null>(null);

const form = reactive<{
  status: FeedbackStatus;
  process_note: string;
  result_note: string;
}>({
  status: "pending",
  process_note: "",
  result_note: "",
});

const feedbackId = computed(() => String(route.params.feedbackId || ""));

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

function syncForm() {
  if (!detail.value) return;
  form.status = detail.value.status;
  form.process_note = detail.value.process_note || "";
  form.result_note = detail.value.result_note || "";
}

async function load() {
  if (!feedbackId.value) return;
  loading.value = true;
  try {
    detail.value = await getAdminFeedbackDetail(feedbackId.value);
    syncForm();
  } catch {
    message.error("获取反馈详情失败");
  } finally {
    loading.value = false;
  }
}

async function handleSave() {
  if (!feedbackId.value) return;
  saving.value = true;
  try {
    detail.value = await updateAdminFeedback(feedbackId.value, {
      status: form.status,
      process_note: form.process_note,
      result_note: form.result_note,
    });
    syncForm();
    message.success("反馈处理信息已更新");
  } catch (err: any) {
    message.error(err.response?.data?.detail || "更新失败");
  } finally {
    saving.value = false;
  }
}

watch(feedbackId, () => {
  void load();
});

onMounted(load);
</script>

<template>
  <div class="warm-page motion-page-enter">
    <div class="warm-page-header motion-fade-up" style="--motion-delay: 40ms">
      <div class="warm-page-heading">
        <div class="warm-page-icon">
          <MessageOutlined />
        </div>
        <div>
          <div class="warm-page-title">Feedback 详情</div>
          <div class="warm-page-desc">查看反馈上下文并更新处理进度和最终结果。</div>
        </div>
      </div>
      <a-button class="back-btn" @click="router.push('/admin/feedbacks')">
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
              <div><span>用户</span><strong>{{ detail.username }} / {{ detail.user_id }}</strong></div>
              <div><span>任务 ID</span><strong>{{ detail.task_id }}</strong></div>
              <div><span>提交时间</span><strong>{{ formatTime(detail.created_at) }}</strong></div>
              <div><span>更新时间</span><strong>{{ formatTime(detail.updated_at) }}</strong></div>
              <div><span>处理时间</span><strong>{{ formatTime(detail.handled_at) }}</strong></div>
            </div>

            <div class="detail-block">
              <div class="detail-label">用户反馈内容</div>
              <div class="detail-text">{{ detail.content || "-" }}</div>
            </div>

            <div class="detail-block">
              <div class="detail-label">处理设置</div>
              <a-form layout="vertical">
                <a-form-item label="处理状态">
                  <a-select v-model:value="form.status">
                    <a-select-option value="pending">待处理</a-select-option>
                    <a-select-option value="processing">处理中</a-select-option>
                    <a-select-option value="completed">已完成</a-select-option>
                  </a-select>
                </a-form-item>
                <a-form-item label="处理进度">
                  <a-textarea v-model:value="form.process_note" :rows="4" :maxlength="5000" show-count />
                </a-form-item>
                <a-form-item label="处理结果" style="margin-bottom: 0">
                  <a-textarea v-model:value="form.result_note" :rows="4" :maxlength="5000" show-count />
                </a-form-item>
              </a-form>
              <div class="save-row">
                <a-button type="primary" class="warm-primary-btn" :loading="saving" @click="handleSave">保存处理结果</a-button>
              </div>
            </div>
          </div>

          <div class="warm-card detail-side motion-fade-up motion-card-lift" style="--motion-delay: 180ms">
            <div class="section-title-row">
              <h3>关联任务</h3>
            </div>
            <div class="task-meta-list">
              <div><span>模型</span><strong>{{ detail.task.model || "-" }}</strong></div>
              <div><span>类型</span><strong>{{ detail.task.mode || "-" }}</strong></div>
              <div><span>来源</span><strong>{{ detail.task.source || "-" }}</strong></div>
              <div><span>任务状态</span><strong>{{ detail.task.status || "-" }}</strong></div>
              <div><span>任务时间</span><strong>{{ formatTime(detail.task.created_at) }}</strong></div>
              <div><span>任务归属用户</span><strong>{{ detail.task_user_id || "-" }}</strong></div>
            </div>
            <div class="detail-block" style="margin-top: 18px">
              <div class="detail-label">任务提示词</div>
              <div class="detail-text">{{ detail.task.prompt || "-" }}</div>
            </div>
          </div>
        </div>
      </template>
    </a-spin>
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
  grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.65fr);
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

.detail-label {
  margin-bottom: 8px;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
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

.save-row {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}

.warm-tag {
  border-radius: 999px;
  font-weight: 600;
}

@media (max-width: 900px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .meta-grid,
  .task-meta-list {
    grid-template-columns: 1fr;
  }
}
</style>
