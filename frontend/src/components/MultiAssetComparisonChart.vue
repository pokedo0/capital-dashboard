<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { createChart, type IChartApi, type ISeriesApi, type MouseEventParams } from 'lightweight-charts';
import { useQuery } from '@tanstack/vue-query';
import TimeRangeSelector from './TimeRangeSelector.vue';
import LegendToggle from './LegendToggle.vue';
import FullscreenModal from './FullscreenModal.vue';
import TwoAssetHistogram from './TwoAssetHistogram.vue';
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
const HISTOGRAM_SYMBOLS: AssetSymbol[] = ['SPY', 'GLD', 'QQQ', 'BTC-USD'];
const HISTOGRAM_LABELS: Record<AssetSymbol, string> = {
  SPY: 'SPY',
  GLD: 'GLD',
  QQQ: 'QQQ',
  'BTC-USD': 'Bitcoin',
};

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
const hoverInfo = ref<
  | { time: string; entries: { label: string; color: string; value?: number }[]; position: { x: number; y: number } }
  | null
>(null);
const fullscreenHoverInfo = ref<
  | { time: string; entries: { label: string; color: string; value?: number }[]; position: { x: number; y: number } }
  | null
>(null);
const histogramBars = computed(() => {
  if (!data.value) return [];
  return HISTOGRAM_SYMBOLS.map((symbol) => {
    const series = data.value?.find((item) => item.symbol === symbol);
    if (!series || !series.points.length) return null;
    const lastPoint = series.points[series.points.length - 1];
    if (!lastPoint || typeof lastPoint.value !== 'number') return null;
    return { symbol: HISTOGRAM_LABELS[symbol] ?? symbol, value: lastPoint.value };
  }).filter((item): item is { symbol: string; value: number } => !!item);
});
let mainCrosshairHandler: ((param: MouseEventParams) => void) | null = null;
let fullscreenCrosshairHandler: ((param: MouseEventParams) => void) | null = null;
const extractValue = (point: unknown): number | undefined => {
  if (typeof point === 'object' && point && 'value' in point) {
    const value = (point as { value?: number }).value;
    return typeof value === 'number' ? value : undefined;
  }
  return undefined;
};

const measureHeight = (element: HTMLElement) => {
  const rect = element.getBoundingClientRect();
  return rect.height || element.clientHeight || element.offsetHeight || 360;
};

const initChart = (element: HTMLDivElement) => {
  const chart = createChart(element, {
    height: measureHeight(element),
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
  chart.applyOptions({ width: element.clientWidth, height: measureHeight(element) });
  return chart;
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

const applyData = (
  chart: IChartApi | null,
  map: Map<string, LineSeries>,
  hoverTarget: typeof hoverInfo,
  type: 'main' | 'fullscreen',
) => {
  if (!chart || !data.value) return;
  data.value.forEach((seriesData) => {
    if (!isAssetSymbol(seriesData.symbol)) return;
    const series = ensureSeries(chart, map, seriesData.symbol);
    series?.setData(seriesData.points.map((point) => ({ time: point.time, value: point.value })));
  });
  chart.timeScale().fitContent();
  syncVisibility(map);
  attachCrosshair(chart, map, hoverTarget, type);
};

const isAssetSymbol = (symbol: string): symbol is AssetSymbol =>
  (SYMBOLS as readonly string[]).includes(symbol as AssetSymbol);

const attachResize = (chart: IChartApi | null, container: HTMLDivElement | null, existing: ResizeObserver | null) => {
  existing?.disconnect();
  if (!chart || !container) return null;
  const observer = new ResizeObserver(() => {
    chart.applyOptions({ width: container.clientWidth, height: measureHeight(container) });
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
    applyData(mainChart, seriesMap, hoverInfo, 'main');
    if (showFullscreen.value && fullscreenChart) {
      applyData(fullscreenChart, fullscreenSeriesMap, fullscreenHoverInfo, 'fullscreen');
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
    fullscreenChart = initChart(fullscreenContainer.value);
    fullscreenObserver = attachResize(fullscreenChart, fullscreenContainer.value, fullscreenObserver);
    applyData(fullscreenChart, fullscreenSeriesMap, fullscreenHoverInfo, 'fullscreen');
  }
};

watch(showFullscreen, (open) => {
  if (!open && fullscreenChart) {
    if (fullscreenCrosshairHandler) {
      fullscreenChart.unsubscribeCrosshairMove(fullscreenCrosshairHandler);
      fullscreenCrosshairHandler = null;
    }
    fullscreenChart.remove();
    fullscreenSeriesMap.clear();
    fullscreenChart = null;
    fullscreenObserver?.disconnect();
    fullscreenObserver = null;
    fullscreenHoverInfo.value = null;
  }
});

onBeforeUnmount(() => {
  if (mainChart && mainCrosshairHandler) {
    mainChart.unsubscribeCrosshairMove(mainCrosshairHandler);
    mainCrosshairHandler = null;
  }
  mainChart?.remove();
  mainObserver?.disconnect();
  if (fullscreenChart && fullscreenCrosshairHandler) {
    fullscreenChart.unsubscribeCrosshairMove(fullscreenCrosshairHandler);
    fullscreenCrosshairHandler = null;
  }
  fullscreenChart?.remove();
  fullscreenObserver?.disconnect();
  fullscreenHoverInfo.value = null;
});

const legendItems = SYMBOLS.map((symbol) => ({
  key: symbol,
  label: symbol === 'BTC-USD' ? 'Bitcoin' : symbol,
  color: COLORS[symbol],
}));

const attachCrosshair = (
  chart: IChartApi | null,
  map: Map<string, LineSeries>,
  hoverTarget: typeof hoverInfo,
  type: 'main' | 'fullscreen',
) => {
  if (!chart) return;
  const handler = (param: MouseEventParams) => {
    if (!param.time || !param.point) {
      hoverTarget.value = null;
      return;
    }
    const time =
      typeof param.time === 'string'
        ? param.time
        : new Date((param.time as number) * 1000).toISOString().split('T')[0] || '';
    const entries = Array.from(map.entries()).map(([symbol, series]) => {
      const point = param.seriesData.get(series);
      return {
        label: symbol === 'BTC-USD' ? 'Bitcoin' : symbol,
        color: COLORS[symbol as AssetSymbol],
        value: extractValue(point),
      };
    });
    hoverTarget.value = { time, entries, position: { x: param.point.x, y: param.point.y } };
  };
  if (type === 'main') {
    if (mainCrosshairHandler) {
      chart.unsubscribeCrosshairMove(mainCrosshairHandler);
    }
    mainCrosshairHandler = handler;
  } else {
    if (fullscreenCrosshairHandler) {
      chart.unsubscribeCrosshairMove(fullscreenCrosshairHandler);
    }
    fullscreenCrosshairHandler = handler;
  }
  chart.subscribeCrosshairMove(handler);
};
</script>

<template>
  <div class="bg-panel border border-white/10 rounded-xl p-4 flex flex-col gap-4">
    <div class="flex flex-wrap justify-between items-center gap-4">
      <div>
        <div class="text-xl text-white font-semibold uppercase">SPY vs GLD</div>
      </div>
      <div class="flex items-center gap-3">
        <TimeRangeSelector v-model="rangeKey" :options="['1W', '1M', '3M', 'YTD', '1Y', '5Y']" />
        <button class="px-3 py-1 border border-white/20 rounded text-textMuted hover:text-white" @click="openFullscreen">
          Fullscreen
        </button>
      </div>
    </div>
    <div class="grid gap-4 w-full xl:grid-cols-[3fr,1fr]">
      <div class="relative flex-1 w-full min-h-[360px]">
        <div ref="mainContainer" class="absolute inset-0"></div>
        <div
          v-if="hoverInfo"
          class="absolute bg-black/80 border border-white/20 rounded px-3 py-2 text-xs text-white pointer-events-none z-50 max-w-[220px]"
          :style="{ left: `calc(${hoverInfo.position.x}px + 12px)`, top: `calc(${hoverInfo.position.y}px - 40px)` }"
        >
          <div>{{ hoverInfo.time }}</div>
          <div v-for="entry in hoverInfo.entries" :key="entry.label" class="flex justify-between gap-3">
            <span :style="{ color: entry.color }">{{ entry.label }}</span>
            <span>{{ entry.value?.toFixed(2) ?? '--' }}%</span>
          </div>
        </div>
      </div>
      <TwoAssetHistogram v-if="histogramBars.length" :bars="histogramBars" bare />
    </div>
    <LegendToggle v-model:activeKeys="activeKeys" :items="legendItems" />
    <FullscreenModal :open="showFullscreen" title="Multi-Asset Comparison" @close="showFullscreen = false">
      <div class="flex flex-col gap-4 w-full h-full">
        <div class="relative flex-1 min-h-[420px]">
          <div ref="fullscreenContainer" class="absolute inset-0"></div>
          <div
            v-if="fullscreenHoverInfo"
            class="absolute bg-black/80 border border-white/20 rounded px-3 py-2 text-xs text-white pointer-events-none z-50 max-w-[220px]"
            :style="{ left: `calc(${fullscreenHoverInfo.position.x}px + 12px)`, top: `calc(${fullscreenHoverInfo.position.y}px - 40px)` }"
          >
            <div>{{ fullscreenHoverInfo.time }}</div>
            <div v-for="entry in fullscreenHoverInfo.entries" :key="entry.label" class="flex justify-between gap-3">
              <span :style="{ color: entry.color }">{{ entry.label }}</span>
              <span>{{ entry.value?.toFixed(2) ?? '--' }}%</span>
            </div>
          </div>
        </div>
        <LegendToggle v-model:activeKeys="activeKeys" :items="legendItems" />
      </div>
    </FullscreenModal>
  </div>
</template>
