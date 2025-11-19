<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { createChart, type IChartApi, type ISeriesApi, type MouseEventParams } from 'lightweight-charts';
import { useQuery } from '@tanstack/vue-query';
import TimeRangeSelector from './TimeRangeSelector.vue';
import LegendToggle from './LegendToggle.vue';
import { fetchMarketBreadth } from '../services/api';

type LineSeries = ISeriesApi<'Line'>;

const BREADTH_SYMBOLS = ['$NDTW', '$NDFI', '$NDTH'] as const;
const COLOR_MAP: Record<string, string> = {
  '^NDX': '#f5f5f5',
  '$NDTW': '#38bdf8',
  '$NDFI': '#facc15',
  '$NDTH': '#fb7185',
};

const rangeKey = ref('1M');
const activeSymbols = ref<string[]>(['$NDTW']);

const { data, refetch } = useQuery({
  queryKey: computed(() => ['market-breadth', rangeKey.value]),
  queryFn: () => fetchMarketBreadth([...BREADTH_SYMBOLS], rangeKey.value),
});

watch(rangeKey, () => refetch());

const container = ref<HTMLDivElement | null>(null);
let chart: IChartApi | null = null;
let resizeObserver: ResizeObserver | null = null;
let crosshairHandler: ((param: MouseEventParams) => void) | null = null;
const seriesMap = new Map<string, LineSeries>();

const hoverInfo = ref<
  | {
      time: string;
      entries: { label: string; color: string; value?: number }[];
      position: { x: number; y: number };
    }
  | null
>(null);

const legendItems = BREADTH_SYMBOLS.map((symbol) => ({
  key: symbol,
  label: symbol.replace('$', ''),
  color: COLOR_MAP[symbol] ?? '#ffffff',
}));

const measureHeight = (el: HTMLElement): number => el.getBoundingClientRect().height || 360;

const initChart = (el: HTMLDivElement): IChartApi =>
  createChart(el, {
    height: measureHeight(el),
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

const ensureSeries = (symbol: string): LineSeries | null => {
  if (!chart) return null;
  if (seriesMap.has(symbol)) return seriesMap.get(symbol)!;
  const series = chart.addLineSeries({
    color: COLOR_MAP[symbol] ?? '#ffffff',
    lineWidth: symbol === '^NDX' ? 2 : 2,
    lineStyle: symbol === '^NDX' ? 1 : 0,
  });
  seriesMap.set(symbol, series);
  return series;
};

const applyVisibility = () => {
  const active = new Set(activeSymbols.value);
  seriesMap.forEach((series, symbol) => {
    if (symbol === '^NDX') {
      series.applyOptions({ visible: true });
      return;
    }
    series.applyOptions({ visible: active.has(symbol) });
  });
};

const applyData = () => {
  if (!chart || !data.value) return;
  const benchmarkSeries = ensureSeries('^NDX');
  benchmarkSeries?.setData(
    data.value.benchmark.points.map((point) => ({ time: point.time, value: point.value })),
  );
  data.value.series.forEach((seriesData) => {
    const series = ensureSeries(seriesData.symbol);
    series?.setData(seriesData.points.map((point) => ({ time: point.time, value: point.value })));
  });
  applyVisibility();
  chart.timeScale().fitContent();
  attachCrosshair();
};

const attachResizeObserver = (el: HTMLDivElement) => {
  resizeObserver?.disconnect();
  resizeObserver = new ResizeObserver(() => {
    if (!chart) return;
    chart.applyOptions({ width: el.clientWidth, height: measureHeight(el) });
  });
  resizeObserver.observe(el);
};

const extractValue = (value: unknown): number | undefined => {
  if (typeof value === 'object' && value && 'value' in value) {
    const candidate = (value as { value?: number }).value;
    return typeof candidate === 'number' ? candidate : undefined;
  }
  return undefined;
};

const attachCrosshair = () => {
  if (!chart) return;
  if (crosshairHandler) {
    chart.unsubscribeCrosshairMove(crosshairHandler);
  }
  crosshairHandler = (param: MouseEventParams) => {
    if (!param.time || !param.point) {
      hoverInfo.value = null;
      return;
    }
    const time =
      typeof param.time === 'string'
        ? param.time
        : new Date((param.time as number) * 1000).toISOString().split('T')[0] || '';
    const entries = Array.from(seriesMap.entries())
      .filter(([symbol]) => symbol === '^NDX' || activeSymbols.value.includes(symbol))
      .map(([symbol, series]) => {
        const value = param.seriesData.get(series);
        return {
          label: symbol === '^NDX' ? 'NDX' : symbol.replace('$', ''),
          color: COLOR_MAP[symbol] ?? '#ffffff',
          value: extractValue(value),
        };
      });
    hoverInfo.value = {
      time,
      entries,
      position: { x: param.point.x, y: param.point.y },
    };
  };
  chart.subscribeCrosshairMove(crosshairHandler);
};

watch(
  () => data.value,
  async () => {
    if (container.value && !chart) {
      await nextTick();
      if (container.value && !chart) {
        chart = initChart(container.value);
        attachResizeObserver(container.value);
      }
    }
    applyData();
  },
  { immediate: true },
);

watch(activeSymbols, () => {
  applyVisibility();
});

onBeforeUnmount(() => {
  if (chart && crosshairHandler) {
    chart.unsubscribeCrosshairMove(crosshairHandler);
  }
  chart?.remove();
  resizeObserver?.disconnect();
  seriesMap.clear();
});
</script>

<template>
  <div class="bg-panel border border-white/10 rounded-xl p-4 flex flex-col gap-4 h-full">
    <div class="flex flex-wrap justify-between items-center gap-4">
      <div>
        <div class="text-xl text-accentCyan font-semibold uppercase">
          Nasdaq 100 Stocks Above 20-Day Average
        </div>
        <div class="flex items-center gap-2 text-xs text-textMuted mt-1">
          <span class="w-4 h-1 rounded-full" :style="{ backgroundColor: COLOR_MAP['^NDX'] }"></span>
          <span>NDX (Benchmark)</span>
        </div>
      </div>
      <TimeRangeSelector v-model="rangeKey" :options="['1W', '1M', '3M', 'YTD', '1Y', '5Y']" />
    </div>
    <div class="relative flex-1 w-full min-h-[360px]">
      <div ref="container" class="absolute inset-0"></div>
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
    <div class="flex flex-col gap-2">
      <div class="text-xs uppercase tracking-wide text-textMuted">Toggle Breadth Indicators</div>
      <LegendToggle v-model:activeKeys="activeSymbols" :items="legendItems" />
    </div>
  </div>
</template>
