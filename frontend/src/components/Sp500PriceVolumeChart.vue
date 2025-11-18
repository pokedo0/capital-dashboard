<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import {
  type BusinessDay,
  type ChartOptions,
  createChart,
  type DeepPartial,
  type IChartApi,
  type ISeriesApi,
  type MouseEventParams,
  type Time,
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
const priceSeriesData = ref<{ time: string; value: number }[]>([]);
const averageSeriesData = ref<{ time: string; value: number }[]>([]);
const volumeSeriesData = ref<{ time: string; value: number; color: string }[]>([]);
const priceValueMap = ref<Map<string, number>>(new Map());
const averageValueMap = ref<Map<string, number>>(new Map());
const volumeValueMap = ref<Map<string, number>>(new Map());
const extractValue = (point: unknown): number | undefined => {
  if (typeof point === 'object' && point && 'value' in point) {
    const value = (point as { value?: number }).value;
    return typeof value === 'number' ? value : undefined;
  }
  return undefined;
};

const normalizeTimeLabel = (time: Time | string | number | BusinessDay): string => {
  if (typeof time === 'string') {
    return time;
  }
  if (typeof time === 'number') {
    return new Date(time * 1000).toISOString().split('T')[0] || '';
  }
  if (typeof time === 'object' && time !== null) {
    const day = String(time.day).padStart(2, '0');
    const month = String(time.month).padStart(2, '0');
    return `${time.year}-${month}-${day}`;
  }
  return '';
};

const valueWithFallback = (point: unknown, map: Map<string, number>, key: string): number | undefined => {
  const direct = extractValue(point);
  if (typeof direct === 'number') {
    return direct;
  }
  return map.get(key);
};

const tooltipStyle = (
  position: { x: number; y: number },
  container: HTMLElement | null,
  width = 240,
) => {
  const padding = 12;
  const offsetX = 16;
  const offsetY = 12;
  const containerWidth = container?.clientWidth ?? 0;
  const containerHeight = container?.clientHeight ?? 0;
  const baseLeft = position.x + offsetX;
  const maxLeft = containerWidth ? containerWidth - width - padding : baseLeft;
  const left = `${Math.max(Math.min(baseLeft, maxLeft), padding)}px`;
  const baseTop = position.y + offsetY;
  const maxTop = containerHeight ? containerHeight - padding : baseTop;
  const top = `${Math.max(Math.min(baseTop, maxTop), padding)}px`;
  return { left, top };
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
  const sharedSeriesOptions = { priceLineVisible: false, lastValueVisible: true } as const;
  const priceSeries = chart.addLineSeries({
    color: '#f78c1f',
    lineWidth: 2,
    ...sharedSeriesOptions,
  });
  const averageSeries = chart.addLineSeries({
    color: '#ef4444',
    lineWidth: 2,
    ...sharedSeriesOptions,
  });
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
  priceData: { time: string; value: number }[],
  averageData: { time: string; value: number }[],
  volumeData: { time: string; value: number; color: string }[],
  hoverTarget?: typeof hoverInfo,
  type?: 'main' | 'fullscreen',
) => {
  if (!bundle) return;
  bundle.priceSeries.setData(priceData);
  bundle.averageSeries.setData(averageData);
  bundle.volumeSeries.setData(volumeData);
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
    const priceData = payload.points.map((point) => ({ time: point.time, value: point.close ?? 0 }));
    const averageData = buildMovingAverage(payload.points, 30);
    const volumeData = payload.points.map((point) => ({
      time: point.time,
      value: point.volume ?? 0,
      color: '#2563eb',
    }));
    priceSeriesData.value = priceData;
    averageSeriesData.value = averageData;
    volumeSeriesData.value = volumeData;
    priceValueMap.value = new Map(priceData.map((point) => [point.time, point.value]));
    averageValueMap.value = new Map(averageData.map((point) => [point.time, point.value]));
    volumeValueMap.value = new Map(volumeData.map((point) => [point.time, point.value]));
    if (mainContainer.value && !mainBundle.value) {
      mainBundle.value = createBundle(mainContainer.value);
    }
    applyData(mainBundle.value, priceData, averageData, volumeData, hoverInfo, 'main');
    if (showFullscreen.value && fullscreenBundle.value) {
      applyData(fullscreenBundle.value, priceData, averageData, volumeData, fullscreenHoverInfo, 'fullscreen');
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
    if (priceSeriesData.value.length) {
      applyData(
        fullscreenBundle.value,
        priceSeriesData.value,
        averageSeriesData.value,
        volumeSeriesData.value,
        fullscreenHoverInfo,
        'fullscreen',
      );
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

const formatPrice = (value?: number) => {
  if (value === undefined) return '--';
  return value.toFixed(2);
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
    const time = normalizeTimeLabel(param.time as Time | BusinessDay | string | number);
    const priceValue = valueWithFallback(pricePoint, priceValueMap.value, time);
    const averageValue = valueWithFallback(averagePoint, averageValueMap.value, time);
    const volumeValue = valueWithFallback(volumePoint, volumeValueMap.value, time);
    hoverTarget.value = {
      time,
      price: priceValue,
      average: averageValue,
      volume: volumeValue,
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
        class="absolute bg-black/85 border border-white/20 rounded px-4 py-3 text-xs text-white pointer-events-none z-50 max-w-[240px] shadow-lg space-y-2"
        :style="tooltipStyle(hoverInfo.position, mainContainer, 240)"
      >
        <div class="text-sm font-semibold">{{ hoverInfo.time }}</div>
        <div class="flex items-center justify-between gap-3">
          <span class="flex items-center gap-2"><span class="w-2 h-2 rounded-full" style="background-color: #f78c1f"></span> Price</span>
          <span>{{ formatPrice(hoverInfo.price) }}</span>
        </div>
        <div class="flex items-center justify-between gap-3">
          <span class="flex items-center gap-2"><span class="w-2 h-2 rounded-full" style="background-color: #ef4444"></span> 30D Avg</span>
          <span>{{ formatPrice(hoverInfo.average) }}</span>
        </div>
        <div class="flex items-center justify-between gap-3">
          <span class="flex items-center gap-2"><span class="w-2 h-2 rounded-full" style="background-color: #2563eb"></span> Volume</span>
          <span>{{ formatVolume(hoverInfo.volume) }}</span>
        </div>
      </div>
    </div>
    <LegendToggle v-model:activeKeys="activeKeys" :items="legendItems" />
    <FullscreenModal :open="showFullscreen" title="S&P500 Price & Volume" @close="showFullscreen = false">
      <div class="flex flex-col gap-4 w-full h-full">
        <div class="relative flex-1 min-h-[420px]">
          <div ref="fullscreenContainer" class="absolute inset-0"></div>
          <div
            v-if="fullscreenHoverInfo"
            class="absolute bg-black/85 border border-white/20 rounded px-4 py-3 text-xs text-white pointer-events-none z-50 max-w-[260px] shadow-lg space-y-2"
            :style="tooltipStyle(fullscreenHoverInfo.position, fullscreenContainer, 260)"
          >
            <div class="text-sm font-semibold">{{ fullscreenHoverInfo.time }}</div>
            <div class="flex items-center justify-between gap-3">
              <span class="flex items-center gap-2"><span class="w-2 h-2 rounded-full" style="background-color: #f78c1f"></span> Price</span>
              <span>{{ formatPrice(fullscreenHoverInfo.price) }}</span>
            </div>
            <div class="flex items-center justify-between gap-3">
              <span class="flex items-center gap-2"><span class="w-2 h-2 rounded-full" style="background-color: #ef4444"></span> 30D Avg</span>
              <span>{{ formatPrice(fullscreenHoverInfo.average) }}</span>
            </div>
            <div class="flex items-center justify-between gap-3">
              <span class="flex items-center gap-2"><span class="w-2 h-2 rounded-full" style="background-color: #2563eb"></span> Volume</span>
              <span>{{ formatVolume(fullscreenHoverInfo.volume) }}</span>
            </div>
          </div>
        </div>
        <LegendToggle v-model:activeKeys="activeKeys" :items="legendItems" />
      </div>
    </FullscreenModal>
  </div>
</template>
