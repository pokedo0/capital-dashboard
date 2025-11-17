<script setup lang="ts">
import { computed } from 'vue';
import type { MarketSummary } from '../types/api';

const props = defineProps<{
  title: string;
  subtitle: string;
  summary?: MarketSummary;
  variant?: 'primary' | 'secondary';
  showDate?: boolean;
}>();

const formattedDate = computed(() => {
  if (!props.summary?.date) return '';
  return new Intl.DateTimeFormat('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(props.summary.date));
});

const dayChangeClass = computed(() =>
  (props.summary?.day_change ?? 0) >= 0 ? 'text-accentGreen' : 'text-accentRed',
);

const vixChangeClass = computed(() =>
  (props.summary?.vix_change_pct ?? 0) >= 0 ? 'text-accentGreen' : 'text-accentRed',
);
</script>

<template>
  <div class="w-full">
    <div v-if="showDate !== false" class="text-accentOrange text-xl font-semibold tracking-wide">
      {{ formattedDate || 'Loading...' }}
    </div>
    <div
      v-if="(variant ?? 'primary') === 'primary'"
      class="mt-2 bg-accent text-3xl font-bold px-6 py-4 uppercase tracking-widest"
    >
      {{ title }}
    </div>
    <div v-else class="mt-2 text-3xl font-semibold uppercase tracking-widest">
      {{ title }}
    </div>
    <div class="mt-2 text-2xl text-accentCyan font-semibold uppercase">
      {{ subtitle }}
    </div>
    <div class="mt-4 flex flex-wrap items-center gap-6 text-lg">
      <div class="flex items-center gap-2">
        <span class="text-accentOrange uppercase text-base tracking-wide">1 Day Chg</span>
        <span :class="dayChangeClass" class="text-xl font-semibold">
          {{ summary ? summary.day_change.toFixed(2) : '--' }}
        </span>
        <span :class="dayChangeClass" class="text-xl font-semibold">
          {{ summary ? summary.day_change_pct.toFixed(2) + '%' : '' }}
        </span>
      </div>
      <div class="flex items-center gap-2 text-white text-xl font-semibold">
        <span>{{ summary ? summary.index_value.toFixed(2) : '--' }}</span>
      </div>
      <div class="flex items-center gap-2 text-white text-xl font-semibold">
        <span>VIX</span>
        <span>{{ summary ? summary.vix_value.toFixed(2) : '--' }}</span>
        <span :class="vixChangeClass">
          {{ summary ? summary.vix_change_pct.toFixed(2) + '%' : '' }}
        </span>
      </div>
    </div>
  </div>
</template>
