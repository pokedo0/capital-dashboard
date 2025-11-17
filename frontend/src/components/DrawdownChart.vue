<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { createChart, type IChartApi, type ISeriesApi } from 'lightweight-charts';
import { useQuery } from '@tanstack/vue-query';
import TimeRangeSelector from './TimeRangeSelector.vue';
import { fetchDrawdown } from '../services/api';

type AreaSeries = ISeriesApi<'Area'>;
type LineSeries = ISeriesApi<'Line'>;

const SYMBOLS = ['TSLA', 'NVDA', 'AAPL', 'MSFT', 'META', 'SPY'];

const selectedSymbol = ref('TSLA');
const rangeKey = ref('1Y');
const chartContainer = ref<HTMLDivElement | null>(null);

const { data, refetch } = useQuery({
  queryKey: computed(() => ['drawdown', selectedSymbol.value, rangeKey.value]),
  queryFn: () => fetchDrawdown(selectedSymbol.value, rangeKey.value),
});

watch([selectedSymbol, rangeKey], () => refetch());

let chart: IChartApi | null = null;
let drawdownSeries: AreaSeries | null = null;
let priceSeries: LineSeries | null = null;
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
    leftPriceScale: {
      borderVisible: false,
      autoScale: true,
      scaleMargins: { top: 0.1, bottom: 0.1 },
    },
    rightPriceScale: {
      borderVisible: false,
      scaleMargins: { top: 0.1, bottom: 0.1 },
    },
    timeScale: {
      borderVisible: false,
      timeVisible: true,
    },
    grid: {
      horzLines: { color: 'rgba(255,255,255,0.05)' },
      vertLines: { color: 'rgba(255,255,255,0.05)' },
    },
  });

  drawdownSeries = chart.addAreaSeries({
    priceScaleId: 'left',
    lineColor: '#ef4444',
    topColor: 'rgba(239,68,68,0.3)',
    bottomColor: 'rgba(239,68,68,0)',
    lineWidth: 2,
  });
  priceSeries = chart.addLineSeries({
    priceScaleId: 'right',
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
    if (!chart) {
      initChart();
    }
    if (!chart || !drawdownSeries || !priceSeries) return;
    drawdownSeries.setData(payload.drawdown.map((point) => ({ time: point.time, value: point.value })));
    drawdownSeries.applyOptions({
      priceLineVisible: true,
      priceLineColor: '#ef4444',
      priceLineWidth: 2,
      baseLineVisible: true,
      baseLineColor: '#ef4444',
    });
    priceSeries.setData(payload.price.map((point) => ({ time: point.time, value: point.value })));
    chart.timeScale().fitContent();
  },
  { immediate: true },
);

const currentDrawdown = computed(() => data.value?.current_drawdown ?? 0);
</script>

<template>
  <div class="bg-panel border border-white/10 rounded-xl p-4 flex flex-col gap-4">
    <div class="flex flex-wrap justify-between items-center gap-4">
      <div>
        <div class="text-xl font-semibold uppercase">{{ selectedSymbol }} Drawdown</div>
        <div class="text-sm text-textMuted">
          Current drawdown:
          <span :class="currentDrawdown >= 0 ? 'text-accentGreen' : 'text-accentRed'">
            {{ currentDrawdown.toFixed(2) }}%
          </span>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <select v-model="selectedSymbol" class="bg-panel border border-white/20 rounded px-3 py-1 text-white">
          <option v-for="symbol in SYMBOLS" :key="symbol" :value="symbol">{{ symbol }}</option>
        </select>
        <TimeRangeSelector v-model="rangeKey" />
      </div>
    </div>
    <div ref="chartContainer" class="w-full h-[320px]"></div>
    <div class="text-xs uppercase tracking-wide flex gap-4 text-textMuted">
      <span class="flex items-center gap-2">
        <span class="w-4 h-1 bg-[#ef4444] rounded-full"></span> Drawdown (%)
      </span>
      <span class="flex items-center gap-2">
        <span class="w-4 h-1 bg-[#f78c1f] rounded-full"></span> Price ($)
      </span>
    </div>
  </div>
</template>
