<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { message } from "ant-design-vue";
import dayjs from "dayjs";
import type { Dayjs } from "dayjs";
import { BugOutlined } from "@ant-design/icons-vue";
import { getAdminErrorAnalytics, getAdminErrorCategoryTimeseries, getAdminErrorTasks, getAdminHistoryDetail } from "@/api/admin";
import { getGenerationModels, getTaskScenes } from "@/api/config";
import { isSessionExpiredError } from "@/lib/authError";
import { VChart } from "@/components/admin/charting";
import HistoryDetailDialog from "@/components/history/HistoryDetailDialog.vue";
import { formatGenerationTaskFailureMessage } from "@/lib/generationErrors";
import type {
  AdminAnalyticsGranularity,
  AdminErrorAnalytics,
  AdminErrorCategoryTimeseries,
  AdminErrorTaskItem,
  GenerationModelOption,
  TaskSceneConfig,
  UserHistoryCard,
} from "@/types";

type DatePreset = "today" | "3d" | "7d" | "30d";

const loading = ref(false);
const preset = ref<DatePreset | undefined>("today");
const dateRange = ref<[Dayjs, Dayjs] | null>(null);
const analytics = ref<AdminErrorAnalytics | null>(null);
const errorTrend = ref<AdminErrorCategoryTimeseries | null>(null);
const modelFilter = ref<string | undefined>(undefined);
const selectedErrorCategory = ref<string | undefined>(undefined);
const selectedBucketLabel = ref<string | undefined>(undefined);
const drilledDateRange = ref<[Dayjs, Dayjs] | null>(null);
const taskTableLoading = ref(false);
const taskTableItems = ref<AdminErrorTaskItem[]>([]);
const taskTableTotal = ref(0);
const taskTablePage = ref(1);
const generationModels = ref<GenerationModelOption[]>([]);
const taskScenes = ref<TaskSceneConfig[]>([]);
const detailOpen = ref(false);
const detailLoading = ref(false);
const detailItem = ref<UserHistoryCard | null>(null);
let activeDetailRequestKey = "";

const TASK_TABLE_PAGE_SIZE = 10;

const taskColumns = [
  { title: "用户", dataIndex: "username", width: 120 },
  { title: "模型", dataIndex: "model", width: 180 },
  { title: "类型", dataIndex: "task_type", width: 110 },
  { title: "来源", dataIndex: "source", width: 90 },
  { title: "状态", dataIndex: "status", width: 90 },
  { title: "错误信息", dataIndex: "error_message" },
  { title: "时间", dataIndex: "created_at", width: 168 },
  { title: "操作", key: "actions", width: 80, fixed: "right" as const },
];

const columns = [
  { title: "错误次数", dataIndex: "count", width: 120 },
  { title: "错误类别", dataIndex: "error_category", width: 200 },
  { title: "错误信息", dataIndex: "error_message" },
];

const filteredItems = computed(() => analytics.value?.items || []);

const filteredFailedTaskCount = computed(() => (
  filteredItems.value.reduce((sum, item) => sum + item.count, 0)
));

const summaryCards = computed(() => [
  {
    key: "total",
    label: selectedErrorCategory.value ? "当前钻取失败数" : "失败任务总数",
    value: selectedErrorCategory.value ? filteredFailedTaskCount.value : (analytics.value?.total_failed_tasks ?? 0),
    desc: selectedErrorCategory.value
      ? "当前选中错误类别在所选时间桶内的失败任务数量"
      : "当前时间范围内状态为失败的任务数量",
    color: "#cf3f36",
  },
  {
    key: "categories",
    label: selectedErrorCategory.value ? "已选错误类别" : "错误类别数",
    value: selectedErrorCategory.value ? 1 : (analytics.value?.distinct_error_categories ?? 0),
    desc: selectedErrorCategory.value ? "图表联动后当前锁定的错误类别" : "按错误类别聚合后的不同错误类型数量",
    color: "#d48806",
  },
  {
    key: "distinct",
    label: selectedErrorCategory.value ? "该类别原始文案数" : "原始错误文案数",
    value: filteredItems.value.length,
    desc: selectedErrorCategory.value ? "当前错误类别下去重后的原始错误文案数量" : "去重后的 error_message 原始文案数量",
    color: "#7c6cf2",
  },
]);

const trendGranularity = computed<AdminAnalyticsGranularity>(() => {
  if (!dateRange.value?.[0] || !dateRange.value?.[1]) return "day";
  const diffDays = dateRange.value[1].endOf("day").diff(dateRange.value[0].startOf("day"), "day") + 1;
  if (diffDays > 120) return "month";
  if (diffDays > 45) return "week";
  return "day";
});

const trendLabels = computed(() => errorTrend.value?.points.map((item) => item.label) || []);
const hasTrendData = computed(() => (
  (errorTrend.value?.series.length || 0) > 0
  && (errorTrend.value?.points.some((point) => point.total_failed_tasks > 0) || false)
));
const trendOption = computed(() => ({
  color: ["#cf3f36", "#d48806", "#7c6cf2", "#1890ff", "#13c2c2", "#52c41a"],
  tooltip: {
    trigger: "axis",
    backgroundColor: "rgba(76, 52, 26, 0.92)",
    borderWidth: 0,
    textStyle: { color: "#fffdf8" },
  },
  legend: { top: 0 },
  grid: { left: 40, right: 20, top: 48, bottom: 28 },
  xAxis: { type: "category", data: trendLabels.value },
  yAxis: { type: "value", minInterval: 1 },
  series: (errorTrend.value?.series || []).map((seriesItem, index) => ({
    name: `${seriesItem.error_category} (${seriesItem.total_count})`,
    type: "line",
    smooth: true,
    symbolSize: 7,
    lineStyle: {
      width: selectedErrorCategory.value === seriesItem.error_category || (!selectedErrorCategory.value && index === 0) ? 3 : 2,
      opacity: selectedErrorCategory.value && selectedErrorCategory.value !== seriesItem.error_category ? 0.35 : 1,
    },
    areaStyle: selectedErrorCategory.value === seriesItem.error_category || (!selectedErrorCategory.value && index === 0)
      ? { color: index === 0 ? "rgba(207, 63, 54, 0.12)" : "rgba(24, 144, 255, 0.10)" }
      : undefined,
    emphasis: { focus: "series" },
    data: errorTrend.value?.points.map((point) => point.categories[seriesItem.error_category] || 0) || [],
  })),
}));

const modelOptions = computed(() => {
  const optionMap = new Map<string, string>();
  generationModels.value.forEach((item) => {
    optionMap.set(item.model_key, item.model_label);
  });
  taskScenes.value
    .filter((item) => item.scene_type === "image_edit")
    .forEach((item) => {
      optionMap.set(item.scene_key, item.display_name || item.scene_label);
    });
  optionMap.set("inpaint", "局部重绘");
  return Array.from(optionMap.entries()).map(([value, label]) => ({ value, label }));
});

function formatQueryDate(value?: Dayjs) {
  return value ? value.format("YYYY-MM-DDTHH:mm:ss") : undefined;
}

function applyPreset(nextPreset: DatePreset) {
  const now = dayjs();
  preset.value = nextPreset;
  if (nextPreset === "today") {
    dateRange.value = [now.startOf("day"), now.endOf("day")];
    return;
  }
  if (nextPreset === "3d") {
    dateRange.value = [now.subtract(2, "day").startOf("day"), now.endOf("day")];
    return;
  }
  if (nextPreset === "7d") {
    dateRange.value = [now.subtract(6, "day").startOf("day"), now.endOf("day")];
    return;
  }
  dateRange.value = [now.subtract(29, "day").startOf("day"), now.endOf("day")];
}

function handlePresetChange(value: DatePreset) {
  applyPreset(value);
  load();
}

function handleDateRangeChange() {
  preset.value = undefined;
  selectedErrorCategory.value = undefined;
  selectedBucketLabel.value = undefined;
  drilledDateRange.value = null;
  if (dateRange.value?.[0] && dateRange.value?.[1]) {
    load();
  }
}

function handleReset() {
  applyPreset("today");
  modelFilter.value = undefined;
  selectedErrorCategory.value = undefined;
  selectedBucketLabel.value = undefined;
  drilledDateRange.value = null;
  load();
}

async function loadModelOptions() {
  try {
    const [models, scenes] = await Promise.all([getGenerationModels(), getTaskScenes()]);
    generationModels.value = models;
    taskScenes.value = scenes;
  } catch {
    generationModels.value = [];
    taskScenes.value = [];
  }
}

async function load() {
  if (!dateRange.value?.[0] || !dateRange.value?.[1]) return;
  loading.value = true;
  try {
    const effectiveRange = drilledDateRange.value || dateRange.value;
    const startDate = formatQueryDate(effectiveRange?.[0]?.startOf("day"));
    const endDate = formatQueryDate(effectiveRange?.[1]?.endOf("day"));
    const [analyticsResult, trendResult] = await Promise.all([
      getAdminErrorAnalytics({
        start_date: startDate,
        end_date: endDate,
        model: modelFilter.value,
        error_category: selectedErrorCategory.value,
      }),
      getAdminErrorCategoryTimeseries({
        granularity: trendGranularity.value,
        start_date: formatQueryDate(dateRange.value[0].startOf("day")),
        end_date: formatQueryDate(dateRange.value[1].endOf("day")),
        model: modelFilter.value,
        limit: 6,
      }),
    ]);
    analytics.value = analyticsResult;
    errorTrend.value = trendResult;
    taskTablePage.value = 1;
    await loadTaskTable(1);
  } catch (err: unknown) {
    if (isSessionExpiredError(err)) return;
    message.error("获取错误统计失败");
  } finally {
    loading.value = false;
  }
}

async function loadTaskTable(page = taskTablePage.value) {
  if (!selectedErrorCategory.value || !dateRange.value?.[0] || !dateRange.value?.[1]) {
    taskTableItems.value = [];
    taskTableTotal.value = 0;
    taskTablePage.value = 1;
    return;
  }
  taskTableLoading.value = true;
  try {
    const effectiveRange = drilledDateRange.value || dateRange.value;
    const res = await getAdminErrorTasks({
      page,
      page_size: TASK_TABLE_PAGE_SIZE,
      start_date: formatQueryDate(effectiveRange?.[0]?.startOf("day")),
      end_date: formatQueryDate(effectiveRange?.[1]?.endOf("day")),
      model: modelFilter.value,
      error_category: selectedErrorCategory.value,
    });
    taskTableItems.value = res.items;
    taskTableTotal.value = res.total;
    taskTablePage.value = page;
  } catch (err: unknown) {
    if (isSessionExpiredError(err)) return;
    message.error("获取错误任务明细失败");
  } finally {
    taskTableLoading.value = false;
  }
}

function getErrorRowKey(record: AdminErrorAnalytics["items"][number]) {
  return `${record.error_category}-${record.error_message}`;
}

function handleTrendChartClick(params: { seriesName?: string; dataIndex?: number }) {
  const rawName = (params.seriesName || "").trim();
  const category = rawName.replace(/\s*\(\d+\)\s*$/, "").trim();
  if (!category) return;
  const point = typeof params.dataIndex === "number" ? errorTrend.value?.points[params.dataIndex] : null;
  if (
    selectedErrorCategory.value === category
    && selectedBucketLabel.value
    && point?.label === selectedBucketLabel.value
  ) {
    clearErrorCategoryFilter();
    return;
  }
  selectedErrorCategory.value = category;
  selectedBucketLabel.value = point?.label;
  if (point?.bucket_start && point?.bucket_end) {
    drilledDateRange.value = [dayjs(point.bucket_start), dayjs(point.bucket_end)];
  } else {
    drilledDateRange.value = null;
  }
  load();
}

function clearErrorCategoryFilter() {
  selectedErrorCategory.value = undefined;
  selectedBucketLabel.value = undefined;
  drilledDateRange.value = null;
  load();
}

function fmtTime(value?: string | null) {
  return value ? dayjs(value).format("YYYY-MM-DD HH:mm:ss") : "-";
}

function modeLabel(value: string) {
  if (value === "text_generate") return "文生图";
  if (value === "image_edit") return "图编辑";
  if (value === "inpaint") return "局部重绘";
  if (value === "promptReverse") return "提示词反推";
  return value;
}

function sourceLabel(value: string) {
  if (value === "app") return "App";
  if (value === "api") return "API";
  return "Web";
}

function modelLabel(value: string) {
  if (!value) return "-";
  return modelOptions.value.find((item) => item.value === value)?.label || value;
}

function statusLabel(value: string) {
  const map: Record<string, string> = {
    pending: "等待中",
    queued: "排队中",
    processing: "处理中",
    success: "成功",
    failed: "失败",
  };
  return map[value] || value;
}

function taskErrorText(record: AdminErrorTaskItem) {
  return formatGenerationTaskFailureMessage(record.error_message, record.credit_refunded);
}

async function openTaskDetail(record: AdminErrorTaskItem) {
  detailOpen.value = true;
  detailLoading.value = true;
  detailItem.value = null;
  const requestKey = record.task_id;
  activeDetailRequestKey = requestKey;
  try {
    const detail = await getAdminHistoryDetail({
      item_type: "task",
      task_id: record.task_id,
    });
    if (activeDetailRequestKey !== requestKey) return;
    detailItem.value = detail;
  } catch {
    if (activeDetailRequestKey !== requestKey) return;
    detailOpen.value = false;
    message.error("获取任务详情失败");
  } finally {
    if (activeDetailRequestKey === requestKey) {
      detailLoading.value = false;
    }
  }
}

onMounted(async () => {
  applyPreset("today");
  await loadModelOptions();
  load();
});
</script>

<template>
  <div class="warm-page motion-page-enter">
    <div class="warm-page-header motion-fade-up" style="--motion-delay: 40ms">
      <div class="warm-page-heading">
        <div class="warm-page-icon">
          <BugOutlined />
        </div>
        <div>
          <div class="warm-page-title">错误统计</div>
          <div class="warm-page-desc">查看失败任务分布，并按错误类别聚合分析趋势与明细。</div>
        </div>
      </div>
      <div v-if="analytics" class="page-period-chip">
        {{ analytics.range_label }}
      </div>
    </div>

    <div class="analytics-filter warm-card motion-fade-up motion-card-lift" style="--motion-delay: 120ms">
      <div class="analytics-filter-row">
        <a-range-picker
          v-model:value="dateRange"
          :placeholder="['开始日期', '结束日期']"
          class="analytics-filter-date"
          @change="handleDateRangeChange"
        />
        <a-select
          v-model:value="modelFilter"
          allow-clear
          show-search
          class="analytics-filter-select"
          placeholder="全部模型"
          :options="modelOptions"
          option-filter-prop="label"
          @change="load"
        />
        <div class="analytics-filter-panel-compact">
          <a-radio-group
            :value="preset"
            class="analytics-segmented-group analytics-segmented-group-secondary"
            button-style="solid"
            @update:value="handlePresetChange"
          >
            <a-radio-button value="today">今日</a-radio-button>
            <a-radio-button value="3d">近 3 天</a-radio-button>
            <a-radio-button value="7d">近 7 天</a-radio-button>
            <a-radio-button value="30d">近 30 天</a-radio-button>
          </a-radio-group>
        </div>
        <a-button type="primary" class="analytics-action-btn" :loading="loading" @click="load">查询</a-button>
        <a-button class="analytics-action-btn analytics-action-btn-secondary" @click="handleReset">重置</a-button>
      </div>
    </div>

    <div class="summary-grid">
      <div
        v-for="(item, index) in summaryCards"
        :key="item.key"
        class="summary-card warm-card motion-card-lift motion-fade-up"
        :style="{ '--motion-delay': `${160 + index * 40}ms` }"
      >
        <div class="summary-card-head">
          <span class="summary-card-label">{{ item.label }}</span>
          <span class="summary-card-dot" :style="{ background: item.color }" />
        </div>
        <div class="summary-card-value" :style="{ color: item.color }">{{ item.value }}</div>
        <div class="summary-card-desc">{{ item.desc }}</div>
      </div>
    </div>

    <div class="warm-card trend-card motion-card-lift motion-fade-up" style="--motion-delay: 220ms">
      <div class="table-card-head">
        <div>
          <div class="table-card-title">错误类别趋势</div>
          <div class="table-card-desc">
            按 {{ trendGranularity === "day" ? "天" : trendGranularity === "week" ? "周" : "月" }} 展示当前范围内 Top 6 错误类别变化趋势。
          </div>
        </div>
        <div v-if="selectedErrorCategory" class="linked-filter-chip-wrap">
          <span class="linked-filter-chip">已筛选：{{ selectedErrorCategory }}</span>
          <span v-if="selectedBucketLabel" class="linked-filter-chip linked-filter-chip-secondary">时间桶：{{ selectedBucketLabel }}</span>
          <a-button type="link" size="small" class="clear-filter-btn" @click="clearErrorCategoryFilter">清除</a-button>
        </div>
      </div>
      <div v-if="hasTrendData" class="trend-chart-wrap">
        <VChart class="trend-chart" :option="trendOption" autoresize @click="handleTrendChartClick" />
      </div>
      <div v-else class="trend-empty">
        <a-empty description="当前时间范围内暂无错误趋势数据" />
      </div>
    </div>

    <div class="warm-card warm-table-card motion-card-lift motion-fade-up" style="--motion-delay: 260ms">
      <div class="table-card-head">
        <div>
          <div class="table-card-title">错误明细</div>
          <div class="table-card-desc">
            {{
              selectedErrorCategory
                ? `当前仅展示“${selectedErrorCategory}”在${selectedBucketLabel || "当前范围"}内的明细。`
                : "按错误类别聚合展示，并保留每类的示例错误文案。"
            }}
          </div>
        </div>
      </div>
      <a-table
        :columns="columns"
        :data-source="filteredItems"
        :loading="loading"
        :pagination="false"
        :row-key="getErrorRowKey"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.dataIndex === 'count'">
            <span class="count-badge">{{ record.count }}</span>
          </template>
          <template v-else-if="column.dataIndex === 'error_message'">
            <div class="error-message-cell">{{ record.error_message }}</div>
          </template>
          <template v-else-if="column.dataIndex === 'error_category'">
            <span class="category-badge">{{ record.error_category }}</span>
          </template>
        </template>
        <template #emptyText>
          <a-empty description="当前时间范围内暂无失败错误记录" />
        </template>
      </a-table>
    </div>

    <div v-if="selectedErrorCategory" class="warm-card warm-table-card motion-card-lift motion-fade-up" style="--motion-delay: 300ms">
      <div class="table-card-head">
        <div>
          <div class="table-card-title">当天任务情况</div>
          <div class="table-card-desc">
            {{ selectedBucketLabel ? `查看“${selectedErrorCategory}”在 ${selectedBucketLabel} 的失败任务明细。` : `查看“${selectedErrorCategory}”对应的失败任务明细。` }}
          </div>
        </div>
        <div class="history-summary">
          <span class="history-summary-chip">筛选结果 {{ taskTableTotal }} 条</span>
        </div>
      </div>
      <a-table
        :columns="taskColumns"
        :data-source="taskTableItems"
        :loading="taskTableLoading"
        :pagination="false"
        :row-key="(record: AdminErrorTaskItem) => record.task_id"
        :scroll="{ x: 1180 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.dataIndex === 'model'">
            <span class="table-single-line" :title="modelLabel(record.model)">{{ modelLabel(record.model) }}</span>
          </template>
          <template v-else-if="column.dataIndex === 'task_type'">
            {{ modeLabel(record.task_type) }}
          </template>
          <template v-else-if="column.dataIndex === 'source'">
            {{ sourceLabel(record.source) }}
          </template>
          <template v-else-if="column.dataIndex === 'status'">
            <span class="category-badge category-badge-danger">{{ statusLabel(record.status) }}</span>
          </template>
          <template v-else-if="column.dataIndex === 'error_message'">
            <div class="error-message-cell">{{ taskErrorText(record) }}</div>
          </template>
          <template v-else-if="column.dataIndex === 'created_at'">
            {{ fmtTime(record.created_at) }}
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-button type="link" size="small" class="table-detail-btn" @click="openTaskDetail(record)">详情</a-button>
          </template>
        </template>
        <template #emptyText>
          <a-empty description="当前筛选条件下暂无失败任务明细" />
        </template>
      </a-table>
      <div v-if="taskTableTotal > TASK_TABLE_PAGE_SIZE" class="warm-pagination">
        <a-pagination
          :current="taskTablePage"
          :total="taskTableTotal"
          :page-size="TASK_TABLE_PAGE_SIZE"
          show-less-items
          @change="loadTaskTable"
        />
      </div>
    </div>
  </div>
  <HistoryDetailDialog
    :open="detailOpen"
    :item="detailItem"
    :loading="detailLoading"
    :model-options="modelOptions"
    show-error-message
    @update:open="detailOpen = $event"
  />
</template>

<style scoped lang="scss">
.analytics-filter {
  margin-bottom: 16px;
}

.page-period-chip {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255, 253, 248, 0.92);
  border: 1px solid rgba(240, 223, 190, 0.95);
  color: #8c7458;
  font-size: 13px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.summary-card {
  min-height: 116px;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  justify-content: space-between;
}

.summary-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.summary-card-label {
  color: #8c7458;
  font-size: 13px;
  font-weight: 700;
}

.summary-card-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  box-shadow: 0 0 0 4px rgba(255, 193, 90, 0.14);
}

.summary-card-value {
  font-size: 30px;
  line-height: 1.1;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.summary-card-desc {
  color: #9a805b;
  font-size: 12px;
  line-height: 1.5;
}

.trend-card {
  margin-bottom: 16px;
  overflow: hidden;
}

.table-card-head {
  padding: 18px 20px 14px;
  border-bottom: 1px solid rgba(240, 223, 190, 0.9);
  background: linear-gradient(180deg, rgba(255, 250, 240, 0.88), rgba(255, 255, 255, 0.2));
}

.table-card-title {
  color: #5d4526;
  font-size: 16px;
  font-weight: 700;
}

.table-card-desc {
  margin-top: 8px;
  color: #9a805b;
  font-size: 12px;
  line-height: 1.5;
}

.linked-filter-chip-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.linked-filter-chip {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(255, 242, 239, 0.96);
  color: #cf3f36;
  font-weight: 700;
  line-height: 1.4;
}

.linked-filter-chip-secondary {
  background: rgba(255, 248, 226, 0.96);
  color: #9c6b00;
}

.category-badge-danger {
  background: rgba(255, 242, 239, 0.96);
  color: #cf3f36;
}

.clear-filter-btn {
  padding-inline: 0;
}

.count-badge {
  display: inline-flex;
  min-width: 34px;
  padding: 2px 10px;
  border-radius: 999px;
  background: rgba(255, 242, 239, 0.96);
  color: #cf3f36;
  font-weight: 700;
  justify-content: center;
}

.category-badge {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(255, 248, 226, 0.96);
  color: #9c6b00;
  font-weight: 700;
  line-height: 1.4;
}

.trend-chart-wrap {
  height: 360px;
  padding: 14px 16px 8px;
}

.trend-chart {
  height: 100%;
}

.trend-empty {
  min-height: 260px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 20px;
}

.error-message-cell {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
  color: var(--theme-text);
}

.history-summary {
  display: flex;
  align-items: center;
  gap: 8px;
}

.history-summary-chip {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255, 248, 226, 0.9);
  color: #9a6b17;
  font-size: 12px;
  font-weight: 700;
}

.table-single-line {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.warm-pagination {
  display: flex;
  justify-content: flex-end;
  padding: 14px 20px 18px;
}

.analytics-filter-select {
  width: 336px;
}

@media (max-width: 768px) {
  .analytics-filter-row {
    align-items: stretch;
  }

  .analytics-filter-select,
  .analytics-filter-date,
  .analytics-action-btn {
    width: 100%;
  }
}
</style>
