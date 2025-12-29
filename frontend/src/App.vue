<script setup lang="ts">
import { useQuery, useQueryClient } from '@tanstack/vue-query';
import MarketHeader from './components/MarketHeader.vue';
import MarketStatsRow from './components/MarketStatsRow.vue';
import Sp500PriceVolumeChart from './components/Sp500PriceVolumeChart.vue';
import SectorTable from './components/SectorTable.vue';
import Mag7RelativeChart from './components/Mag7RelativeChart.vue';
import Mag7HistogramPerformance from './components/Mag7HistogramPerformance.vue';
import MultiAssetComparisonChart from './components/MultiAssetComparisonChart.vue';
import SectorComparisonChart from './components/SectorComparisonChart.vue';
import CustomAssetDashboard from './components/CustomAssetDashboard.vue';
import DrawdownChart from './components/DrawdownChart.vue';
import RelativeComparisonChart from './components/RelativeComparisonChart.vue';
import FearGreedComparisonChart from './components/FearGreedComparisonChart.vue';
import MarketBreadthChart from './components/MarketBreadthChart.vue';
import SpForwardPeChart from './components/SpForwardPeChart.vue';
import { clearApiCache, fetchRealtimeMarketSummary } from './services/api';
import { ref } from 'vue';

const nasdaqBreadthOptions = [
  { value: '$NDTW', label: '$NDTW Above 20-Day' },
  { value: '$NDFI', label: '$NDFI Above 50-Day' },
  { value: '$NDTH', label: '$NDTH Above 200-Day' },
];

const spBreadthOptions = [
  { value: '$S5TW', label: '$S5TW Above 20-Day' },
  { value: '$S5FI', label: '$S5FI Above 50-Day' },
  { value: '$S5TH', label: '$S5TH Above 200-Day' },
];

// Using realtime API with 5-minute TTL cache
const { data: sp500Summary } = useQuery({
  queryKey: ['market', 'realtime', 'sp500'],
  queryFn: () => fetchRealtimeMarketSummary('sp500'),
  refetchInterval: 5 * 60 * 1000, // Refetch every 5 minutes
});

const { data: nasdaqSummary } = useQuery({
  queryKey: ['market', 'realtime', 'nasdaq'],
  queryFn: () => fetchRealtimeMarketSummary('nasdaq'),
  refetchInterval: 5 * 60 * 1000, // Refetch every 5 minutes
});

const queryClient = useQueryClient();
const clearingCache = ref(false);

const handleClearCache = async () => {
  if (clearingCache.value) return;
  clearingCache.value = true;
  try {
    await clearApiCache();
    await queryClient.invalidateQueries();
  } finally {
    clearingCache.value = false;
  }
};

</script>

<template>
  <div class="min-h-screen bg-background text-white py-8">
    <div class="mx-auto w-full max-w-[1500px] px-2 md:px-10 space-y-10">
      <section class="w-full">
        <MarketHeader
          title="Capital Dashboard"
          subtitle="S&P500 Dashboard"
          :summary="sp500Summary"
          :show-absolute-change="false"
        >
          <template #actions>
            <button
              type="button"
              class="relative flex items-center justify-center bg-white/10 hover:bg-white/20 active:scale-95 text-white p-2 rounded-full border border-white/25 transition disabled:opacity-60"
              :disabled="clearingCache"
              @click="handleClearCache"
              title="Force refresh cached data"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
              </svg>
              <span
                v-if="clearingCache"
                class="absolute -bottom-8 left-1/2 -translate-x-1/2 text-xs bg-black/80 border border-white/20 rounded px-2 py-1 whitespace-nowrap"
              >Refreshing...</span>
            </button>
          </template>
        </MarketHeader>
      </section>

      <section class="grid gap-6 xl:grid-cols-[2fr,1fr] xl:items-stretch items-start">
        <Sp500PriceVolumeChart />
        <SectorTable />
      </section>

      <section class="space-y-4">
        <div class="text-2xl text-accentCyan font-semibold uppercase">NASDAQ 100 Dashboard</div>
        <MarketStatsRow :summary="nasdaqSummary" />
        <div class="grid gap-6 xl:grid-cols-[3fr,2fr]">
          <Mag7RelativeChart />
          <Mag7HistogramPerformance />
        </div>
      </section>

      <section class="space-y-4">
        <div class="text-2xl text-accentCyan font-semibold uppercase">Market Breadth Dashboard</div>
        <div class="grid gap-6 xl:grid-cols-2">
          <MarketBreadthChart
            title="Nasdaq 100 Stocks Above X-Day Average"
            :options="nasdaqBreadthOptions"
            benchmark-symbol="^NDX"
            benchmark-label="NDX Index"
            default-symbol="$NDFI"
            chart-key="nasdaq-breadth"
            default-range="1Y"
          />
          <MarketBreadthChart
            title="S&P 500 Stocks Above X-Day Average"
            :options="spBreadthOptions"
            benchmark-symbol="^GSPC"
            benchmark-label="SPX Index"
            default-symbol="$S5FI"
            chart-key="spx-breadth"
            default-range="1Y"
          />
        </div>
      </section>

      <section class="space-y-6">
        <FearGreedComparisonChart />
        <SpForwardPeChart />
        <MultiAssetComparisonChart />
        <SectorComparisonChart />
        <CustomAssetDashboard />
      </section>

      <section class="grid gap-6 xl:grid-cols-2">
        <DrawdownChart />
        <RelativeComparisonChart />
      </section>
    </div>
  </div>
</template>
