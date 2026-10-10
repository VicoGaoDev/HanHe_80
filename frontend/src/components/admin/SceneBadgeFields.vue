<script setup lang="ts">
import { computed } from "vue";

const text = defineModel<string>("text", { default: "" });
const color = defineModel<string>("color", { default: "" });

const presets = [
  { label: "HOT", value: "#FF7A00", fillText: true },
  { label: "NEW", value: "#7C4DFF", fillText: true },
  { label: "红", value: "#F5222D", fillText: false },
  { label: "蓝", value: "#1677FF", fillText: false },
  { label: "绿", value: "#52C41A", fillText: false },
];

const pickerColor = computed(() => (
  /^#[0-9A-Fa-f]{6}$/.test(color.value) ? color.value : "#FF7A00"
));

function applyPreset(preset: (typeof presets)[number]) {
  color.value = preset.value;
  if (preset.fillText && !text.value.trim()) text.value = preset.label;
}

function updatePickerColor(event: Event) {
  const value = (event.target as HTMLInputElement).value;
  color.value = value.toUpperCase();
}
</script>

<template>
  <div class="scene-badge-fields">
    <a-input v-model:value="text" class="warm-input" :maxlength="16" placeholder="例如 HOT、NEW，留空不显示" />
    <div class="scene-badge-color-row">
      <input class="scene-badge-picker" type="color" :value="pickerColor" @input="updatePickerColor" />
      <a-input v-model:value="color" class="warm-input" :maxlength="7" placeholder="#FF7A00" />
    </div>
    <div class="scene-badge-presets">
      <button
        v-for="preset in presets"
        :key="preset.value"
        type="button"
        class="scene-badge-preset"
        :style="{ background: preset.value }"
        @click="applyPreset(preset)"
      >
        {{ preset.label }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.scene-badge-fields {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.scene-badge-color-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.scene-badge-picker {
  width: 36px;
  height: 32px;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
}

.scene-badge-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.scene-badge-preset {
  border: none;
  border-radius: 999px;
  padding: 2px 8px;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
  cursor: pointer;
}
</style>
