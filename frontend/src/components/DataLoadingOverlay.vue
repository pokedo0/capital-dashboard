<template>
  <Transition name="widget-loading-fade">
    <div
      v-if="show"
      class="absolute inset-0 z-30 flex items-center justify-center bg-panel/80 backdrop-blur-sm rounded-xl"
    >
      <div class="flex flex-col items-center gap-3">
        <div class="widget-data-spinner">
          <svg viewBox="0 0 50 50" class="w-8 h-8">
            <circle cx="25" cy="25" r="20" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="3" />
            <circle
              cx="25" cy="25" r="20" fill="none"
              stroke="#67f0d6" stroke-width="3" stroke-linecap="round"
              class="spinner-arc"
            />
          </svg>
        </div>
        <span class="text-[10px] text-white/30 uppercase tracking-widest">{{ label }}</span>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  show: boolean;
  label?: string;
}>(), {
  label: 'Loading…',
});
</script>

<style scoped>
.widget-data-spinner svg {
  animation: wdsRotate 1.2s linear infinite;
  filter: drop-shadow(0 0 6px rgba(103, 240, 214, 0.3));
}

.spinner-arc {
  stroke-dasharray: 80, 200;
  stroke-dashoffset: 0;
  animation: wdsDash 1.4s ease-in-out infinite;
}

@keyframes wdsRotate {
  100% { transform: rotate(360deg); }
}

@keyframes wdsDash {
  0%   { stroke-dasharray: 1, 200; stroke-dashoffset: 0; }
  50%  { stroke-dasharray: 80, 200; stroke-dashoffset: -35; }
  100% { stroke-dasharray: 80, 200; stroke-dashoffset: -125; }
}

.widget-loading-fade-enter-active {
  transition: opacity 0.25s ease-out;
}
.widget-loading-fade-leave-active {
  transition: opacity 0.35s ease-in;
}
.widget-loading-fade-enter-from,
.widget-loading-fade-leave-to {
  opacity: 0;
}
</style>
