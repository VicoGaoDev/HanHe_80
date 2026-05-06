<script setup lang="ts">
import { computed } from "vue";
import type { PropType } from "vue";
import type { Dayjs } from "dayjs";
import type { AdminAnalyticsGranularity, AdminUser, TaskMode, TaskSource } from "@/types";

type FilterState = {
  status?: string;
  user_id?: string;
  source?: TaskSource;
  model?: string;
  mode?: TaskMode;
  dateRange: [Dayjs, Dayjs] | null;
};

const props = defineProps({
  users: {
    type: Array as PropType<AdminUser[]>,
    default: () => [],
  },
  modelOptions: {
    type: Array as PropType<Array<{ label: string; value: string }>>,
    default: () => [],
  },
  filters: {
    type: Object as PropType<FilterState>,
    required: true,
  },
  granularity: {
    type: String as PropType<AdminAnalyticsGranularity>,
    required: true,
  },
  preset: {
    type: String,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits<{
  (e: "update:granularity", value: AdminAnalyticsGranularity): void;
  (e: "preset-change", value: string): void;
  (e: "reset"): void;
}>();

const presetOptions = computed(() => {
  if (props.granularity === "week") {
    return [
      { key: "8w", label: "近 8 周" },
      { key: "12w", label: "近 12 周" },
    ];
  }
  if (props.granularity === "month") {
    return [
      { key: "6m", label: "近 6 月" },
      { key: "12m", label: "近 12 月" },
    ];
  }
  return [
    { key: "3d", label: "近 3 天" },
    { key: "30d", label: "近 30 天" },
  ];
});
</script>

<template>
  <div class="analytics-filter warm-card motion-fade-up motion-card-lift" style="--motion-delay: 120ms">
    <div class="analytics-filter-row">
      <div class="analytics-filter-panel-compact">
        <a-radio-group
          :value="granularity"
          class="analytics-segmented-group"
          button-style="solid"
          @update:value="emit('update:granularity', $event)"
        >
          <a-radio-button value="day">按日</a-radio-button>
          <a-radio-button value="week">按周</a-radio-button>
          <a-radio-button value="month">按月</a-radio-button>
        </a-radio-group>
      </div>

      <div class="analytics-filter-panel-compact">
        <a-radio-group
          :value="preset"
          class="analytics-segmented-group analytics-segmented-group-secondary"
          button-style="solid"
          @update:value="emit('preset-change', $event)"
        >
          <a-radio-button
            v-for="item in presetOptions"
            :key="item.key"
            :value="item.key"
          >
            {{ item.label }}
          </a-radio-button>
        </a-radio-group>
      </div>

      <a-select
        v-model:value="filters.user_id"
        placeholder="全部用户"
        allow-clear
        show-search
        option-filter-prop="label"
        class="analytics-filter-select"
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

      <a-select
        v-model:value="filters.status"
        placeholder="全部状态"
        allow-clear
        class="analytics-filter-select"
      >
        <a-select-option value="pending">等待中</a-select-option>
        <a-select-option value="processing">处理中</a-select-option>
        <a-select-option value="success">成功</a-select-option>
        <a-select-option value="failed">失败</a-select-option>
      </a-select>

      <a-select
        v-model:value="filters.source"
        placeholder="全部来源"
        allow-clear
        class="analytics-filter-select"
      >
        <a-select-option value="web">Web</a-select-option>
        <a-select-option value="app">App</a-select-option>
      </a-select>

      <a-select
        v-model:value="filters.mode"
        placeholder="全部类型"
        allow-clear
        class="analytics-filter-select"
      >
        <a-select-option value="generate">生图</a-select-option>
        <a-select-option value="inpaint">局部重绘</a-select-option>
        <a-select-option value="promptReverse">提示词反推</a-select-option>
      </a-select>

      <a-select
        v-model:value="filters.model"
        placeholder="全部模型"
        allow-clear
        class="analytics-filter-select analytics-filter-model"
      >
        <a-select-option
          v-for="option in modelOptions"
          :key="option.value"
          :value="option.value"
        >
          {{ option.label }}
        </a-select-option>
      </a-select>

      <a-range-picker
        v-model:value="filters.dateRange"
        class="analytics-filter-date"
      />
      <a-button class="analytics-action-btn analytics-action-btn-secondary" :loading="loading" @click="emit('reset')">
        重置
      </a-button>
    </div>
  </div>
</template>

<style scoped lang="scss">
.analytics-filter {
  padding: 16px 18px;
  position: relative;
  overflow: hidden;

  &::before {
    content: "";
    position: absolute;
    inset: 0 auto auto 0;
    width: 100%;
    height: 1px;
    background: linear-gradient(90deg, rgba(255, 193, 90, 0.85), rgba(255, 193, 90, 0));
  }
}

.analytics-filter-panel-compact {
  flex-shrink: 0;
}

.analytics-filter-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

:deep(.analytics-segmented-group.ant-radio-group) {
  display: inline-flex;
  padding: 3px;
  border-radius: 12px;
  background: linear-gradient(180deg, #fffaf4, #fff4e5);
  border: 1px solid rgba(236, 204, 151, 0.95);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.92),
    0 8px 16px rgba(236, 185, 88, 0.06);
}

:deep(.analytics-segmented-group .ant-radio-button-wrapper) {
  height: 34px;
  line-height: 32px;
  padding-inline: 18px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: #6f5634;
  font-weight: 700;
  font-size: 14px;
  box-shadow: none;
  transition: all var(--motion-duration-fast) var(--motion-ease-soft);
}

:deep(.analytics-segmented-group .ant-radio-button-wrapper:not(:first-child)::before) {
  display: none;
}

:deep(.analytics-segmented-group .ant-radio-button-wrapper:hover) {
  color: var(--theme-accent-text-hover);
  background: var(--theme-nav-hover-bg);
}

:deep(.analytics-segmented-group .ant-radio-button-wrapper-checked:not(.ant-radio-button-wrapper-disabled)) {
  color: var(--theme-accent-contrast);
  background: var(--theme-accent);
  box-shadow: 0 10px 18px var(--theme-shadow-strong);
}

:deep(.analytics-segmented-group .ant-radio-button-wrapper-checked:not(.ant-radio-button-wrapper-disabled):hover) {
  color: var(--theme-accent-contrast);
  background: var(--theme-accent-strong);
}

.analytics-filter-select {
  width: 138px;
}

.analytics-filter-model {
  width: 168px;
}

.analytics-filter-date {
  width: 240px;
}

:deep(.analytics-filter-select .ant-select-selector),
:deep(.analytics-filter-date.ant-picker) {
  border-radius: 12px !important;
  border-color: var(--theme-control-border) !important;
  background: var(--theme-control-bg) !important;
  box-shadow: none !important;
}

:deep(.analytics-filter-select.ant-select-focused .ant-select-selector),
:deep(.analytics-filter-date.ant-picker-focused) {
  border-color: var(--theme-border-accent) !important;
  box-shadow: 0 0 0 2px var(--theme-focus-ring) !important;
}

.analytics-action-btn {
  height: 36px;
  min-width: 72px;
  border-radius: 12px;
  padding-inline: 14px;
  font-weight: 700;
}

:deep(.analytics-segmented-group-secondary .ant-radio-button-wrapper) {
  padding-inline: 16px;
}

.analytics-action-btn.ant-btn-primary {
  border: none !important;
  background: var(--theme-accent) !important;
  box-shadow: 0 12px 22px var(--theme-shadow-strong) !important;

  &:hover,
  &:focus {
    background: var(--theme-accent-strong) !important;
    box-shadow: 0 14px 24px var(--theme-shadow-strong) !important;
  }
}

.analytics-action-btn-secondary {
  border: 1px solid var(--theme-panel-border-strong) !important;
  background: var(--theme-panel-bg-strong) !important;
  color: var(--theme-accent-text) !important;
  box-shadow: none !important;

  &:hover,
  &:focus {
    border-color: var(--theme-border-strong) !important;
    background: var(--theme-control-hover-bg) !important;
    color: var(--theme-accent-text-hover) !important;
  }
}

@media (max-width: 768px) {
  .analytics-filter {
    padding: 16px;
  }

  .analytics-filter-row {
    align-items: stretch;
  }

  .analytics-filter-select,
  .analytics-filter-model,
  .analytics-filter-date {
    width: 100%;
  }
}
</style>
