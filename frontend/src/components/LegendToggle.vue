<script setup lang="ts">
const props = defineProps<{
  items: { key: string; label: string; color: string }[];
  activeKeys: string[];
}>();

const emit = defineEmits<{
  (e: 'update:activeKeys', value: string[]): void;
}>();

const toggle = (key: string) => {
  const isActive = props.activeKeys.includes(key);
  const next = isActive
    ? props.activeKeys.filter((k) => k !== key)
    : [...props.activeKeys, key];
  emit('update:activeKeys', next);
};
</script>

<template>
  <div class="flex flex-wrap gap-3 text-sm">
    <button
      v-for="item in items"
      :key="item.key"
      class="flex items-center gap-2 uppercase tracking-wide"
      @click="toggle(item.key)"
    >
      <span
        class="w-4 h-1 rounded-full"
        :style="{ backgroundColor: item.color, opacity: activeKeys.includes(item.key) ? 1 : 0.2 }"
      ></span>
      <span :class="activeKeys.includes(item.key) ? 'text-white' : 'text-textMuted'">
        {{ item.label }}
      </span>
    </button>
  </div>
</template>
