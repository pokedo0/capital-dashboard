<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { createChart, type IChartApi, type ISeriesApi } from 'lightweight-charts';
import { useQuery } from '@tanstack/vue-query';
import TimeRangeSelector from './TimeRangeSelector.vue';
import { fetchRelativeTo } from '../services/api';

type LineSeries = ISeriesApi<'Line'>;

const SYMBOLS = ['UNH', 'AAPL', 'MSFT', 'NVDA', 'TSLA', 'META'];
const BENCHMARKS = ['XLV', 'XLK', 'XLF', 'SPY', 'QQQ'];

const selectedSymbol = ref('UNH');
const selectedBenchmark = ref('XLV');
const rangeKey = ref('1Y');
const chartContainer = ref<HTMLDivElement | null>(null);

const { data, refetch } = useQuery({
  queryKey: computed(() => ['relative-to', selectedSymbol.value, selectedBenchmark.value, rangeKey.value]),
  queryFn: () => fetchRelativeTo(selectedSymbol.value, selectedBenchmark.value, rangeKey.value),
});

watch([selectedSymbol, selectedBenchmark, rangeKey], () => refetch());

let chart: IChartApi | null = null;
let ratioSeries: LineSeries | null = null;
let averageSeries: LineSeries | null = null;
let observer: ResizeObserver | null = null;

const initChart = () => {
  if (!chartContainer.value) return;
  disposeChart();
  chart = createChart(chartContainer.value, {
    height: 320,
    layout: {
      background: { color: '#050505' },
      textColor: '#f8fafc',
      fontFamily: "'IBM Plex Sans', Inter, ui-sans-serif",
    },
    grid: {
      horzLines: { color: 'rgba(255,255,255,0.05)' },
      vertLines: { color: 'rgba(255,255,255,0.05)' },
    },
    rightPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false, timeVisible: true },
  });

  ratioSeries = chart.addLineSeries({
    color: '#60a5fa',
    lineWidth: 2,
  });
  averageSeries = chart.addLineSeries({
    color: '#f78c1f',
    lineWidth: 2,
  });

  observer = new ResizeObserver(() => {
    if (chart && chartContainer.value) {
      chart.applyOptions({ width: chartContainer.value.clientWidth, height: chartContainer.value.clientHeight });
    }
  });
  observer.observe(chartContainer.value);
};

const disposeChart = () => {
  observer?.disconnect();
  observer = null;
  chart?.remove();
  chart = null;
};

onBeforeUnmount(disposeChart);

watch(
  () => data.value,
  (payload) => {
    if (!payload || !chartContainer.value) return;
    if (!chart) initChart();
    if (!chart || !ratioSeries || !averageSeries) return;
    ratioSeries.setData(payload.ratio.map((point) => ({ time: point.time, value: point.value })));
    averageSeries.setData(payload.moving_average.map((point) => ({ time: point.time, value: point.value })));
    chart.timeScale().fitContent();
  },
  { immediate: true },
);
</script>

<template>
  <div class="bg-panel border border-white/10 rounded-xl p-4 flex flex-col gap-4">
    <div class="flex flex-wrap justify-between items-center gap-4">
      <div>
        <div class="text-xl font-semibold uppercase">{{ selectedSymbol }} Relative {{ selectedBenchmark }}</div>
        <p class="text-sm text-textMuted">Price ratio (symbol / benchmark × 100) with 30-day average</p>
      </div>
      <div class="flex items-center gap-3">
        <select v-model="selectedSymbol" class="bg-panel border border-white/20 rounded px-3 py-1 text-white">
          <option v-for="symbol in SYMBOLS" :key="symbol" :value="symbol">{{ symbol }}</option>
        </select>
        <select v-model="selectedBenchmark" class="bg-panel border border-white/20 rounded px-3 py-1 text-white">
          <option v-for="bm in BENCHMARKS" :key="bm" :value="bm">{{ bm }}</option>
        </select>
        <TimeRangeSelector v-model="rangeKey" :options="['6M', '1Y', '2Y']" />
      </div>
    </div>
    <div ref="chartContainer" class="w-full h-[320px]"></div>
    <div class="text-xs uppercase tracking-wide flex gap-4 text-textMuted">
      <span class="flex items-center gap-2">
        <span class="w-4 h-1 bg-[#60a5fa] rounded-full"></span> Ratio
      </span>
      <span class="flex items-center gap-2">
        <span class="w-4 h-1 bg-[#f78c1f] rounded-full"></span> 30D Avg
      </span>
    </div>
  </div>
</template>
