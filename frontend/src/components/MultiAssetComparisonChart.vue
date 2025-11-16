<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { createChart, type IChartApi, type ISeriesApi } from 'lightweight-charts';
import { useQuery } from '@tanstack/vue-query';
import TimeRangeSelector from './TimeRangeSelector.vue';
import LegendToggle from './LegendToggle.vue';
import FullscreenModal from './FullscreenModal.vue';
import { fetchRelativePerformance } from '../services/api';

type LineSeries = ISeriesApi<'Line'>;

const SYMBOLS = ['SPY', 'GLD', 'QQQ', 'BTC-USD'] as const;
type AssetSymbol = (typeof SYMBOLS)[number];
const SYMBOL_PARAMS: string[] = [...SYMBOLS];
const COLORS: Record<AssetSymbol, string> = {
  SPY: '#f87171',
  GLD: '#fde047',
  QQQ: '#60a5fa',
  'BTC-USD': '#f97316',
};

const rangeKey = ref('1Y');
const activeKeys = ref<string[]>([...SYMBOLS]);
const showFullscreen = ref(false);

const { data, refetch } = useQuery({
  queryKey: computed(() => ['relative', 'multi', rangeKey.value]),
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

const initChart = (element: HTMLDivElement, height = 280) => {
  return createChart(element, {
    height,
    layout: {
      background: { color: '#050505' },
      textColor: '#f8fafc',
      fontFamily: "'IBM Plex Sans', Inter, ui-sans-serif",
    },
    grid: {
      horzLines: { color: 'rgba(255,255,255,0.08)' },
      vertLines: { color: 'rgba(255,255,255,0.05)' },
    },
    rightPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false, timeVisible: true },
  });
};

const ensureSeries = (chart: IChartApi | null, map: Map<string, LineSeries>, symbol: AssetSymbol) => {
  if (!chart) return null;
  if (map.has(symbol)) return map.get(symbol)!;
  const series = chart.addLineSeries({
    color: COLORS[symbol],
    lineWidth: symbol === 'BTC-USD' ? 3 : 2,
  });
  map.set(symbol, series);
  return series;
};

const applyData = (chart: IChartApi | null, map: Map<string, LineSeries>) => {
  if (!chart || !data.value) return;
  data.value.forEach((seriesData) => {
    if (!isAssetSymbol(seriesData.symbol)) return;
    const series = ensureSeries(chart, map, seriesData.symbol);
    series?.setData(seriesData.points.map((point) => ({ time: point.time, value: point.value })));
  });
  chart.timeScale().fitContent();
  syncVisibility(map);
};

const isAssetSymbol = (symbol: string): symbol is AssetSymbol =>
  (SYMBOLS as readonly string[]).includes(symbol as AssetSymbol);

const attachResize = (chart: IChartApi | null, container: HTMLDivElement | null, existing: ResizeObserver | null) => {
  existing?.disconnect();
  if (!chart || !container) return null;
  const observer = new ResizeObserver(() => {
    chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
  });
  observer.observe(container);
  return observer;
};

const syncVisibility = (map: Map<string, LineSeries>) => {
  const visible = new Set(activeKeys.value);
  map.forEach((series, key) => {
    series.applyOptions({ visible: visible.has(key) });
  });
};

watch(
  () => data.value,
  () => {
    if (mainContainer.value && !mainChart) {
      mainChart = initChart(mainContainer.value);
      mainObserver = attachResize(mainChart, mainContainer.value, mainObserver);
    }
    applyData(mainChart, seriesMap);
    if (showFullscreen.value && fullscreenChart) {
      applyData(fullscreenChart, fullscreenSeriesMap);
    }
  },
  { immediate: true },
);

watch(activeKeys, () => {
  syncVisibility(seriesMap);
  syncVisibility(fullscreenSeriesMap);
});

const openFullscreen = async () => {
  showFullscreen.value = true;
  await nextTick();
  if (fullscreenContainer.value) {
    fullscreenChart = initChart(fullscreenContainer.value, 420);
    fullscreenObserver = attachResize(fullscreenChart, fullscreenContainer.value, fullscreenObserver);
    applyData(fullscreenChart, fullscreenSeriesMap);
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
  label: symbol === 'BTC-USD' ? 'Bitcoin' : symbol,
  color: COLORS[symbol],
}));
</script>

<template>
  <div class="bg-panel border border-white/10 rounded-xl p-4 flex flex-col gap-4">
    <div class="flex flex-wrap justify-between items-center gap-4">
      <div>
        <div class="text-xl text-white font-semibold uppercase">SPY vs GLD (YTD)</div>
        <p class="text-textMuted text-sm">Compare ETF and Bitcoin relative returns</p>
      </div>
      <div class="flex items-center gap-3">
        <TimeRangeSelector v-model="rangeKey" :options="['3M', '6M', '1Y']" />
        <button class="px-3 py-1 border border-white/20 rounded text-textMuted hover:text-white" @click="openFullscreen">
          Fullscreen
        </button>
      </div>
    </div>
    <div ref="mainContainer" class="w-full h-[280px]"></div>
    <LegendToggle v-model:activeKeys="activeKeys" :items="legendItems" />
    <FullscreenModal :open="showFullscreen" title="Multi-Asset Comparison" @close="showFullscreen = false">
      <div ref="fullscreenContainer" class="w-full h-full min-h-[420px]"></div>
    </FullscreenModal>
  </div>
</template>
