<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { createChart, type IChartApi, type ISeriesApi } from 'lightweight-charts';
import { useQuery } from '@tanstack/vue-query';
import TimeRangeSelector from './TimeRangeSelector.vue';
import { fetchDrawdown } from '../services/api';

type AreaSeries = ISeriesApi<'Area'>;
type LineSeries = ISeriesApi<'Line'>;

const SYMBOLS = ['SPY', 'TSLA', 'NVDA', 'AAPL', 'MSFT', 'META'];

const selectedSymbol = ref('SPY');
const rangeKey = ref('1Y');
const chartContainer = ref<HTMLDivElement | null>(null);

const { data, refetch } = useQuery({
  queryKey: computed(() => ['drawdown', selectedSymbol.value, rangeKey.value]),
  queryFn: () => fetchDrawdown(selectedSymbol.value, rangeKey.value),
});

watch([selectedSymbol, rangeKey], () => refetch());

let chart: IChartApi | null = null;
let fillAreaSeries: AreaSeries | null = null;
let maskAreaSeries: AreaSeries | null = null;
let drawdownLineSeries: LineSeries | null = null;
let priceSeries: LineSeries | null = null;
let baselineSeries: LineSeries | null = null;
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
      scaleMargins: { top: 0.05, bottom: 0.05 },
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
  chart.priceScale('left').applyOptions({
    borderVisible: false,
    scaleMargins: { top: 0.02, bottom: 0.02 },
    entireTextOnly: true,
  });

  fillAreaSeries = chart.addAreaSeries({
    priceScaleId: 'left',
    lineColor: 'rgba(37,99,235,0)',
    topColor: 'rgba(37,99,235,0.85)',
    bottomColor: 'rgba(37,99,235,0.85)',
  });
  maskAreaSeries = chart.addAreaSeries({
    priceScaleId: 'left',
    lineColor: '#050505',
    topColor: '#050505',
    bottomColor: '#050505',
  });
  drawdownLineSeries = chart.addLineSeries({
    priceScaleId: 'left',
    color: 'rgba(248,113,113,0.0001)',
    lineWidth: 2,
    priceFormat: {
      type: 'custom',
      formatter: (price: number) => `${price.toFixed(0)}%`,
      minMove: 0.01,
    },
  });
  priceSeries = chart.addLineSeries({
    priceScaleId: 'right',
    color: '#f78c1f',
    lineWidth: 2,
  });
  baselineSeries = chart.addLineSeries({
    priceScaleId: 'left',
    color: '#ef4444',
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
  fillAreaSeries = null;
  maskAreaSeries = null;
  drawdownLineSeries = null;
  priceSeries = null;
  baselineSeries = null;
};

onBeforeUnmount(disposeChart);

watch(
  () => data.value,
  (payload) => {
    if (!payload || !chartContainer.value) return;
    if (!chart) {
      initChart();
    }
    if (
      !chart ||
      !fillAreaSeries ||
      !maskAreaSeries ||
      !drawdownLineSeries ||
      !priceSeries ||
      !baselineSeries
    ) {
      return;
    }

    const drawdownData = payload.drawdown.map((point) => ({ time: point.time, value: point.value }));
    fillAreaSeries.setData(drawdownData.map((point) => ({ time: point.time, value: 0 })));
    maskAreaSeries.setData(drawdownData);
    drawdownLineSeries.setData(drawdownData);
    priceSeries.setData(payload.price.map((point) => ({ time: point.time, value: point.value })));
    baselineSeries.setData(
      payload.drawdown.map((point) => ({
        time: point.time,
        value: -30,
      })),
    );
    chart.timeScale().fitContent();
  },
  { immediate: true },
);

const currentDrawdown = computed(() => data.value?.current_drawdown ?? 0);
const yAxisValues = computed(() => {
  const points = data.value?.drawdown ?? [];
  let minValue = points.reduce((acc, point) => Math.min(acc, point.value ?? 0), 0);
  if (!Number.isFinite(minValue)) {
    minValue = 0;
  }
  minValue = Math.min(minValue, -5);
  const step = 5;
  const lowerBound = Math.floor(minValue / step) * step;
  const values: number[] = [];
  for (let value = 0; value >= lowerBound; value -= step) {
    values.push(value);
  }
  return values;
});
</script>

<template>
  <div class="bg-panel border border-white/10 rounded-xl p-4 flex flex-col gap-4 relative">
    <div class="flex flex-wrap justify-between items-center gap-4">
      <div>
        <div class="text-xl font-semibold uppercase">{{ selectedSymbol }} Drawdown</div>
        <div class="text-sm text-textMuted flex items-center gap-2">
          <span>Current drawdown:</span>
          <span class="text-white font-semibold">{{ currentDrawdown.toFixed(2) }}%</span>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <select v-model="selectedSymbol" class="bg-panel border border-white/20 rounded px-3 py-1 text-white">
          <option v-for="symbol in SYMBOLS" :key="symbol" :value="symbol">{{ symbol }}</option>
        </select>
        <TimeRangeSelector v-model="rangeKey" />
      </div>
    </div>
    <div class="flex w-full h-[320px] relative">
      <div class="w-14 flex flex-col justify-between text-xs text-textMuted pr-2">
        <span v-for="value in yAxisValues" :key="value">{{ value.toFixed(0) }}%</span>
      </div>
      <div ref="chartContainer" class="flex-1 h-full relative">
        <div class="absolute top-4 left-1/2 -translate-x-1/2 text-accentRed text-sm font-semibold">
          Baseline -30%
        </div>
        <div class="absolute top-12 right-4 text-white text-sm font-semibold">
          {{ currentDrawdown.toFixed(2) }}%
        </div>
      </div>
    </div>
    <div class="text-xs uppercase tracking-wide flex gap-4 text-textMuted">
      <span class="flex items-center gap-2">
        <span class="w-4 h-1 bg-[#1d4ed8] rounded-full"></span> Drawdown (%)
      </span>
      <span class="flex items-center gap-2">
        <span class="w-4 h-1 bg-[#f78c1f] rounded-full"></span> Price ($)
      </span>
      <span class="flex items-center gap-2">
        <span class="w-4 h-1 bg-[#ef4444] rounded-full"></span> Baseline -30%
      </span>
    </div>
  </div>
</template>
