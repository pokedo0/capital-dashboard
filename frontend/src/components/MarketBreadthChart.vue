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
import { fetchMarketBreadth } from '../services/api';

type LineSeries = ISeriesApi<'Line'>;

const BREADTH_OPTIONS = [
  { value: '$NDTW', label: 'NDTW - Above 20-Day Average' },
  { value: '$NDFI', label: 'NDFI - Above 50-Day Average' },
  { value: '$NDTH', label: 'NDTH - Above 200-Day Average' },
] as const;
type BreadthSymbol = (typeof BREADTH_OPTIONS)[number]['value'];

const COLOR_MAP: Record<string, string> = {
  '^NDX': '#f04949',
  '$NDTW': '#f04949',
  '$NDFI': '#f04949',
  '$NDTH': '#f04949',
};
const PRICE_COLOR = '#bdc3c7';

const rangeKey = ref('1M');
const selectedSymbol = ref<BreadthSymbol>(BREADTH_OPTIONS[0].value);
const selectedOption = computed(
  () => BREADTH_OPTIONS.find((option) => option.value === selectedSymbol.value) ?? BREADTH_OPTIONS[0],
);

const { data, refetch } = useQuery({
  queryKey: computed(() => ['market-breadth', rangeKey.value, selectedSymbol.value]),
  queryFn: () => fetchMarketBreadth([selectedSymbol.value], rangeKey.value),
});

watch([rangeKey, selectedSymbol], () => refetch());

const container = ref<HTMLDivElement | null>(null);
let chart: IChartApi | null = null;
let priceSeries: LineSeries | null = null;
let breadthSeries: LineSeries | null = null;
let breadthSymbol: string | null = null;
let resizeObserver: ResizeObserver | null = null;
let crosshairHandler: ((param: MouseEventParams) => void) | null = null;

type TooltipEntry = { label: string; color: string; value?: number; unit: 'percent' | 'index' };

const hoverInfo = ref<
  | {
      time: string;
      entries: TooltipEntry[];
      position: { x: number; y: number };
    }
  | null
>(null);

const measureHeight = (el: HTMLElement): number => el.getBoundingClientRect().height || 360;

const tooltipStyle = (position: { x: number; y: number }, container: HTMLElement | null) => {
  const padding = 12;
  const offsetX = 16;
  const offsetY = 12;
  const containerWidth = container?.clientWidth ?? 0;
  const containerHeight = container?.clientHeight ?? 0;
  const tooltipWidth = 220;
  const tooltipHeight = 140;

  let left = position.x + offsetX;
  if (containerWidth) {
    left = Math.min(Math.max(left, padding), containerWidth - tooltipWidth - padding);
  }

  let top = position.y + offsetY;
  if (containerHeight) {
    top = Math.min(Math.max(top, padding), containerHeight - tooltipHeight - padding);
  }

  return { left: `${left}px`, top: `${top}px` };
};

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
    leftPriceScale: { visible: true, borderVisible: false },
    rightPriceScale: { visible: true, borderVisible: false },
    timeScale: { borderVisible: false, timeVisible: true },
  });

const ensureBreadthSeries = () => {
  if (!chart) return null;
  if (!breadthSeries || breadthSymbol !== selectedSymbol.value) {
    if (breadthSeries) {
      chart.removeSeries(breadthSeries);
    }
    breadthSeries = chart.addSeries(LineSeriesDefinition, {
      color: COLOR_MAP[selectedSymbol.value] ?? '#ffffff',
      lineWidth: 2,
      priceScaleId: 'left',
    });
    breadthSymbol = selectedSymbol.value;
  } else {
    breadthSeries.applyOptions({ color: COLOR_MAP[selectedSymbol.value] ?? '#ffffff' });
  }
  return breadthSeries;
};

const ensurePriceSeries = () => {
  if (!chart) return null;
  if (priceSeries) return priceSeries;
  priceSeries = chart.addSeries(LineSeriesDefinition, {
    color: PRICE_COLOR,
    lineWidth: 2,
    priceScaleId: 'right',
  });
  return priceSeries;
};

const applyData = () => {
  if (!chart || !data.value) return;
  const breadth = data.value.series[0];
  const breadthLine = ensureBreadthSeries();
  breadthLine?.setData(
    (breadth?.points ?? []).map((point) => ({ time: point.time, value: point.value })),
  );

  const ndxPriceSeries = ensurePriceSeries();
  ndxPriceSeries?.setData(
    data.value.benchmark_price.map((point) => ({ time: point.time, value: point.value })),
  );
  chart.priceScale('left').applyOptions({ autoScale: true, borderVisible: false });
  chart.priceScale('right').applyOptions({ autoScale: true, borderVisible: false });

  chart.timeScale().fitContent();
  attachCrosshair();
};

const attachResizeObserver = (el: HTMLDivElement) => {
  resizeObserver?.disconnect();
  resizeObserver = new ResizeObserver(() => {
    chart?.applyOptions({ width: el.clientWidth, height: measureHeight(el) });
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
    const entries: TooltipEntry[] = [];
    if (breadthSeries) {
      const breadthValue = param.seriesData.get(breadthSeries);
      entries.push({
        label: selectedOption.value.label,
        color: COLOR_MAP[selectedSymbol.value] ?? '#ffffff',
        value: extractValue(breadthValue),
        unit: 'percent',
      });
    }
    if (priceSeries) {
      const priceValue = param.seriesData.get(priceSeries);
      entries.push({
        label: 'NDX Index',
        color: PRICE_COLOR,
        value: extractValue(priceValue),
        unit: 'index',
      });
    }
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

onBeforeUnmount(() => {
  if (chart && crosshairHandler) {
    chart.unsubscribeCrosshairMove(crosshairHandler);
  }
  chart?.remove();
  resizeObserver?.disconnect();
  breadthSeries = null;
  breadthSymbol = null;
  priceSeries = null;
});
</script>

<template>
  <div class="bg-panel border border-white/10 rounded-xl p-4 flex flex-col gap-4 h-full">
    <div class="flex flex-wrap justify-between items-center gap-4">
      <div>
        <div class="text-xl text-accentCyan font-semibold uppercase">
          Nasdaq 100 Stocks Above X-Day Average
        </div>
        <div class="flex items-center gap-3 text-xs text-textMuted mt-1">
          <span class="flex items-center gap-2">
            <span
              class="w-4 h-1 rounded-full"
              :style="{ backgroundColor: COLOR_MAP[selectedSymbol] }"
            ></span>
            <span>{{ selectedOption.label }} (Left Axis)</span>
          </span>
          <span class="flex items-center gap-2">
            <span class="w-4 h-1 rounded-full" :style="{ backgroundColor: PRICE_COLOR }"></span>
            <span>NDX Index (Right Axis)</span>
          </span>
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-4">
        <label class="text-sm uppercase tracking-wide text-textMuted flex flex-col gap-1">
          Breadth Indicator
          <select
            v-model="selectedSymbol"
            class="bg-black/40 border border-white/20 rounded px-2 py-1 text-white text-sm focus:outline-none"
          >
            <option v-for="option in BREADTH_OPTIONS" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>
        <TimeRangeSelector v-model="rangeKey" :options="['1W', '1M', '3M', 'YTD', '1Y', '5Y']" />
      </div>
    </div>
    <div class="relative flex-1 w-full min-h-[360px]">
      <div ref="container" class="absolute inset-0"></div>
      <div
        v-if="hoverInfo"
        class="absolute bg-black/80 border border-white/20 rounded px-3 py-2 text-xs text-white pointer-events-none z-50 max-w-[220px]"
        :style="tooltipStyle(hoverInfo.position, container)"
      >
        <div>{{ hoverInfo.time }}</div>
        <div v-for="entry in hoverInfo.entries" :key="entry.label" class="flex justify-between gap-3">
          <span :style="{ color: entry.color }">{{ entry.label }}</span>
          <span>
            <template v-if="entry.unit === 'percent'">
              {{ entry.value?.toFixed(2) ?? '--' }}%
            </template>
            <template v-else>
              {{ entry.value?.toFixed(2) ?? '--' }}
            </template>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
