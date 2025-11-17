<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { createChart, type IChartApi, type ISeriesApi, type MouseEventParams } from 'lightweight-charts';
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
let mainCrosshairHandler: ((param: MouseEventParams) => void) | null = null;
const hoverInfo = ref<
  | {
      time: string;
      entries: { label: string; color: string; value?: number }[];
      position: { x: number; y: number };
    }
  | null
>(null);
const extractValue = (point: unknown): number | undefined => {
  if (typeof point === 'object' && point && 'value' in point) {
    const value = (point as { value?: number }).value;
    return typeof value === 'number' ? value : undefined;
  }
  return undefined;
};

const initChart = (container: HTMLDivElement): IChartApi => {
  const chartHeight = container.clientHeight || 360;
  return createChart(container, {
    height: chartHeight,
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
  if (chart === mainChart) {
    attachCrosshair();
  }
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

const attachCrosshair = () => {
  if (!mainChart) return;
  if (mainCrosshairHandler) {
    mainChart.unsubscribeCrosshairMove(mainCrosshairHandler);
  }
  mainCrosshairHandler = (param: MouseEventParams) => {
    if (!param.time || !param.point) {
      hoverInfo.value = null;
      return;
    }
    const time =
      typeof param.time === 'string'
        ? param.time
        : new Date((param.time as number) * 1000).toISOString().split('T')[0] || '';
    const entries = Array.from(seriesMap.entries()).map(([symbol, series]) => {
      const value = param.seriesData.get(series);
      return {
        label: symbol === '^NDX' ? 'NDX' : symbol,
        color: COLOR_MAP[symbol as SymbolKey] ?? '#fff',
        value: extractValue(value),
      };
    });
    hoverInfo.value = { time, entries, position: { x: param.point.x, y: param.point.y } };
  };
  mainChart.subscribeCrosshairMove(mainCrosshairHandler);
};
</script>

<template>
  <div class="bg-panel border border-white/10 rounded-xl p-4 flex flex-col gap-4">
    <div class="flex flex-wrap justify-between items-center gap-4">
      <div>
        <div class="text-xl text-accentCyan font-semibold uppercase">Mag 7 Line Performance</div>      </div>
      <div class="flex items-center gap-3">
        <TimeRangeSelector v-model="rangeKey" :options="['1W', '1M', '3M', '6M']" />
        <button class="px-3 py-1 border border-white/20 rounded text-textMuted hover:text-white" @click="openFullscreen">
          Fullscreen
        </button>
      </div>
    </div>
    <div ref="mainContainer" class="w-full h-[360px] relative">
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
    <LegendToggle v-model:activeKeys="activeKeys" :items="legendItems" />
    <FullscreenModal :open="showFullscreen" title="Mag 7 Relative Performance" @close="showFullscreen = false">
      <div ref="fullscreenContainer" class="w-full h-full min-h-[420px]"></div>
    </FullscreenModal>
  </div>
</template>
