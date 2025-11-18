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
import { fetchMarketSummary } from './services/api';

const { data: sp500Summary } = useQuery({
  queryKey: ['market', 'sp500'],
  queryFn: () => fetchMarketSummary('sp500'),
  refetchInterval: 60_000,
});

const { data: nasdaqSummary } = useQuery({
  queryKey: ['market', 'nasdaq'],
  queryFn: () => fetchMarketSummary('nasdaq'),
  refetchInterval: 60_000,
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
        <div class="bg-panel border border-white/10 rounded-xl p-4">
          <MarketStatsRow :summary="nasdaqSummary" />
        </div>
        <div class="grid gap-6 xl:grid-cols-2">
          <Mag7RelativeChart />
          <Mag7HistogramPerformance />
        </div>
      </section>

      <section>
        <MultiAssetComparisonChart />
      </section>

      <section class="grid gap-6 xl:grid-cols-2">
        <DrawdownChart />
        <RelativeComparisonChart />
      </section>
    </div>
  </div>
</template>
