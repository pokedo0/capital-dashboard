<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  modelValue: string;
  options?: string[];
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
}>();

const ranges = computed(() => props.options ?? ['1W', '1M', '3M', '6M', '1Y']);

const selectRange = (value: string) => {
  emit('update:modelValue', value);
};
</script>

<template>
  <div class="flex flex-wrap gap-2">
    <button
      v-for="range in ranges"
      :key="range"
      type="button"
      class="px-3 py-1 text-sm uppercase tracking-wide border rounded border-accentOrange transition-colors"
      :class="modelValue === range ? 'bg-accentOrange text-black' : 'text-accentOrange'"
      @click="selectRange(range)"
    >
      {{ range }}
    </button>
  </div>
</template>
