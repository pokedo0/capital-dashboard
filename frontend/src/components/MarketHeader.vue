<script setup lang="ts">
import { computed } from 'vue';
import type { MarketSummary } from '../types/api';
import MarketStatsRow from './MarketStatsRow.vue';

const props = defineProps<{
  title: string;
  subtitle: string;
  summary?: MarketSummary;
  variant?: 'primary' | 'secondary';
  showDate?: boolean;
  showAbsoluteChange?: boolean;
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
    <MarketStatsRow
      :summary="summary"
      :show-absolute-change="showAbsoluteChange ?? true"
      class="mt-4"
    />
  </div>
</template>
