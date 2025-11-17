<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query';
import MarketHeader from './components/MarketHeader.vue';
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

</script>

<template>
  <div class="min-h-screen bg-background text-white px-4 md:px-10 py-8 space-y-10">
    <section>
      <MarketHeader title="Shepherd Capital Markets" subtitle="S&P500 Dashboard" :summary="sp500Summary" />
    </section>

    <section class="grid gap-6 xl:grid-cols-[2fr,1fr]">
      <div class="flex flex-col gap-4">
        <div class="text-lg font-semibold uppercase tracking-wide">SPY Price & Volume</div>
        <Sp500PriceVolumeChart />
      </div>
      <SectorTable />
    </section>

    <section class="space-y-4">
      <div class="text-2xl text-accentCyan font-semibold uppercase">Mag 7 Focus</div>
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
</template>
