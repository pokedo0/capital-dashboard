<template>
  <div class="widget-loading-container bg-panel border border-white/10 rounded-xl p-4 flex flex-col items-center justify-center gap-4 w-full" :style="{ minHeight: minHeight }">
    <!-- Spinner -->
    <div class="widget-spinner">
      <svg class="spinner-svg" viewBox="0 0 50 50">
        <circle class="spinner-track" cx="25" cy="25" r="20" fill="none" stroke-width="3" />
        <circle class="spinner-arc" cx="25" cy="25" r="20" fill="none" stroke-width="3" stroke-linecap="round" />
      </svg>
    </div>
    <!-- Label -->
    <span class="text-xs text-white/30 uppercase tracking-widest">{{ label }}</span>
    <!-- Skeleton bars -->
    <div class="flex flex-col gap-2 w-full max-w-xs">
      <div class="skeleton-bar h-2 rounded-full w-full" />
      <div class="skeleton-bar h-2 rounded-full w-3/4" />
      <div class="skeleton-bar h-2 rounded-full w-1/2" />
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  label?: string;
  minHeight?: string;
}>(), {
  label: 'Loading…',
  minHeight: '200px',
});
</script>

<style scoped>
.widget-loading-container {
  animation: widgetFadeIn 0.3s ease-out;
}

@keyframes widgetFadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* Spinner */
.widget-spinner {
  width: 36px;
  height: 36px;
  filter: drop-shadow(0 0 6px rgba(103, 240, 214, 0.35));
}

.spinner-svg {
  animation: spinnerRotate 1.2s linear infinite;
}

.spinner-track {
  stroke: rgba(255, 255, 255, 0.06);
}

.spinner-arc {
  stroke: #67f0d6;
  stroke-dasharray: 80, 200;
  stroke-dashoffset: 0;
  animation: spinnerDash 1.4s ease-in-out infinite;
}

@keyframes spinnerRotate {
  100% { transform: rotate(360deg); }
}

@keyframes spinnerDash {
  0% {
    stroke-dasharray: 1, 200;
    stroke-dashoffset: 0;
  }
  50% {
    stroke-dasharray: 80, 200;
    stroke-dashoffset: -35;
  }
  100% {
    stroke-dasharray: 80, 200;
    stroke-dashoffset: -125;
  }
}

/* Skeleton bars */
.skeleton-bar {
  background: linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.6s ease-in-out infinite;
}

@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
