<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query';
import MarketHeader from './components/MarketHeader.vue';
import MarketStatsRow from './components/MarketStatsRow.vue';
import Sp500PriceVolumeChart from './components/Sp500PriceVolumeChart.vue';
import SectorTable from './components/SectorTable.vue';
import Mag7RelativeChart from './components/Mag7RelativeChart.vue';
import Mag7HistogramPerformance from './components/Mag7HistogramPerformance.vue';
import MultiAssetComparisonChart from './components/MultiAssetComparisonChart.vue';
import DrawdownChart from './components/DrawdownChart.vue';
import RelativeComparisonChart from './components/RelativeComparisonChart.vue';
import FearGreedComparisonChart from './components/FearGreedComparisonChart.vue';
import MarketBreadthChart from './components/MarketBreadthChart.vue';
import SpForwardPeChart from './components/SpForwardPeChart.vue';
import { fetchMarketSummary } from './services/api';

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

const { data: sp500Summary } = useQuery({
  queryKey: ['market', 'sp500'],
  queryFn: () => fetchMarketSummary('sp500'),
});

const { data: nasdaqSummary } = useQuery({
  queryKey: ['market', 'nasdaq'],
  queryFn: () => fetchMarketSummary('nasdaq'),
});

</script>

<template>
  <div class="min-h-screen bg-background text-white py-8">
    <div class="mx-auto w-full max-w-[1500px] px-4 md:px-10 space-y-10">
      <section>
        <MarketHeader
          title="Shepherd Capital Markets"
          subtitle="S&P500 Dashboard"
          :summary="sp500Summary"
          :show-absolute-change="false"
        />
      </section>

      <section class="grid gap-6 xl:grid-cols-[2fr,1fr]">
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
      </section>

      <section class="grid gap-6 xl:grid-cols-2">
        <DrawdownChart />
        <RelativeComparisonChart />
      </section>
    </div>
  </div>
</template>
