<script setup lang="ts">
import { computed } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { fetchSectorSummary } from '../services/api';

const { data } = useQuery({
  queryKey: ['sectors'],
  queryFn: () => fetchSectorSummary(),
});

const sortedSectors = computed(() => {
  const sectors = data.value?.sectors ?? [];
  return [...sectors].sort((a, b) => (b.change_pct ?? 0) - (a.change_pct ?? 0));
});

const formatNumber = (value: number) => value.toFixed(2);
</script>

<template>
  <div class="bg-panel border border-white/10 rounded-xl p-4 h-full">
    <div class="text-xl font-semibold text-white uppercase tracking-wide mb-4">Sector ETFs</div>
    <div class="overflow-x-auto">
      <table class="w-full text-left text-sm whitespace-nowrap">
        <thead class="text-textMuted uppercase tracking-wide text-xs">
          <tr>
            <th class="pb-2">Name</th>
            <th class="pb-2 text-right">1Day</th>
            <th class="pb-2 text-right">Volume (M)</th>
            <th class="pb-2 text-right">% Avg</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="sector in sortedSectors" :key="sector.symbol" class="border-t border-white/5 text-sm">
            <td class="py-2 text-white">{{ sector.name }}</td>
            <td class="py-2 text-right" :class="sector.change_pct >= 0 ? 'text-accentGreen' : 'text-accentRed'">
              {{ formatNumber(sector.change_pct) }}%
            </td>
            <td class="py-2 text-right text-white">
              {{ formatNumber(sector.volume_millions) }}
            </td>
            <td class="py-2 text-right text-white">
              {{ formatNumber(sector.percent_of_avg) }}%
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
