<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import {
  createChart,
  LineStyle,
  PriceScaleMode,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type MouseEventParams,
} from 'lightweight-charts';
import { useQuery } from '@tanstack/vue-query';
import TimeRangeSelector from './TimeRangeSelector.vue';
import FullscreenModal from './FullscreenModal.vue';
import { fetchFearGreedComparison } from '../services/api';

type LineSeries = ISeriesApi<'Line'>;

const rangeOptions = ['1W', '1M', '3M', '6M', 'YTD', '1Y', '5Y'];
const rangeKey = ref('6M');
const showFullscreen = ref(false);

const { data, refetch } = useQuery({
  queryKey: computed(() => ['fear-greed', rangeKey.value]),
  queryFn: () => fetchFearGreedComparison(rangeKey.value),
});

watch(rangeKey, () => refetch());

const FEAR_ZONES = [
  { value: 25, label: 'Extreme Fear', color: '#ef4444' },
  { value: 45, label: 'Fear', color: '#f97316' },
  { value: 55, label: 'Neutral', color: '#eab308' },
  { value: 75, label: 'Greed', color: '#22c55e' },
];

const mainContainer = ref<HTMLDivElement | null>(null);
const fullscreenContainer = ref<HTMLDivElement | null>(null);
const mainOverlay = ref<HTMLDivElement | null>(null);
const fullscreenOverlay = ref<HTMLDivElement | null>(null);
const mainGreedZone = ref<HTMLDivElement | null>(null);
const mainExtremeZone = ref<HTMLDivElement | null>(null);
const fullscreenGreedZone = ref<HTMLDivElement | null>(null);
const fullscreenExtremeZone = ref<HTMLDivElement | null>(null);
let mainChart: IChartApi | null = null;
let fullscreenChart: IChartApi | null = null;
let mainObserver: ResizeObserver | null = null;
let fullscreenObserver: ResizeObserver | null = null;
let mainFearSeries: LineSeries | null = null;
let mainSpySeries: LineSeries | null = null;
let fullscreenFearSeries: LineSeries | null = null;
let fullscreenSpySeries: LineSeries | null = null;
let mainLines: IPriceLine[] = [];
let fullscreenLines: IPriceLine[] = [];
let mainCrosshairHandler: ((param: MouseEventParams) => void) | null = null;
let fullscreenCrosshairHandler: ((param: MouseEventParams) => void) | null = null;

type HoverInfo = {
  time: string;
  fear?: number;
  spy?: number;
  position: { x: number; y: number };
};

const mainHover = ref<HoverInfo | null>(null);
const fullscreenHover = ref<HoverInfo | null>(null);

const measureHeight = (element: HTMLElement) => {
  const rect = element.getBoundingClientRect();
  return rect.height || element.offsetHeight || 360;
};

const initChart = (element: HTMLDivElement) => {
  const chart = createChart(element, {
    height: measureHeight(element),
    layout: {
      background: { color: '#050505' },
      textColor: '#f8fafc',
      fontFamily: "'IBM Plex Sans', Inter, ui-sans-serif",
    },
    leftPriceScale: { visible: true, mode: PriceScaleMode.Normal, autoScale: true },
    rightPriceScale: { visible: true, mode: PriceScaleMode.Normal, autoScale: true },
    crosshair: { mode: 1 },
    grid: {
      horzLines: { color: 'rgba(255,255,255,0.08)' },
      vertLines: { color: 'rgba(255,255,255,0.05)' },
    },
    timeScale: { borderVisible: false, timeVisible: true },
  });
  chart.applyOptions({ width: element.clientWidth, height: measureHeight(element) });
  return chart;
};

const ensureSeries = (chart: IChartApi | null, type: 'fear' | 'spy'): LineSeries | null => {
  if (!chart) return null;
  const options =
    type === 'fear'
      ? { color: '#22c55e', lineWidth: 2, priceScaleId: 'left' }
      : { color: '#60a5fa', lineWidth: 2, priceScaleId: 'right' as const };
  return chart.addLineSeries(options);
};

const updateFearZones = (scope: 'main' | 'fullscreen') => {
  const isMain = scope === 'main';
  const series = isMain ? mainFearSeries : fullscreenFearSeries;
  const overlay =
    (isMain ? mainOverlay.value : fullscreenOverlay.value) ??
    (isMain ? mainContainer.value : fullscreenContainer.value);
  const greedEl = isMain ? mainGreedZone.value : fullscreenGreedZone.value;
  const fearEl = isMain ? mainExtremeZone.value : fullscreenExtremeZone.value;
  if (!series || !overlay) return;
  const overlayHeight = overlay.clientHeight;
  if (!overlayHeight) return;
  const clamp = (value: number) => Math.min(Math.max(value, 0), overlayHeight);
  const greedCoord = series.priceToCoordinate(75);
  if (greedEl) {
    if (typeof greedCoord !== 'number') {
      greedEl.style.opacity = '0';
    } else {
      const height = clamp(greedCoord);
      greedEl.style.opacity = '1';
      greedEl.style.top = '0px';
      greedEl.style.height = `${height}px`;
    }
  }
  const fearCoord = series.priceToCoordinate(25);
  if (fearEl) {
    if (typeof fearCoord !== 'number') {
      fearEl.style.opacity = '0';
    } else {
      const top = clamp(fearCoord);
      fearEl.style.opacity = '1';
      fearEl.style.top = `${top}px`;
      fearEl.style.height = `${Math.max(overlayHeight - top, 0)}px`;
    }
  }
};

const scheduleZoneUpdate = (scope: 'main' | 'fullscreen') => {
  requestAnimationFrame(() => updateFearZones(scope));
};

const attachResize = (
  chart: IChartApi | null,
  container: HTMLDivElement | null,
  existing: ResizeObserver | null,
  scope: 'main' | 'fullscreen',
) => {
  existing?.disconnect();
  if (!chart || !container) return null;
  const observer = new ResizeObserver(() => {
    chart.applyOptions({ width: container.clientWidth, height: measureHeight(container) });
    scheduleZoneUpdate(scope);
  });
  observer.observe(container);
  scheduleZoneUpdate(scope);
  return observer;
};

const clearPriceLines = (series: LineSeries | null, store: IPriceLine[]) => {
  if (!series) return;
  store.forEach((line) => series.removePriceLine(line));
  store.length = 0;
};

const applyZoneLines = (series: LineSeries | null, store: IPriceLine[]) => {
  if (!series) return;
  clearPriceLines(series, store);
  FEAR_ZONES.forEach((zone) => {
    const line = series.createPriceLine({
      price: zone.value,
      color: zone.color,
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: zone.label,
    });
    store.push(line);
  });
};

const extractValue = (point: unknown): number | undefined => {
  if (typeof point === 'object' && point && 'value' in point) {
    const value = (point as { value?: number }).value;
    return typeof value === 'number' ? value : undefined;
  }
  return undefined;
};

const attachCrosshair = (
  chart: IChartApi | null,
  fearSeries: LineSeries | null,
  spySeries: LineSeries | null,
  hoverRef: typeof mainHover,
  store: 'main' | 'fullscreen',
) => {
  if (!chart || !fearSeries || !spySeries) return;
  const handler = (param: MouseEventParams) => {
    if (!param.time || !param.point) {
      hoverRef.value = null;
      return;
    }
    const fearPoint = param.seriesData.get(fearSeries);
    const spyPoint = param.seriesData.get(spySeries);
    const time =
      typeof param.time === 'string'
        ? param.time
        : new Date((param.time as number) * 1000).toISOString().split('T')[0];
    hoverRef.value = {
      time,
      fear: extractValue(fearPoint),
      spy: extractValue(spyPoint),
      position: { x: param.point.x, y: param.point.y },
    };
  };
  const existing = store === 'main' ? mainCrosshairHandler : fullscreenCrosshairHandler;
  if (existing && chart) {
    chart.unsubscribeCrosshairMove(existing);
  }
  chart.subscribeCrosshairMove(handler);
  if (store === 'main') {
    mainCrosshairHandler = handler;
  } else {
    fullscreenCrosshairHandler = handler;
  }
};

const applyData = (
  chart: IChartApi | null,
  fearSeries: LineSeries | null,
  spySeries: LineSeries | null,
  payload: Awaited<ReturnType<typeof fetchFearGreedComparison>>,
  hoverRef: typeof mainHover,
  lines: IPriceLine[],
  store: 'main' | 'fullscreen',
) => {
  if (!chart || !fearSeries || !spySeries || !payload) return;
  const normalize = (points: { time: string; value: number }[]) => {
    const map = new Map<string, number>();
    points.forEach((point) => {
      if (!point.time || typeof point.value !== 'number') return;
      map.set(point.time, point.value);
    });
    return Array.from(map.entries())
      .sort((a, b) => new Date(a[0]).getTime() - new Date(b[0]).getTime())
      .map(([time, value]) => ({ time, value }));
  };
  fearSeries.setData(normalize(payload.index));
  spySeries.setData(normalize(payload.spy));
  chart.timeScale().fitContent();
  chart.priceScale('left').applyOptions({ autoScale: true, mode: PriceScaleMode.Normal });
  chart.priceScale('right').applyOptions({ autoScale: true, mode: PriceScaleMode.Normal });
  applyZoneLines(fearSeries, lines);
  attachCrosshair(chart, fearSeries, spySeries, hoverRef, store);
  scheduleZoneUpdate(store);
};

watch(
  () => data.value,
  async (payload) => {
    if (!payload) return;
    if (mainContainer.value && !mainChart) {
      await nextTick();
      if (mainContainer.value) {
        mainChart = initChart(mainContainer.value);
        mainFearSeries = ensureSeries(mainChart, 'fear');
        mainSpySeries = ensureSeries(mainChart, 'spy');
        mainObserver = attachResize(mainChart, mainContainer.value, mainObserver, 'main');
      }
    }
    applyData(mainChart, mainFearSeries, mainSpySeries, payload, mainHover, mainLines, 'main');
    if (showFullscreen.value && fullscreenContainer.value) {
      if (!fullscreenChart) {
        fullscreenChart = initChart(fullscreenContainer.value);
        fullscreenFearSeries = ensureSeries(fullscreenChart, 'fear');
        fullscreenSpySeries = ensureSeries(fullscreenChart, 'spy');
        fullscreenObserver = attachResize(
          fullscreenChart,
          fullscreenContainer.value,
          fullscreenObserver,
          'fullscreen',
        );
      }
      applyData(
        fullscreenChart,
        fullscreenFearSeries,
        fullscreenSpySeries,
        payload,
        fullscreenHover,
        fullscreenLines,
        'fullscreen',
      );
    }
  },
  { immediate: true },
);

const openFullscreen = async () => {
  showFullscreen.value = true;
  await nextTick();
  if (fullscreenContainer.value && data.value) {
    fullscreenChart = initChart(fullscreenContainer.value);
    fullscreenFearSeries = ensureSeries(fullscreenChart, 'fear');
    fullscreenSpySeries = ensureSeries(fullscreenChart, 'spy');
    fullscreenObserver = attachResize(
      fullscreenChart,
      fullscreenContainer.value,
      fullscreenObserver,
      'fullscreen',
    );
    applyData(
      fullscreenChart,
      fullscreenFearSeries,
      fullscreenSpySeries,
      data.value,
      fullscreenHover,
      fullscreenLines,
      'fullscreen',
    );
  }
};

watch(showFullscreen, (visible) => {
  if (!visible && fullscreenChart) {
    if (fullscreenCrosshairHandler) {
      fullscreenChart.unsubscribeCrosshairMove(fullscreenCrosshairHandler);
      fullscreenCrosshairHandler = null;
    }
    fullscreenChart.remove();
    fullscreenChart = null;
    fullscreenObserver?.disconnect();
    fullscreenObserver = null;
    fullscreenHover.value = null;
    fullscreenLines = [];
    fullscreenFearSeries = null;
    fullscreenSpySeries = null;
  }
});

watch(mainOverlay, (el) => {
  if (el) scheduleZoneUpdate('main');
});

watch(fullscreenOverlay, (el) => {
  if (el) scheduleZoneUpdate('fullscreen');
});

onBeforeUnmount(() => {
  if (mainChart && mainCrosshairHandler) {
    mainChart.unsubscribeCrosshairMove(mainCrosshairHandler);
  }
  mainChart?.remove();
  mainObserver?.disconnect();
  fullscreenChart?.remove();
  fullscreenObserver?.disconnect();
});

const zoneBadges = [
  { text: 'Extreme Fear', color: 'bg-red-500/30 text-red-200' },
  { text: 'Fear', color: 'bg-orange-500/30 text-orange-200' },
  { text: 'Neutral', color: 'bg-yellow-500/30 text-yellow-200' },
  { text: 'Greed', color: 'bg-emerald-500/30 text-emerald-200' },
];
</script>

<template>
  <div class="bg-panel border border-white/10 rounded-xl p-4 flex flex-col gap-4">
    <div class="flex flex-wrap justify-between items-center gap-4">
      <div>
        <div class="text-xl text-accentCyan font-semibold uppercase">Fear & Greed vs SPY</div>
        <p class="text-sm text-textMuted">Dual-axis comparison with sentiment zones</p>
      </div>
      <div class="flex items-center gap-3">
        <TimeRangeSelector v-model="rangeKey" :options="rangeOptions" />
        <button class="px-3 py-1 border border-white/20 rounded text-textMuted hover:text-white" @click="openFullscreen">
          Fullscreen
        </button>
      </div>
    </div>
    <div class="flex flex-wrap gap-2 text-xs uppercase tracking-wide">
      <span
        v-for="badge in zoneBadges"
        :key="badge.text"
        :class="['px-2 py-0.5 rounded-full', badge.color]"
      >
        {{ badge.text }}
      </span>
    </div>
    <div class="relative flex-1 w-full min-h-[360px]">
      <div ref="mainContainer" class="absolute inset-0"></div>
      <div ref="mainOverlay" class="pointer-events-none absolute inset-0 z-10">
        <div
          ref="mainGreedZone"
          class="absolute inset-x-0 bg-emerald-400/10 transition-[height] duration-300 ease-out"
          style="opacity: 0"
        ></div>
        <div
          ref="mainExtremeZone"
          class="absolute inset-x-0 bg-red-400/10 transition-[height] duration-300 ease-out"
          style="opacity: 0"
        ></div>
      </div>
      <div
        v-if="mainHover"
        class="absolute bg-black/80 border border-white/20 rounded px-3 py-2 text-xs text-white pointer-events-none z-50"
        :style="{ left: `calc(${mainHover.position.x}px + 12px)`, top: `calc(${mainHover.position.y}px - 40px)` }"
      >
        <div>{{ mainHover.time }}</div>
        <div class="flex justify-between gap-2">
          <span class="text-green-300">Fear & Greed</span>
          <span>{{ mainHover.fear?.toFixed(1) ?? '--' }}</span>
        </div>
        <div class="flex justify-between gap-2">
          <span class="text-blue-300">SPY</span>
          <span>{{ mainHover.spy?.toFixed(2) ?? '--' }}</span>
        </div>
      </div>
    </div>
    <div class="text-xs uppercase tracking-wide flex gap-6 text-textMuted">
      <span class="flex items-center gap-2">
        <span class="w-4 h-1 bg-emerald-400 rounded-full"></span> Fear & Greed Index
      </span>
      <span class="flex items-center gap-2">
        <span class="w-4 h-1 bg-blue-400 rounded-full"></span> SPY Close
      </span>
    </div>
    <FullscreenModal
      :open="showFullscreen"
      title="Fear & Greed vs SPY"
      @close="showFullscreen = false"
    >
      <div class="relative flex-1 min-h-[440px]">
        <div ref="fullscreenContainer" class="absolute inset-0"></div>
        <div ref="fullscreenOverlay" class="pointer-events-none absolute inset-0 z-10">
          <div
            ref="fullscreenGreedZone"
            class="absolute inset-x-0 bg-emerald-400/10 transition-[height] duration-300 ease-out"
            style="opacity: 0"
          ></div>
          <div
            ref="fullscreenExtremeZone"
            class="absolute inset-x-0 bg-red-400/10 transition-[height] duration-300 ease-out"
            style="opacity: 0"
          ></div>
        </div>
        <div
          v-if="fullscreenHover"
          class="absolute bg-black/80 border border-white/20 rounded px-3 py-2 text-xs text-white pointer-events-none z-50"
          :style="{
            left: `calc(${fullscreenHover.position.x}px + 12px)`,
            top: `calc(${fullscreenHover.position.y}px - 40px)`,
          }"
        >
          <div>{{ fullscreenHover.time }}</div>
          <div class="flex justify-between gap-2">
            <span class="text-green-300">Fear & Greed</span>
            <span>{{ fullscreenHover.fear?.toFixed(1) ?? '--' }}</span>
          </div>
          <div class="flex justify-between gap-2">
            <span class="text-blue-300">SPY</span>
            <span>{{ fullscreenHover.spy?.toFixed(2) ?? '--' }}</span>
          </div>
        </div>
      </div>
    </FullscreenModal>
  </div>
</template>
