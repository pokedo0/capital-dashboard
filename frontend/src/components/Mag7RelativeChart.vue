<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { createChart, type IChartApi, type ISeriesApi } from 'lightweight-charts';
import { useQuery } from '@tanstack/vue-query';
import TimeRangeSelector from './TimeRangeSelector.vue';
import LegendToggle from './LegendToggle.vue';
import FullscreenModal from './FullscreenModal.vue';
import { fetchRelativePerformance } from '../services/api';

type LineSeries = ISeriesApi<'Line'>;

const SYMBOLS = ['NVDA', 'GOOG', 'AMZN', 'AAPL', 'META', 'MSFT', 'TSLA', '^NDX'] as const;
type SymbolKey = (typeof SYMBOLS)[number];
const SYMBOL_PARAMS: string[] = [...SYMBOLS];
const COLOR_MAP: Record<SymbolKey, string> = {
  NVDA: '#a6ff0d',
  GOOG: '#facc15',
  AMZN: '#f97316',
  AAPL: '#c084fc',
  META: '#67f0d6',
  MSFT: '#60a5fa',
  TSLA: '#f87171',
  '^NDX': '#f5f5f5',
};

const rangeKey = ref('1M');
const activeKeys = ref<string[]>([...SYMBOLS]);
const showFullscreen = ref(false);

const { data, refetch } = useQuery({
  queryKey: computed(() => ['relative', 'mag7', rangeKey.value]),
  queryFn: () => fetchRelativePerformance(SYMBOL_PARAMS, rangeKey.value),
});

watch(rangeKey, () => refetch());

const mainContainer = ref<HTMLDivElement | null>(null);
const fullscreenContainer = ref<HTMLDivElement | null>(null);
let mainChart: IChartApi | null = null;
let fullscreenChart: IChartApi | null = null;
let mainObserver: ResizeObserver | null = null;
let fullscreenObserver: ResizeObserver | null = null;
const seriesMap = new Map<string, LineSeries>();
const fullscreenSeriesMap = new Map<string, LineSeries>();

const initChart = (container: HTMLDivElement): IChartApi => {
  return createChart(container, {
    height: 280,
    layout: {
      background: { color: '#050505' },
      textColor: '#f8fafc',
      fontFamily: "'IBM Plex Sans', Inter, ui-sans-serif",
    },
    grid: {
      horzLines: { color: 'rgba(255,255,255,0.08)' },
      vertLines: { color: 'rgba(255,255,255,0.05)' },
    },
    crosshair: { mode: 1 },
    rightPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false, timeVisible: true },
  });
};

const ensureSeries = (chart: IChartApi | null, map: Map<string, LineSeries>, symbol: SymbolKey) => {
  if (!chart) return null;
  if (map.has(symbol)) return map.get(symbol)!;
  const series = chart.addLineSeries({
    color: COLOR_MAP[symbol] ?? '#ffffff',
    lineWidth: symbol === '^NDX' ? 1 : 2,
    lineStyle: symbol === '^NDX' ? 1 : 0,
  });
  map.set(symbol, series);
  return series;
};

const applyRelativeData = (chart: IChartApi | null, map: Map<string, LineSeries>) => {
  if (!chart || !data.value) return;
  data.value.forEach((seriesData) => {
    if (!isSymbolKey(seriesData.symbol)) return;
    const series = ensureSeries(chart, map, seriesData.symbol);
    series?.setData(seriesData.points.map((point) => ({ time: point.time, value: point.value })));
  });
  chart.timeScale().fitContent();
  syncLegend(map);
};

const isSymbolKey = (value: string): value is SymbolKey =>
  (SYMBOLS as readonly string[]).includes(value as SymbolKey);

const attachResize = (chart: IChartApi | null, container: HTMLDivElement | null, existing: ResizeObserver | null) => {
  existing?.disconnect();
  if (!chart || !container) return null;
  const observer = new ResizeObserver(() => {
    chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
  });
  observer.observe(container);
  return observer;
};

const syncLegend = (map: Map<string, LineSeries>) => {
  const visible = new Set(activeKeys.value);
  map.forEach((series, symbol) => {
    series.applyOptions({ visible: visible.has(symbol) });
  });
};

watch(
  () => data.value,
  () => {
    if (mainContainer.value && !mainChart) {
      mainChart = initChart(mainContainer.value);
      mainObserver = attachResize(mainChart, mainContainer.value, mainObserver);
    }
    applyRelativeData(mainChart, seriesMap);
    if (showFullscreen.value && fullscreenChart) {
      applyRelativeData(fullscreenChart, fullscreenSeriesMap);
    }
  },
  { immediate: true },
);

watch(activeKeys, () => {
  syncLegend(seriesMap);
  syncLegend(fullscreenSeriesMap);
});

const openFullscreen = async () => {
  showFullscreen.value = true;
  await nextTick();
  if (fullscreenContainer.value) {
    fullscreenChart = initChart(fullscreenContainer.value);
    fullscreenObserver = attachResize(fullscreenChart, fullscreenContainer.value, fullscreenObserver);
    applyRelativeData(fullscreenChart, fullscreenSeriesMap);
  }
};

watch(showFullscreen, (open) => {
  if (!open && fullscreenChart) {
    fullscreenChart.remove();
    fullscreenSeriesMap.clear();
    fullscreenChart = null;
    fullscreenObserver?.disconnect();
    fullscreenObserver = null;
  }
});

onBeforeUnmount(() => {
  mainChart?.remove();
  mainObserver?.disconnect();
  fullscreenChart?.remove();
  fullscreenObserver?.disconnect();
});

const legendItems = SYMBOLS.map((symbol) => ({
  key: symbol,
  label: symbol === '^NDX' ? 'NDX' : symbol,
  color: COLOR_MAP[symbol],
}));
</script>

<template>
  <div class="bg-panel border border-white/10 rounded-xl p-4 flex flex-col gap-4">
    <div class="flex flex-wrap justify-between items-center gap-4">
      <div>
        <div class="text-xl text-accentCyan font-semibold uppercase">Mag7 Nov Performance</div>
        <p class="text-textMuted text-sm">Relative performance since selected period</p>
      </div>
      <div class="flex items-center gap-3">
        <TimeRangeSelector v-model="rangeKey" :options="['1W', '1M', '3M', '6M']" />
        <button class="px-3 py-1 border border-white/20 rounded text-textMuted hover:text-white" @click="openFullscreen">
          Fullscreen
        </button>
      </div>
    </div>
    <div ref="mainContainer" class="w-full h-[280px]"></div>
    <LegendToggle v-model:activeKeys="activeKeys" :items="legendItems" />
    <FullscreenModal :open="showFullscreen" title="Mag 7 Relative Performance" @close="showFullscreen = false">
      <div ref="fullscreenContainer" class="w-full h-full min-h-[360px]"></div>
    </FullscreenModal>
  </div>
</template>
