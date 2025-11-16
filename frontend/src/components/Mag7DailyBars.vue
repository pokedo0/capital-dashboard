<script setup lang="ts">
import { computed } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { fetchDailyPerformance } from '../services/api';

const SYMBOLS = ['NVDA', 'GOOG', 'AMZN', 'AAPL', 'META', 'MSFT', 'TSLA'];

const { data } = useQuery({
  queryKey: ['daily', 'mag7'],
  queryFn: () => fetchDailyPerformance(SYMBOLS),
  refetchInterval: 60_000,
});

const orderedData = computed(() =>
  SYMBOLS.map((symbol) => data.value?.find((item) => item.symbol === symbol))
    .filter(Boolean)
    .map((item) => item!),
);

const maxValue = computed(() => {
  const values = orderedData.value.map((item) => Math.abs(item.change_pct));
  return Math.max(...values, 1);
});
</script>

<template>
  <div class="bg-panel border border-white/10 rounded-xl p-4 flex flex-col gap-4">
    <div class="text-xl text-accentCyan font-semibold uppercase">Mag 7 Daily Performance</div>
    <div class="flex gap-4 items-end justify-between">
      <div
        v-for="item in orderedData"
        :key="item.symbol"
        class="flex flex-col items-center flex-1"
      >
        <div
          class="w-10 rounded-t"
          :class="item.change_pct >= 0 ? 'bg-accentGreen' : 'bg-accentRed'"
          :style="{ height: `${(Math.abs(item.change_pct) / maxValue) * 200 + 2}px` }"
        ></div>
        <div class="text-sm font-semibold mt-2" :class="item.change_pct >= 0 ? 'text-accentGreen' : 'text-accentRed'">
          {{ item.change_pct.toFixed(2) }}%
        </div>
        <div class="text-textMuted text-sm mt-1 uppercase tracking-wide">{{ item.symbol }}</div>
      </div>
    </div>
  </div>
</template>
