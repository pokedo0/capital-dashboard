<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { createChart, type IChartApi, type ISeriesApi, type MouseEventParams } from 'lightweight-charts';
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
let crosshairHandler: ((param: MouseEventParams) => void) | null = null;
const hoverInfo = ref<{ time: string; ratio?: number; average?: number; position: { x: number; y: number } } | null>(
  null,
);
const extractValue = (point: unknown): number | undefined => {
  if (typeof point === 'object' && point && 'value' in point) {
    const value = (point as { value?: number }).value;
    return typeof value === 'number' ? value : undefined;
  }
  return undefined;
};

const measureSize = (element: HTMLElement) => {
  const rect = element.getBoundingClientRect();
  const width = rect.width || element.clientWidth || element.offsetWidth || 600;
  const height = rect.height || element.clientHeight || element.offsetHeight || 320;
  return { width, height };
};

const initChart = () => {
  if (!chartContainer.value) return;
  disposeChart();
  const size = measureSize(chartContainer.value);
  chart = createChart(chartContainer.value, {
    height: size.height,
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
  chart.applyOptions({ width: size.width, height: size.height });

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
      const nextSize = measureSize(chartContainer.value);
      chart.applyOptions({ width: nextSize.width, height: nextSize.height });
    }
  });
  observer.observe(chartContainer.value);

  crosshairHandler = (param: MouseEventParams) => {
    if (!param.time || !param.point || !ratioSeries || !averageSeries) {
      hoverInfo.value = null;
      return;
    }
    const ratioPoint = param.seriesData.get(ratioSeries);
    const avgPoint = param.seriesData.get(averageSeries);
    const time =
      typeof param.time === 'string'
        ? param.time
        : new Date((param.time as number) * 1000).toISOString().split('T')[0] || '';
    hoverInfo.value = {
      time,
      ratio: extractValue(ratioPoint),
      average: extractValue(avgPoint),
      position: { x: param.point.x, y: param.point.y },
    };
  };
  chart.subscribeCrosshairMove(crosshairHandler);
};

const disposeChart = () => {
  observer?.disconnect();
  observer = null;
  if (chart && crosshairHandler) {
    chart.unsubscribeCrosshairMove(crosshairHandler);
  }
  chart?.remove();
  chart = null;
  crosshairHandler = null;
  hoverInfo.value = null;
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

const symbolInput = computed({
  get: () => selectedSymbol.value,
  set: (val: string) => {
    selectedSymbol.value = val.trim().toUpperCase();
  },
});

const benchmarkInput = computed({
  get: () => selectedBenchmark.value,
  set: (val: string) => {
    selectedBenchmark.value = val.trim().toUpperCase();
  },
});
</script>

<template>
  <div class="bg-panel border border-white/10 rounded-xl p-4 flex flex-col gap-4">
    <div class="flex flex-wrap justify-between items-center gap-4">
      <div>
        <div class="text-xl font-semibold uppercase">{{ selectedSymbol }} Relative {{ selectedBenchmark }}</div>
        <p class="text-sm text-textMuted">Price ratio (symbol / benchmark × 100) with 50-day average</p>
      </div>
      <div class="flex items-center gap-3">
        <div>
          <input
            v-model="symbolInput"
            list="relative-symbols"
            class="bg-panel border border-white/20 rounded px-3 py-1 text-white uppercase"
            placeholder="Symbol"
          />
          <datalist id="relative-symbols">
            <option v-for="symbol in SYMBOLS" :key="symbol" :value="symbol" />
          </datalist>
        </div>
        <div>
          <input
            v-model="benchmarkInput"
            list="relative-benchmarks"
            class="bg-panel border border-white/20 rounded px-3 py-1 text-white uppercase"
            placeholder="Benchmark"
          />
          <datalist id="relative-benchmarks">
            <option v-for="bm in BENCHMARKS" :key="bm" :value="bm" />
          </datalist>
        </div>
        <TimeRangeSelector v-model="rangeKey" :options="['6M', '1Y', '2Y']" />
      </div>
    </div>
    <div class="relative w-full flex-1 min-h-[320px]">
      <div ref="chartContainer" class="absolute inset-0"></div>
      <div
        v-if="hoverInfo"
        class="absolute bg-black/80 border border-white/20 rounded px-3 py-2 text-xs text-white pointer-events-none z-50"
        :style="{ left: `calc(${hoverInfo.position.x}px + 12px)`, top: `calc(${hoverInfo.position.y}px - 40px)` }"
      >
        <div>{{ hoverInfo.time }}</div>
        <div>Ratio: {{ hoverInfo.ratio?.toFixed(2) ?? '--' }}</div>
        <div>50D Avg: {{ hoverInfo.average?.toFixed(2) ?? '--' }}</div>
      </div>
    </div>
    <div class="text-xs uppercase tracking-wide flex gap-4 text-textMuted">
      <span class="flex items-center gap-2">
        <span class="w-4 h-1 bg-[#60a5fa] rounded-full"></span> Ratio
      </span>
      <span class="flex items-center gap-2">
        <span class="w-4 h-1 bg-[#f78c1f] rounded-full"></span> 50D Avg
      </span>
    </div>
  </div>
</template>
