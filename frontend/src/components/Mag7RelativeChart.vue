<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import {
  createChart,
  LineSeries as LineSeriesDefinition,
  type IChartApi,
  type ISeriesApi,
  type MouseEventParams,
} from 'lightweight-charts';
import { useQuery } from '@tanstack/vue-query';
import TimeRangeSelector from './TimeRangeSelector.vue';
import LegendToggle from './LegendToggle.vue';
import FullscreenModal from './FullscreenModal.vue';
import { fetchRelativePerformance } from '../services/api';

type LineSeries = ISeriesApi<'Line'>;

const BASE_SYMBOLS = ['NVDA', 'GOOG', 'AMZN', 'AAPL', 'META', 'MSFT', 'TSLA', '^NDX'] as const;
const EXTENDED_SYMBOLS = [...BASE_SYMBOLS, 'AVGO', 'TSM'] as const;
type SymbolKey = (typeof EXTENDED_SYMBOLS)[number];
const SYMBOL_PARAMS: string[] = [...EXTENDED_SYMBOLS];
const COLOR_MAP: Record<SymbolKey, string> = {
  NVDA: '#9edc2f',
  GOOG: '#f5c242',
  AMZN: '#4f8fe6',
  AAPL: '#b58bff',
  META: '#6be0c6',
  MSFT: '#4f5dff',
  TSLA: '#d73737',
  '^NDX': '#f5f5f5',
  AVGO: '#fb7185',
  TSM: '#38bdf8',
};
const MS_PER_DAY = 24 * 60 * 60 * 1000;
const downsampleWeekly = (points: { time: string; value: number }[]) => {
  if (!points.length) return points;
  const result: typeof points = [];
  let lastSampleTime: number | null = null;
  points.forEach((point) => {
    const current = new Date(point.time).getTime();
    if (Number.isNaN(current)) {
      result.push(point);
      return;
    }
    if (lastSampleTime === null || current - lastSampleTime >= 7 * MS_PER_DAY) {
      result.push(point);
      lastSampleTime = current;
    } else {
      result[result.length - 1] = point;
    }
  });
  return result;
};

const rangeKey = ref('1M');
const lineupMode = ref<'M7' | 'M9'>('M7');
const displayedSymbols = computed(() =>
  lineupMode.value === 'M7' ? BASE_SYMBOLS : EXTENDED_SYMBOLS,
);
const activeKeys = ref<string[]>([...displayedSymbols.value]);
const showFullscreen = ref(false);

const { data, refetch } = useQuery({
  queryKey: computed(() => ['relative', 'mag7', rangeKey.value]),
  queryFn: () => fetchRelativePerformance(SYMBOL_PARAMS, rangeKey.value),
});

const transformedData = computed(() => {
  if (!data.value) return null;
  return data.value.map((series) => {
    let points = series.points;
    if (rangeKey.value === '5Y') {
      points = downsampleWeekly(points);
    }
    return { ...series, points };
  });
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
let fullscreenCrosshairHandler: ((param: MouseEventParams) => void) | null = null;
const hoverInfo = ref<
  | {
      time: string;
      entries: { label: string; color: string; value?: number }[];
      position: { x: number; y: number };
    }
  | null
>(null);
const fullscreenHoverInfo = ref<
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

const measureHeight = (element: HTMLElement): number => {
  const rect = element.getBoundingClientRect();
  return rect.height || element.clientHeight || 360;
};

const initChart = (container: HTMLDivElement): IChartApi => {
  const chartHeight = measureHeight(container);
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
  const series = chart.addSeries(LineSeriesDefinition, {
    color: COLOR_MAP[symbol] ?? '#ffffff',
    lineWidth: symbol === '^NDX' ? 3 : 2,
    lineStyle: symbol === '^NDX' ? 2 : 0,
    priceLineVisible: false,
  });
  map.set(symbol, series);
  return series;
};

const resetViewport = (chart: IChartApi | null) => {
  if (!chart) return;
  chart.timeScale().resetTimeScale();
  chart.timeScale().fitContent();
  chart.priceScale('right').applyOptions({ autoScale: true });
};

const applyRelativeData = (
  chart: IChartApi | null,
  map: Map<string, LineSeries>,
  hoverTarget: typeof hoverInfo,
  type: 'main' | 'fullscreen',
  payload: { symbol: string; points: { time: string; value: number }[] }[] | null,
) => {
  if (!chart || !payload) return;
  payload.forEach((seriesData) => {
    if (!isSymbolKey(seriesData.symbol)) return;
    const series = ensureSeries(chart, map, seriesData.symbol);
    series?.setData(seriesData.points.map((point) => ({ time: point.time, value: point.value })));
  });
  syncLegend(map);
  resetViewport(chart);
  attachCrosshair(chart, map, hoverTarget, type);
};

const isSymbolKey = (value: string): value is SymbolKey =>
  (EXTENDED_SYMBOLS as readonly string[]).includes(value as SymbolKey);

const attachResize = (chart: IChartApi | null, container: HTMLDivElement | null, existing: ResizeObserver | null) => {
  existing?.disconnect();
  if (!chart || !container) return null;
  const observer = new ResizeObserver(() => {
    chart.applyOptions({ width: container.clientWidth, height: measureHeight(container) });
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
  () => transformedData.value,
  async (seriesPayload) => {
    if (!seriesPayload) return;
    if (mainContainer.value && !mainChart) {
      await nextTick();
      if (mainContainer.value) {
        mainChart = initChart(mainContainer.value);
        mainObserver = attachResize(mainChart, mainContainer.value, mainObserver);
      }
    }
    applyRelativeData(mainChart, seriesMap, hoverInfo, 'main', seriesPayload);
    if (showFullscreen.value && fullscreenChart) {
      applyRelativeData(fullscreenChart, fullscreenSeriesMap, fullscreenHoverInfo, 'fullscreen', seriesPayload);
    }
  },
  { immediate: true },
);

watch(activeKeys, () => {
  syncLegend(seriesMap);
  syncLegend(fullscreenSeriesMap);
});

watch(lineupMode, (mode) => {
  const target = mode === 'M7' ? BASE_SYMBOLS : EXTENDED_SYMBOLS;
  activeKeys.value = [...target];
});

const openFullscreen = async () => {
  showFullscreen.value = true;
  await nextTick();
  if (fullscreenContainer.value) {
    fullscreenChart = initChart(fullscreenContainer.value);
    fullscreenObserver = attachResize(fullscreenChart, fullscreenContainer.value, fullscreenObserver);
    applyRelativeData(fullscreenChart, fullscreenSeriesMap, fullscreenHoverInfo, 'fullscreen', transformedData.value);
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

const legendItems = computed(() =>
  displayedSymbols.value.map((symbol) => ({
    key: symbol,
    label: symbol === '^NDX' ? 'NDX' : symbol,
    color: COLOR_MAP[symbol],
  })),
);

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
    const visible = new Set(activeKeys.value);
    const entries = Array.from(map.entries())
      .filter(([symbol]) => visible.has(symbol))
      .map(([symbol, series]) => {
        const value = param.seriesData.get(series);
        return {
          label: symbol === '^NDX' ? 'NDX' : symbol,
          color: COLOR_MAP[symbol as SymbolKey] ?? '#fff',
          value: extractValue(value),
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
  <div class="bg-panel border border-white/10 rounded-xl p-4 flex flex-col gap-4 h-full">
    <div class="flex flex-wrap justify-between items-center gap-4">
      <div>
        <div class="text-xl text-accentCyan font-semibold uppercase">Mag 7 Line Performance</div>      </div>
      <div class="flex items-center gap-3">
        <div class="flex bg-white/10 rounded-full overflow-hidden text-xs font-medium text-white">
          <button
            type="button"
            class="px-3 py-1 transition-colors"
            :class="lineupMode === 'M7' ? 'bg-accentCyan text-black' : 'text-white/70'"
            @click="lineupMode = 'M7'"
          >
            M7
          </button>
          <button
            type="button"
            class="px-3 py-1 transition-colors"
            :class="lineupMode === 'M9' ? 'bg-accentCyan text-black' : 'text-white/70'"
            @click="lineupMode = 'M9'"
          >
            M9
          </button>
        </div>
        <TimeRangeSelector v-model="rangeKey" :options="['1W', '1M', '3M', 'YTD', '1Y', '5Y']" />
        <button class="px-3 py-1 border border-white/20 rounded text-textMuted hover:text-white" @click="openFullscreen">
          Fullscreen
        </button>
      </div>
    </div>
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
    <LegendToggle v-model:activeKeys="activeKeys" :items="legendItems" />
    <FullscreenModal :open="showFullscreen" title="Mag 7 Relative Performance" @close="showFullscreen = false">
      <div class="flex flex-col gap-4 w-full h-full">
        <div class="relative flex-1 min-h-[420px]">
          <div ref="fullscreenContainer" class="absolute inset-0"></div>
          <div
            v-if="fullscreenHoverInfo"
            class="absolute bg-black/80 border border-white/20 rounded px-3 py-2 text-xs text-white pointer-events-none z-50 max-w-[220px]"
            :style="{
              left: `calc(${fullscreenHoverInfo.position.x}px + 12px)`,
              top: `calc(${fullscreenHoverInfo.position.y}px - 40px)`,
            }"
          >
            <div>{{ fullscreenHoverInfo.time }}</div>
            <div
              v-for="entry in fullscreenHoverInfo.entries"
              :key="entry.label"
              class="flex justify-between gap-3"
            >
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
