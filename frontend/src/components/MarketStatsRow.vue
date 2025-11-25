<script setup lang="ts">
import { computed } from 'vue';
import type { MarketSummary } from '../types/api';

const props = defineProps<{
  summary?: MarketSummary;
  showAbsoluteChange?: boolean;
}>();

const dayChangeClass = computed(() =>
  (props.summary?.day_change ?? 0) >= 0 ? 'text-accentGreen' : 'text-accentRed',
);

const vixChangeClass = computed(() =>
  (props.summary?.vix_change_pct ?? 0) >= 0 ? 'text-accentGreen' : 'text-accentRed',
);

const formatPercent = (value?: number | null) => {
  if (value === null || value === undefined) return '--';
  return `${value.toFixed(1)}%`;
};
</script>

<template>
  <div class="flex flex-wrap items-center gap-6 text-lg">
    <div v-if="summary?.advancers_pct !== undefined" class="flex items-center gap-2">
      <span class="text-accentOrange uppercase text-base tracking-wide">Advance</span>
      <span class="text-accentGreen text-xl font-semibold">
        {{ summary ? formatPercent(summary.advancers_pct) : '--' }}
      </span>
    </div>
    <div v-if="summary?.decliners_pct !== undefined" class="flex items-center gap-2">
      <span class="text-accentOrange uppercase text-base tracking-wide">Decline</span>
      <span class="text-accentRed text-xl font-semibold">
        {{ summary ? formatPercent(summary.decliners_pct) : '--' }}
      </span>
    </div>
    <div class="flex items-center gap-2">
      <span class="text-accentOrange uppercase text-base tracking-wide">1 Day Chg</span>
      <span
        v-if="(showAbsoluteChange ?? true)"
        :class="dayChangeClass"
        class="text-xl font-semibold"
      >
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
</template>
