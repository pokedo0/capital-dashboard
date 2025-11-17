<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import {
  type ChartOptions,
  createChart,
  type DeepPartial,
  type IChartApi,
  type ISeriesApi,
  type MouseEventParams,
} from 'lightweight-charts';
import { useQuery } from '@tanstack/vue-query';
import TimeRangeSelector from './TimeRangeSelector.vue';
import LegendToggle from './LegendToggle.vue';
import FullscreenModal from './FullscreenModal.vue';
import { fetchOhlcv } from '../services/api';
import type { OHLCVPoint } from '../types/api';

type LineSeries = ISeriesApi<'Line'>;
type HistogramSeries = ISeriesApi<'Histogram'>;

interface ChartBundle {
  chart: IChartApi;
  priceSeries: LineSeries;
  averageSeries: LineSeries;
  volumeSeries: HistogramSeries;
  observer: ResizeObserver;
}

const rangeKey = ref('1Y');
const showFullscreen = ref(false);
const activeKeys = ref(['price', 'ma', 'volume']);

const { data, refetch } = useQuery({
  queryKey: computed(() => ['ohlcv', 'SPY', rangeKey.value]),
  queryFn: () => fetchOhlcv('SPY', rangeKey.value),
  refetchOnMount: false,
});

watch(rangeKey, () => refetch());

const mainContainer = ref<HTMLDivElement | null>(null);
const fullscreenContainer = ref<HTMLDivElement | null>(null);
const mainBundle = ref<ChartBundle | null>(null);
const fullscreenBundle = ref<ChartBundle | null>(null);
const hoverInfo = ref<
  | {
      time: string;
      price?: number;
      average?: number;
      volume?: number;
      position: { x: number; y: number };
    }
  | null
>(null);
const fullscreenHoverInfo = ref<
  | {
      time: string;
      price?: number;
      average?: number;
      volume?: number;
      position: { x: number; y: number };
    }
  | null
>(null);
let mainCrosshairHandler: ((param: MouseEventParams) => void) | null = null;
let fullscreenCrosshairHandler: ((param: MouseEventParams) => void) | null = null;
const extractValue = (point: unknown): number | undefined => {
  if (typeof point === 'object' && point && 'value' in point) {
    const value = (point as { value?: number }).value;
    return typeof value === 'number' ? value : undefined;
  }
  return undefined;
};

const chartOptions: DeepPartial<ChartOptions> = {
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
  leftPriceScale: { visible: true, borderVisible: false },
  timeScale: { borderVisible: false },
};

const measureSize = (element: HTMLElement) => {
  const rect = element.getBoundingClientRect();
  const width = rect.width || element.clientWidth || element.offsetWidth || 600;
  const height = rect.height || element.clientHeight || element.offsetHeight || 360;
  return { width, height };
};

const createBundle = (element: HTMLDivElement): ChartBundle => {
  const size = measureSize(element);
  const chart = createChart(element, { ...chartOptions, height: size.height });
  chart.applyOptions({ width: size.width, height: size.height });
  const priceSeries = chart.addLineSeries({ color: '#f78c1f', lineWidth: 2 });
  const averageSeries = chart.addLineSeries({ color: '#ef4444', lineWidth: 2 });
  const volumeSeries = chart.addHistogramSeries({
    priceScaleId: 'left',
    color: '#2563eb',
    priceFormat: {
      type: 'custom',
      formatter: (value: number) => `${(value / 1_000_000).toFixed(2)}M`,
      minMove: 1,
    },
  });
  volumeSeries.priceScale().applyOptions({
    scaleMargins: { top: 0.75, bottom: 0 },
    title: 'Volume (M)',
    entireTextOnly: true,
  });
  const observer = new ResizeObserver(() => {
    const nextSize = measureSize(element);
    chart.applyOptions({ width: nextSize.width, height: nextSize.height });
  });
  observer.observe(element);
  return { chart, priceSeries, averageSeries, volumeSeries, observer };
};

const destroyBundle = (bundle: ChartBundle | null) => {
  if (!bundle) return;
  if (bundle === mainBundle.value) {
    if (mainCrosshairHandler) {
      bundle.chart.unsubscribeCrosshairMove(mainCrosshairHandler);
      mainCrosshairHandler = null;
    }
    hoverInfo.value = null;
  }
  if (bundle === fullscreenBundle.value) {
    if (fullscreenCrosshairHandler) {
      bundle.chart.unsubscribeCrosshairMove(fullscreenCrosshairHandler);
      fullscreenCrosshairHandler = null;
    }
    fullscreenHoverInfo.value = null;
  }
  bundle.observer.disconnect();
  bundle.chart.remove();
};

const applyData = (
  bundle: ChartBundle | null,
  points: OHLCVPoint[],
  hoverTarget?: typeof hoverInfo,
  type?: 'main' | 'fullscreen',
) => {
  if (!bundle) return;
  bundle.priceSeries.setData(points.map((p) => ({ time: p.time, value: p.close ?? 0 })));
  bundle.averageSeries.setData(buildMovingAverage(points, 30));
  bundle.volumeSeries.setData(
    points.map((p) => ({
      time: p.time,
      value: (p.volume ?? 0),
      color: '#2563eb',
    })),
  );
  bundle.chart.timeScale().fitContent();
  syncVisibility(bundle);
  if (hoverTarget && type) {
    attachCrosshair(bundle, hoverTarget, type);
  }
};

const syncVisibility = (bundle: ChartBundle | null) => {
  if (!bundle) return;
  const visible = new Set(activeKeys.value);
  bundle.priceSeries.applyOptions({ visible: visible.has('price') });
  bundle.averageSeries.applyOptions({ visible: visible.has('ma') });
  bundle.volumeSeries.applyOptions({ visible: visible.has('volume') });
};

watch(
  () => data.value,
  (payload) => {
    if (!payload) return;
    if (mainContainer.value && !mainBundle.value) {
      mainBundle.value = createBundle(mainContainer.value);
    }
    applyData(mainBundle.value, payload.points, hoverInfo, 'main');
    if (showFullscreen.value && fullscreenBundle.value) {
      applyData(fullscreenBundle.value, payload.points, fullscreenHoverInfo, 'fullscreen');
    }
  },
  { immediate: true },
);

watch(activeKeys, () => {
  syncVisibility(mainBundle.value);
  syncVisibility(fullscreenBundle.value);
});

const openFullscreen = async () => {
  showFullscreen.value = true;
  await nextTick();
  if (fullscreenContainer.value) {
    fullscreenBundle.value = createBundle(fullscreenContainer.value);
    if (data.value) {
      applyData(fullscreenBundle.value, data.value.points, fullscreenHoverInfo, 'fullscreen');
    }
  }
};

watch(showFullscreen, (open) => {
  if (!open) {
    destroyBundle(fullscreenBundle.value);
    fullscreenBundle.value = null;
  }
});

onBeforeUnmount(() => {
  destroyBundle(mainBundle.value);
  destroyBundle(fullscreenBundle.value);
});

const legendItems = [
  { key: 'price', label: 'Price', color: '#f78c1f' },
  { key: 'ma', label: '30D Avg', color: '#ef4444' },
  { key: 'volume', label: 'Volume', color: '#2563eb' },
];

const formatVolume = (value?: number) => {
  if (value === undefined) return '--';
  return `${(value / 1_000_000).toFixed(2)}M`;
};

const buildMovingAverage = (points: OHLCVPoint[], period: number) => {
  const values: { time: string; value: number }[] = [];
  const queue: number[] = [];
  points.forEach((point) => {
    if (typeof point.close !== 'number') return;
    queue.push(point.close);
    if (queue.length > period) queue.shift();
    if (queue.length === period) {
      const avg = queue.reduce((acc, val) => acc + val, 0) / period;
      values.push({ time: point.time, value: avg });
    }
  });
  return values;
};

const attachCrosshair = (
  bundle: ChartBundle | null,
  hoverTarget: typeof hoverInfo,
  type: 'main' | 'fullscreen',
) => {
  if (!bundle) return;
  const handler = (param: MouseEventParams) => {
    if (!param.time || !param.point) {
      hoverTarget.value = null;
      return;
    }
    const pricePoint = param.seriesData.get(bundle.priceSeries);
    const averagePoint = param.seriesData.get(bundle.averageSeries);
    const volumePoint = param.seriesData.get(bundle.volumeSeries);
    const time =
      typeof param.time === 'string'
        ? param.time
        : new Date((param.time as number) * 1000).toISOString().split('T')[0] || '';
    hoverTarget.value = {
      time,
      price: extractValue(pricePoint),
      average: extractValue(averagePoint),
      volume: extractValue(volumePoint),
      position: { x: param.point.x, y: param.point.y },
    };
  };
  if (type === 'main') {
    if (mainCrosshairHandler) {
      bundle.chart.unsubscribeCrosshairMove(mainCrosshairHandler);
    }
    mainCrosshairHandler = handler;
  } else {
    if (fullscreenCrosshairHandler) {
      bundle.chart.unsubscribeCrosshairMove(fullscreenCrosshairHandler);
    }
    fullscreenCrosshairHandler = handler;
  }
  bundle.chart.subscribeCrosshairMove(handler);
};
</script>

<template>
  <div class="bg-panel border border-white/10 rounded-xl p-4 flex flex-col gap-4">
    <div class="flex flex-wrap justify-between items-center gap-4">
      <div>
        <div class="text-xl text-accentCyan font-semibold uppercase">SPY Price & Volume</div>
        <p class="text-sm text-textMuted">Index price with 30-day average and volume overlay</p>
      </div>
      <div class="flex items-center gap-3">
        <TimeRangeSelector v-model="rangeKey" />
        <button class="px-3 py-1 border border-white/20 rounded text-textMuted hover:text-white" @click="openFullscreen">
          Fullscreen
        </button>
      </div>
    </div>
    <div class="relative flex-1 w-full min-h-[360px]">
      <div ref="mainContainer" class="absolute inset-0"></div>
      <div
        v-if="hoverInfo"
        class="absolute bg-black/80 border border-white/20 rounded px-3 py-2 text-xs text-white pointer-events-none z-50"
        :style="{ left: `calc(${hoverInfo.position.x}px + 12px)`, top: `calc(${hoverInfo.position.y}px - 50px)` }"
      >
        <div>{{ hoverInfo.time }}</div>
        <div>Price: {{ hoverInfo.price?.toFixed(2) ?? '--' }}</div>
        <div>30D Avg: {{ hoverInfo.average?.toFixed(2) ?? '--' }}</div>
        <div>Volume: {{ formatVolume(hoverInfo.volume) }}</div>
      </div>
    </div>
    <LegendToggle v-model:activeKeys="activeKeys" :items="legendItems" />
    <FullscreenModal :open="showFullscreen" title="S&P500 Price & Volume" @close="showFullscreen = false">
      <div class="flex flex-col gap-4 w-full h-full">
        <div class="relative flex-1 min-h-[420px]">
          <div ref="fullscreenContainer" class="absolute inset-0"></div>
          <div
            v-if="fullscreenHoverInfo"
            class="absolute bg-black/80 border border-white/20 rounded px-3 py-2 text-xs text-white pointer-events-none z-50"
            :style="{
              left: `calc(${fullscreenHoverInfo.position.x}px + 12px)`,
              top: `calc(${fullscreenHoverInfo.position.y}px - 50px)`,
            }"
          >
            <div>{{ fullscreenHoverInfo.time }}</div>
            <div>Price: {{ fullscreenHoverInfo.price?.toFixed(2) ?? '--' }}</div>
            <div>30D Avg: {{ fullscreenHoverInfo.average?.toFixed(2) ?? '--' }}</div>
            <div>Volume: {{ formatVolume(fullscreenHoverInfo.volume) }}</div>
          </div>
        </div>
        <LegendToggle v-model:activeKeys="activeKeys" :items="legendItems" />
      </div>
    </FullscreenModal>
  </div>
</template>
