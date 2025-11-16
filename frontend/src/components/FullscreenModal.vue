<script setup lang="ts">
const { open, title } = defineProps<{
  open: boolean;
  title?: string;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
}>();
</script>

<template>
  <teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
    >
      <div class="w-full h-full max-w-6xl bg-panel border border-white/10 rounded-lg flex flex-col">
        <div class="flex justify-between items-center px-6 py-4 border-b border-white/10">
          <div class="text-lg font-semibold uppercase tracking-wide">
            {{ title }}
          </div>
          <button class="text-textMuted hover:text-white text-2xl" @click="emit('close')">×</button>
        </div>
        <div class="flex-1 overflow-hidden p-4">
          <slot />
        </div>
      </div>
    </div>
  </teleport>
</template>
