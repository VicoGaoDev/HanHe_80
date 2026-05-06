<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { message } from "ant-design-vue";
import dayjs from "dayjs";
import type { Dayjs } from "dayjs";
import { BarChartOutlined } from "@ant-design/icons-vue";
import { getGenerationModels } from "@/api/config";
import {
  getStats,
  getAdminAnalyticsBreakdown,
  getAdminAnalyticsSummary,
  getAdminAnalyticsTimeseries,
  getAdminHistory,
  listUsers,
} from "@/api/admin";
import AnalyticsFilterBar from "@/components/admin/AnalyticsFilterBar.vue";
import BreakdownCharts from "@/components/admin/BreakdownCharts.vue";
import KpiCards from "@/components/admin/KpiCards.vue";
import TrendCharts from "@/components/admin/TrendCharts.vue";
import type {
  AdminAnalyticsBreakdown,
  AdminAnalyticsGranularity,
  AdminAnalyticsQuery,
  AdminAnalyticsSummary,
  AdminAnalyticsTimeseries,
  AdminStats,
  AdminUser,
  GenerationModelOption,
  HistoryFilter,
  HistoryItem,
  TaskMode,
  TaskSource,
} from "@/types";

const analyticsLoading = ref(false);
const statsLoading = ref(false);
const historyLoading = ref(false);
const stats = ref<AdminStats | null>(null);
const summary = ref<AdminAnalyticsSummary | null>(null);
const timeseries = ref<AdminAnalyticsTimeseries | null>(null);
const breakdown = ref<AdminAnalyticsBreakdown | null>(null);
const users = ref<AdminUser[]>([]);
const generationModels = ref<GenerationModelOption[]>([]);
const history = ref<HistoryItem[]>([]);
const historyTotal = ref(0);
const historyCreditTotal = ref(0);
const page = ref(1);
const granularity = ref<AdminAnalyticsGranularity>("day");
const preset = ref("7d");
const ready = ref(false);

const filters = reactive<{
  status: string | undefined;
  user_id: string | undefined;
  source: TaskSource | undefined;
  model: string | undefined;
  mode: TaskMode | undefined;
  dateRange: [Dayjs, Dayjs] | null;
}>({
  status: undefined,
  user_id: undefined,
  source: undefined,
  model: undefined,
  mode: undefined,
  dateRange: null,
});

const columns = [
  { title: "ID", dataIndex: "task_id", width: 70 },
  { title: "用户", dataIndex: "username", width: 150 },
  { title: "来源", dataIndex: "source", width: 90 },
  { title: "类型", dataIndex: "mode", width: 100 },
  { title: "模型", dataIndex: "model", width: 120 },
  { title: "消耗积分", dataIndex: "credit_cost", width: 110 },
  { title: "提示词", dataIndex: "prompt", width: 220, ellipsis: true },
  { title: "状态", dataIndex: "status", width: 90 },
  { title: "图片", key: "imgCount", width: 70 },
  { title: "时间", dataIndex: "created_at", width: 180 },
];

const modelOptions = computed(() => {
  const options = generationModels.value.map((item) => ({
    label: item.model_label,
    value: item.model_key,
  }));
  options.push({ label: "局部重绘", value: "inpaint" });
  options.push({ label: "提示词反推", value: "提示词反推" });
  return options;
});

const activeFilterSummary = computed(() => {
  const chips: string[] = [];
  if (filters.user_id) {
    const user = users.value.find((item) => item.id === filters.user_id);
    if (user) chips.push(`用户：${user.username}`);
  }
  if (filters.source) chips.push(`来源：${sourceLabel(filters.source)}`);
  if (filters.mode) chips.push(`类型：${modeLabel(filters.mode)}`);
  if (filters.model) chips.push(`模型：${modelLabel(filters.model)}`);
  if (filters.status) chips.push(`状态：${statusLabel(filters.status)}`);
  if (filters.dateRange) {
    chips.push(
      `${filters.dateRange[0].format("YYYY-MM-DD")} ~ ${filters.dateRange[1].format("YYYY-MM-DD")}`,
    );
  }
  if (!chips.length && summary.value) chips.push(`统计范围：${summary.value.current_range_label}`);
  return chips;
});

const overviewStats = computed(() => {
  if (!stats.value) return [];
  return [
    {
      key: "total_tasks",
      label: "所有时间总任务数",
      value: stats.value.total_tasks,
      desc: "累计发起的全部任务数量（含提示词反推）",
      color: "#1890ff",
    },
    {
      key: "total_credit_cost",
      label: "所有时间总积分消耗",
      value: stats.value.total_credit_cost,
      desc: "累计任务实际扣减的积分总量（含提示词反推）",
      color: "#722ed1",
    },
    {
      key: "active_users",
      label: "近 7 天活跃用户",
      value: stats.value.active_users,
      desc: "按最近 7 天内发起任务或提示词反推计算",
      color: "#13c2c2",
    },
    {
      key: "total_users",
      label: "总用户数",
      value: stats.value.total_users,
      desc: "当前系统内非超级管理员用户",
      color: "#fa8c16",
    },
  ];
});

const filterSignature = computed(() => JSON.stringify({
  granularity: granularity.value,
  preset: preset.value,
  status: filters.status || null,
  user_id: filters.user_id || null,
  source: filters.source || null,
  model: filters.model || null,
  mode: filters.mode || null,
  start: filters.dateRange?.[0]?.valueOf() || null,
  end: filters.dateRange?.[1]?.valueOf() || null,
}));

function defaultPresetByGranularity(value: AdminAnalyticsGranularity) {
  if (value === "week") return "8w";
  if (value === "month") return "6m";
  return "3d";
}

function applyPresetRange(value: string) {
  const now = dayjs();
  if (value === "3d") {
    filters.dateRange = [now.subtract(2, "day").startOf("day"), now.endOf("day")];
    return;
  }
  if (value === "30d") {
    filters.dateRange = [now.subtract(29, "day").startOf("day"), now.endOf("day")];
    return;
  }
  if (value === "8w") {
    filters.dateRange = [now.subtract(7, "week").startOf("day"), now.endOf("day")];
    return;
  }
  if (value === "12w") {
    filters.dateRange = [now.subtract(11, "week").startOf("day"), now.endOf("day")];
    return;
  }
  if (value === "6m") {
    filters.dateRange = [now.subtract(5, "month").startOf("day"), now.endOf("day")];
    return;
  }
  if (value === "12m") {
    filters.dateRange = [now.subtract(11, "month").startOf("day"), now.endOf("day")];
    return;
  }
  filters.dateRange = [now.subtract(2, "day").startOf("day"), now.endOf("day")];
}

function buildAnalyticsQuery(): AdminAnalyticsQuery {
  return {
    granularity: granularity.value,
    status: filters.status,
    user_id: filters.user_id,
    source: filters.source,
    model: filters.model,
    mode: filters.mode,
    start_date: filters.dateRange?.[0].startOf("day").toISOString(),
    end_date: filters.dateRange?.[1].endOf("day").toISOString(),
  };
}

function buildHistoryFilter(): HistoryFilter {
  return {
    status: filters.status,
    user_id: filters.user_id,
    source: filters.source,
    model: filters.model,
    mode: filters.mode,
    start_date: filters.dateRange?.[0].startOf("day").toISOString(),
    end_date: filters.dateRange?.[1].endOf("day").toISOString(),
  };
}

async function loadUsers() {
  try {
    users.value = (await listUsers()).filter((item) => !item.is_whitelisted);
  } catch {
    users.value = [];
  }
}

async function loadModels() {
  try {
    generationModels.value = await getGenerationModels();
  } catch {
    generationModels.value = [];
  }
}

async function loadAnalytics() {
  analyticsLoading.value = true;
  try {
    const query = buildAnalyticsQuery();
    const [summaryRes, timeseriesRes, breakdownRes] = await Promise.all([
      getAdminAnalyticsSummary(query),
      getAdminAnalyticsTimeseries(query),
      getAdminAnalyticsBreakdown(query),
    ]);
    summary.value = summaryRes;
    timeseries.value = timeseriesRes;
    breakdown.value = breakdownRes;
  } catch {
    message.error("获取统计分析失败");
  } finally {
    analyticsLoading.value = false;
  }
}

async function loadStatsData() {
  statsLoading.value = true;
  try {
    stats.value = await getStats();
  } catch {
    message.error("获取概览统计失败");
  } finally {
    statsLoading.value = false;
  }
}

async function loadHistory() {
  historyLoading.value = true;
  try {
    const res = await getAdminHistory(page.value, 10, buildHistoryFilter());
    history.value = res.items;
    historyTotal.value = res.total;
    historyCreditTotal.value = res.total_credit_cost;
  } catch {
    message.error("获取任务记录失败");
  } finally {
    historyLoading.value = false;
  }
}

async function loadPageData() {
  await Promise.all([loadAnalytics(), loadHistory()]);
}

function handleReset() {
  filters.status = undefined;
  filters.user_id = undefined;
  filters.source = undefined;
  filters.model = undefined;
  filters.mode = undefined;
  preset.value = defaultPresetByGranularity(granularity.value);
  applyPresetRange(preset.value);
}

function handleGranularityChange(value: AdminAnalyticsGranularity) {
  granularity.value = value;
  preset.value = defaultPresetByGranularity(value);
  applyPresetRange(preset.value);
}

function handlePresetChange(value: string) {
  preset.value = value;
  applyPresetRange(value);
}

function handlePageChange(nextPage: number) {
  page.value = nextPage;
  loadHistory();
}

function handleBucketClick(payload: { start?: string | null; end?: string | null }) {
  if (!payload.start || !payload.end) return;
  filters.dateRange = [dayjs(payload.start), dayjs(payload.end)];
  preset.value = "custom";
}

function handleBreakdownFilter(payload: { type: "status" | "source" | "mode" | "model" | "user"; value: string }) {
  if (payload.type === "status") filters.status = payload.value;
  if (payload.type === "source") filters.source = payload.value as TaskSource;
  if (payload.type === "mode") filters.mode = payload.value as TaskMode;
  if (payload.type === "model") filters.model = payload.value;
  if (payload.type === "user") {
    const matchedUser = users.value.find((item) => item.username === payload.value);
    if (matchedUser) filters.user_id = matchedUser.id;
  }
}

function fmtTime(value: string) {
  return value ? dayjs(value).format("YYYY-MM-DD HH:mm:ss") : "-";
}

function modeLabel(value: string) {
  if (value === "inpaint") return "局部重绘";
  if (value === "promptReverse") return "提示词反推";
  return "生图";
}

function sourceLabel(value: string) {
  if (value === "app") return "App";
  return "Web";
}

function modelLabel(value: string) {
  if (!value) return "-";
  return modelOptions.value.find((item) => item.value === value)?.label || value;
}

function statusLabel(value: string) {
  const map: Record<string, string> = {
    pending: "等待中",
    processing: "处理中",
    success: "成功",
    failed: "失败",
  };
  return map[value] || value;
}

function statusColor(value: string) {
  if (value === "success") return "green";
  if (value === "failed") return "red";
  if (value === "processing") return "orange";
  return "default";
}

onMounted(async () => {
  preset.value = defaultPresetByGranularity(granularity.value);
  applyPresetRange(preset.value);
  await Promise.all([loadUsers(), loadModels()]);
  await Promise.all([loadPageData(), loadStatsData()]);
  ready.value = true;
});

watch(filterSignature, async () => {
  if (!ready.value) return;
  page.value = 1;
  await loadPageData();
});
</script>

<template>
  <div class="warm-page motion-page-enter">
    <div class="warm-page-header motion-fade-up" style="--motion-delay: 40ms">
      <div class="warm-page-heading">
        <div class="warm-page-icon">
          <BarChartOutlined />
        </div>
        <div>
          <div class="warm-page-title">数据统计</div>
          <div class="warm-page-desc">查看日、周、月趋势对比，了解任务、用户和积分消耗的整体情况。</div>
        </div>
      </div>
      <div v-if="summary" class="page-period-meta">
        <span class="page-period-chip">当前周期：{{ summary.current_range_label }}</span>
        <span class="page-period-chip">对比周期：{{ summary.previous_range_label }}</span>
      </div>
    </div>

    <AnalyticsFilterBar
      :users="users"
      :model-options="modelOptions"
      :filters="filters"
      :granularity="granularity"
      :preset="preset"
      :loading="analyticsLoading || historyLoading"
      @update:granularity="handleGranularityChange"
      @preset-change="handlePresetChange"
      @reset="handleReset"
    />

    <section class="dashboard-section">
      <div class="section-title-row">
        <h3 class="section-title">固定概览</h3>
        <span class="section-tip">这一组为固定口径统计，不随当前筛选条件变化。</span>
      </div>
      <a-spin :spinning="statsLoading">
        <div class="overview-grid">
          <div
            v-for="(item, index) in overviewStats"
            :key="item.key"
            class="overview-card warm-card motion-card-lift motion-fade-up"
            :style="{ '--motion-delay': `${160 + Math.min(index, 5) * 40}ms` }"
          >
            <div class="overview-card-head">
              <span class="overview-card-label">{{ item.label }}</span>
              <span class="overview-card-dot" :style="{ background: item.color }" />
            </div>
            <div class="overview-card-value" :style="{ color: item.color }">{{ item.value }}</div>
            <div class="overview-card-desc">{{ item.desc }}</div>
          </div>
        </div>
      </a-spin>
    </section>

    <section class="dashboard-section">
      <div class="section-title-row">
        <h3 class="section-title">核心指标</h3>
        <span class="section-kicker">Overview</span>
      </div>
      <KpiCards :summary="summary" :loading="analyticsLoading" />
    </section>

    <section class="dashboard-section">
      <div class="section-title-row">
        <h3 class="section-title">趋势分析</h3>
        <span class="section-tip">点击图表任意时间点可直接下钻到该时间范围明细。</span>
      </div>
      <div class="section-filter-chips">
        <span v-for="item in activeFilterSummary" :key="item" class="section-filter-chip">{{ item }}</span>
      </div>
      <TrendCharts :data="timeseries" :loading="analyticsLoading" @bucket-click="handleBucketClick" />
    </section>

    <section class="dashboard-section">
      <div class="section-title-row">
        <h3 class="section-title">结构分布</h3>
        <span class="section-tip">点击占比或排行图可自动带筛选查看记录。</span>
      </div>
      <div class="section-filter-chips">
        <span v-for="item in activeFilterSummary" :key="item" class="section-filter-chip">{{ item }}</span>
      </div>
      <BreakdownCharts :data="breakdown" :loading="analyticsLoading" @filter-click="handleBreakdownFilter" />
    </section>

    <section class="dashboard-section">
      <div class="warm-card warm-table-card motion-card-lift motion-fade-up" style="--motion-delay: 320ms">
        <div class="table-card-head">
          <div>
            <div class="table-card-title-row">
              <h3 class="section-title">全部任务记录</h3>
              <span class="section-kicker">Details</span>
            </div>
            <div class="table-card-desc">当前图表与筛选条件对应的任务与提示词反推明细。</div>
          </div>
          <div class="history-summary">
            <span class="history-summary-chip">筛选结果 {{ historyTotal }} 条</span>
            <span class="history-summary-chip">总消耗积分 {{ historyCreditTotal }}</span>
          </div>
        </div>

        <a-table
          :columns="columns"
          :data-source="history"
          :loading="historyLoading"
          :row-key="(record: HistoryItem) => record.display_id || record.task_id"
          :pagination="false"
          sticky
          :scroll="{ x: 1200, y: 560 }"
          class="admin-mobile-table"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.dataIndex === 'username'">
              <div class="table-user-cell">
                <a-avatar :size="30" :src="record.avatar_url || undefined" class="table-user-avatar">
                  {{ record.username?.charAt(0)?.toUpperCase() }}
                </a-avatar>
                <span>{{ record.username || "-" }}</span>
              </div>
            </template>
            <template v-else-if="column.dataIndex === 'task_id'">
              {{ record.display_id || record.task_id }}
            </template>
            <template v-else-if="column.dataIndex === 'mode'">
              {{ modeLabel(record.mode) }}
            </template>
            <template v-else-if="column.dataIndex === 'source'">
              {{ sourceLabel(record.source) }}
            </template>
            <template v-else-if="column.dataIndex === 'prompt'">
              {{ record.prompt || "-" }}
            </template>
            <template v-else-if="column.dataIndex === 'model'">
              {{ modelLabel(record.model) }}
            </template>
            <template v-else-if="column.dataIndex === 'status'">
              <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
            </template>
            <template v-else-if="column.key === 'imgCount'">
              {{ record.images.length }}
            </template>
            <template v-else-if="column.dataIndex === 'created_at'">
              {{ fmtTime(record.created_at) }}
            </template>
          </template>
        </a-table>
      </div>

      <div v-if="historyTotal > 10" class="warm-pagination">
        <a-pagination
          :current="page"
          :total="historyTotal"
          :page-size="10"
          show-less-items
          @change="handlePageChange"
        />
      </div>
    </section>
  </div>
</template>

<style scoped lang="scss">
.dashboard-section + .dashboard-section {
  margin-top: 18px;
}

.dashboard-section {
  padding-top: 2px;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}

.overview-card {
  min-height: 116px;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  justify-content: space-between;
}

.overview-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.overview-card-label {
  color: #8c7458;
  font-size: 13px;
  font-weight: 700;
}

.overview-card-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  box-shadow: 0 0 0 4px rgba(255, 193, 90, 0.14);
}

.overview-card-value {
  font-size: 30px;
  line-height: 1.1;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.overview-card-desc {
  color: #9a805b;
  font-size: 12px;
  line-height: 1.5;
}

.section-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  flex-wrap: wrap;
  padding: 0 2px;
}

.section-title {
  font-size: 16px;
  font-weight: 700;
  color: #5d4526;
  margin: 0;
  position: relative;
  padding-left: 14px;

  &::before {
    content: "";
    position: absolute;
    left: 0;
    top: 50%;
    transform: translateY(-50%);
    width: 6px;
    height: 18px;
    border-radius: 999px;
    background: linear-gradient(180deg, #ffc45b, #ffab25);
    box-shadow: 0 6px 12px rgba(255, 169, 37, 0.24);
  }
}

.section-kicker {
  flex-shrink: 0;
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(255, 245, 223, 0.9);
  color: #a07d49;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.section-tip,
.page-period-meta,
.history-summary {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  font-size: 13px;
  color: #8c7458;
}

.section-filter-chips {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin: -2px 2px 12px;
}

.section-filter-chip {
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  color: #8c7458;
  background: rgba(255, 253, 248, 0.92);
  border: 1px solid rgba(240, 223, 190, 0.95);
}

.page-period-meta {
  justify-content: flex-end;
}

.page-period-chip,
.history-summary-chip {
  padding: 7px 12px;
  border-radius: 999px;
  background: rgba(255, 253, 248, 0.92);
  border: 1px solid rgba(240, 223, 190, 0.95);
  box-shadow: 0 10px 18px rgba(236, 185, 88, 0.08);
}

.table-card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 14px;
  padding: 18px 20px 14px;
  border-bottom: 1px solid rgba(240, 223, 190, 0.9);
  background: linear-gradient(180deg, rgba(255, 250, 240, 0.88), rgba(255, 255, 255, 0.2));
}

.table-card-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.table-card-desc {
  margin-top: 8px;
  color: #9a805b;
  font-size: 12px;
  line-height: 1.5;
}

.table-user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--theme-title);
  font-weight: 700;
}

.table-user-avatar {
  background: linear-gradient(180deg, var(--theme-brand-bg-start), var(--theme-brand-bg-end));
  color: var(--theme-accent-contrast);
  font-weight: 700;
}

:deep(.admin-mobile-table .ant-table-header) {
  position: sticky;
  top: 0;
  z-index: 2;
}

:deep(.admin-mobile-table .ant-table-thead > tr > th) {
  background: var(--theme-table-head-bg);
  color: var(--theme-title);
  font-weight: 700;
  border-bottom: 1px solid var(--theme-border);
}

:deep(.admin-mobile-table .ant-table-body) {
  scrollbar-width: thin;
}

@media (max-width: 768px) {
  :deep(.admin-mobile-table .ant-table-content) {
    overflow-x: auto !important;
  }

  .page-period-meta {
    justify-content: flex-start;
  }

  .table-card-head {
    flex-direction: column;
    padding: 16px;
  }
}
</style>
