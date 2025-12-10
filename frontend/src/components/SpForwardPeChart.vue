<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import {
  LineSeries as LineSeriesDefinition,
  createChart,
  PriceScaleMode,
  type IChartApi,
  type ISeriesApi,
  type MouseEventParams,
} from 'lightweight-charts';
import { useQuery } from '@tanstack/vue-query';
import TimeRangeSelector from './TimeRangeSelector.vue';
import FullscreenModal from './FullscreenModal.vue';
import { fetchForwardPeComparison } from '../services/api';

type LineSeries = ISeriesApi<'Line'>;

const rangeOptions = ['6M', 'YTD', '1Y', '5Y'];
const rangeKey = ref('1Y');
const showFullscreen = ref(false);

const { data, refetch } = useQuery({
  queryKey: computed(() => ['forward-pe', rangeKey.value]),
  queryFn: () => fetchForwardPeComparison(rangeKey.value),
});

watch(rangeKey, () => refetch());

const containerRef = ref<HTMLDivElement | null>(null);
const fullscreenContainerRef = ref<HTMLDivElement | null>(null);
let chart: IChartApi | null = null;
let peSeries: LineSeries | null = null;
let spxSeries: LineSeries | null = null;
let observer: ResizeObserver | null = null;
let crosshairHandler: ((param: MouseEventParams) => void) | null = null;
let fullscreenChart: IChartApi | null = null;
let fullscreenPeSeries: LineSeries | null = null;
let fullscreenSpxSeries: LineSeries | null = null;
let fullscreenObserver: ResizeObserver | null = null;
let fullscreenCrosshairHandler: ((param: MouseEventParams) => void) | null = null;

type HoverInfo = {
  time: string;
  pe?: number;
  spx?: number;
  position: { x: number; y: number };
} | null;

const hoverInfo = ref<HoverInfo>(null);
const fullscreenHover = ref<HoverInfo>(null);

const measureSize = (element: HTMLElement) => {
  const rect = element.getBoundingClientRect();
  return {
    width: rect.width || element.clientWidth || element.offsetWidth || 720,
    height: rect.height || element.clientHeight || element.offsetHeight || 420,
  };
};

const downsampleWeekly = (points: { time: string; value: number }[]) => {
  if (!points.length) return points;
  const result: typeof points = [];
  let lastSample: number | null = null;
  const weekMs = 7 * 24 * 60 * 60 * 1000;
  points.forEach((point) => {
    const current = new Date(point.time).getTime();
    if (Number.isNaN(current)) {
      result.push(point);
      return;
    }
    if (lastSample === null || current - lastSample >= weekMs) {
      result.push(point);
      lastSample = current;
    } else {
      result[result.length - 1] = point;
    }
  });
  return result;
};

const extractValue = (point: unknown): number | undefined => {
  if (typeof point === 'object' && point && 'value' in point) {
    const value = (point as { value?: number }).value;
    return typeof value === 'number' ? value : undefined;
  }
  return undefined;
};

const formatTime = (value: string | number) => {
  if (typeof value === 'string') return value;
  const date = new Date((value as number) * 1000);
  return date.toISOString().split('T')[0] ?? '';
};

const tooltipStyle = (
  position: { x: number; y: number },
  container: HTMLElement | null,
  width = 260,
  height = 140,
) => {
  const padding = 12;
  const rightAxisGuard = 72;
  const offsetX = 70;
  const offsetY = 15;
  const containerWidth = container?.clientWidth ?? 0;
  const containerHeight = container?.clientHeight ?? 0;
  const baseLeft = position.x + offsetX;
  const maxLeft = containerWidth ? containerWidth - width - padding - rightAxisGuard : baseLeft;
  const left = `${Math.max(Math.min(baseLeft, maxLeft), padding)}px`;
  const baseTop = position.y + offsetY;
  const maxTop = containerHeight ? containerHeight - height - padding : baseTop;
  const top = `${Math.max(Math.min(baseTop, maxTop), padding)}px`;
  return { left, top };
};

const disposeChart = () => {
  observer?.disconnect();
  observer = null;
  if (chart && crosshairHandler) {
    chart.unsubscribeCrosshairMove(crosshairHandler);
  }
  chart?.remove();
  chart = null;
  peSeries = null;
  spxSeries = null;
  crosshairHandler = null;
  hoverInfo.value = null;
};

const disposeFullscreen = () => {
  fullscreenObserver?.disconnect();
  fullscreenObserver = null;
  if (fullscreenChart && fullscreenCrosshairHandler) {
    fullscreenChart.unsubscribeCrosshairMove(fullscreenCrosshairHandler);
  }
  fullscreenChart?.remove();
  fullscreenChart = null;
  fullscreenPeSeries = null;
  fullscreenSpxSeries = null;
  fullscreenCrosshairHandler = null;
  fullscreenHover.value = null;
};

const initChart = () => {
  if (!containerRef.value) return;
  disposeChart();
  const size = measureSize(containerRef.value);
  chart = createChart(containerRef.value, {
    height: size.height,
    layout: {
      background: { color: '#050505' },
      textColor: '#f8fafc',
      fontFamily: "'IBM Plex Sans', Inter, ui-sans-serif",
    },
    leftPriceScale: {
      borderVisible: true,
      visible: true,
      autoScale: true,
      mode: PriceScaleMode.Normal,
      entireTextOnly: true,
    },
    rightPriceScale: { borderVisible: true, autoScale: true, mode: PriceScaleMode.Normal },
    timeScale: { borderVisible: false, timeVisible: true },
    grid: {
      horzLines: { color: 'rgba(255,255,255,0.05)' },
      vertLines: { color: 'rgba(255,255,255,0.05)' },
    },
    crosshair: { mode: 1 },
  });
  chart.applyOptions({ width: size.width, height: size.height });

  peSeries = chart.addSeries(LineSeriesDefinition, {
    color: '#22c55e',
    lineWidth: 2,
    priceLineVisible: false,
    priceScaleId: 'left',
    lastValueVisible: true,
  });
  peSeries.applyOptions({
    priceFormat: { type: 'custom', formatter: (value: number) => value.toFixed(2) },
  });
  spxSeries = chart.addSeries(LineSeriesDefinition, {
    color: '#60a5fa',
    lineWidth: 2,
    priceLineVisible: false,
    priceScaleId: 'right',
    lastValueVisible: true,
  });

  observer = new ResizeObserver(() => {
    if (containerRef.value && chart) {
      const nextSize = measureSize(containerRef.value);
      chart.applyOptions({ width: nextSize.width, height: nextSize.height });
    }
  });
  observer.observe(containerRef.value);

  crosshairHandler = (param: MouseEventParams) => {
    if (!param.time || !param.point || !peSeries || !spxSeries) {
      hoverInfo.value = null;
      return;
    }
    const pePoint = param.seriesData.get(peSeries);
    const spxPoint = param.seriesData.get(spxSeries);
    hoverInfo.value = {
      time: formatTime(param.time),
      pe: extractValue(pePoint),
      spx: extractValue(spxPoint),
      position: { x: param.point.x, y: param.point.y },
    };
  };
  chart.subscribeCrosshairMove(crosshairHandler);
};

const initFullscreenChart = () => {
  if (!fullscreenContainerRef.value) return;
  disposeFullscreen();
  const size = measureSize(fullscreenContainerRef.value);
  fullscreenChart = createChart(fullscreenContainerRef.value, {
    height: size.height,
    layout: {
      background: { color: '#050505' },
      textColor: '#f8fafc',
      fontFamily: "'IBM Plex Sans', Inter, ui-sans-serif",
    },
    leftPriceScale: {
      borderVisible: true,
      visible: true,
      autoScale: true,
      mode: PriceScaleMode.Normal,
      entireTextOnly: true,
    },
    rightPriceScale: { borderVisible: true, autoScale: true, mode: PriceScaleMode.Normal },
    timeScale: { borderVisible: false, timeVisible: true },
    grid: {
      horzLines: { color: 'rgba(255,255,255,0.05)' },
      vertLines: { color: 'rgba(255,255,255,0.05)' },
    },
    crosshair: { mode: 1 },
  });
  fullscreenChart.applyOptions({ width: size.width, height: size.height });

  fullscreenPeSeries = fullscreenChart.addSeries(LineSeriesDefinition, {
    color: '#22c55e',
    lineWidth: 2,
    priceLineVisible: false,
    priceScaleId: 'left',
    lastValueVisible: true,
  });
  fullscreenPeSeries.applyOptions({
    priceFormat: { type: 'custom', formatter: (value: number) => value.toFixed(2) },
  });
  fullscreenSpxSeries = fullscreenChart.addSeries(LineSeriesDefinition, {
    color: '#60a5fa',
    lineWidth: 2,
    priceLineVisible: false,
    priceScaleId: 'right',
    lastValueVisible: true,
  });

  fullscreenObserver = new ResizeObserver(() => {
    if (fullscreenContainerRef.value && fullscreenChart) {
      const nextSize = measureSize(fullscreenContainerRef.value);
      fullscreenChart.applyOptions({ width: nextSize.width, height: nextSize.height });
    }
  });
  fullscreenObserver.observe(fullscreenContainerRef.value);

  fullscreenCrosshairHandler = (param: MouseEventParams) => {
    if (!param.time || !param.point || !fullscreenPeSeries || !fullscreenSpxSeries) {
      fullscreenHover.value = null;
      return;
    }
    const pePoint = param.seriesData.get(fullscreenPeSeries);
    const spxPoint = param.seriesData.get(fullscreenSpxSeries);
    fullscreenHover.value = {
      time: formatTime(param.time),
      pe: extractValue(pePoint),
      spx: extractValue(spxPoint),
      position: { x: param.point.x, y: param.point.y },
    };
  };
  fullscreenChart.subscribeCrosshairMove(fullscreenCrosshairHandler);
};

watch(
  () => data.value,
  (payload) => {
    if (!payload) return;
    if (!chart) {
      initChart();
    }
    if (!chart || !peSeries || !spxSeries) return;
    // 数据已在后端按交易日对齐，这里不再降采样，避免 hover 缺口
    peSeries.setData(payload.forward_pe.map((point) => ({ time: point.time, value: point.value })));
    spxSeries.setData(payload.spx.map((point) => ({ time: point.time, value: point.value })));
    chart.timeScale().fitContent();
    chart.priceScale('left').applyOptions({ autoScale: true, visible: true, borderVisible: true });
    chart.priceScale('right').applyOptions({ autoScale: true });

    if (fullscreenChart && fullscreenPeSeries && fullscreenSpxSeries) {
      fullscreenPeSeries.setData(
        payload.forward_pe.map((point) => ({ time: point.time, value: point.value })),
      );
      fullscreenSpxSeries.setData(
        payload.spx.map((point) => ({ time: point.time, value: point.value })),
      );
      fullscreenChart.timeScale().fitContent();
      fullscreenChart.priceScale('left').applyOptions({
        autoScale: true,
        visible: true,
        borderVisible: true,
      });
      fullscreenChart.priceScale('right').applyOptions({ autoScale: true });
    }
  },
  { immediate: true },
);

watch(
  () => showFullscreen.value,
  async (open) => {
    if (open) {
      await nextTick();
      initFullscreenChart();
      if (data.value && fullscreenPeSeries && fullscreenSpxSeries && fullscreenChart) {
        fullscreenPeSeries.setData(
          data.value.forward_pe.map((point) => ({ time: point.time, value: point.value })),
        );
        fullscreenSpxSeries.setData(
          data.value.spx.map((point) => ({ time: point.time, value: point.value })),
        );
        fullscreenChart.timeScale().fitContent();
      }
    } else {
      disposeFullscreen();
    }
  },
);

onMounted(() => {
  if (containerRef.value) {
    initChart();
  }
});

onBeforeUnmount(() => {
  disposeChart();
  disposeFullscreen();
});
</script>

<template>
  <div class="bg-panel border border-white/10 rounded-xl p-4 flex flex-col gap-4">
    <div class="flex flex-wrap justify-between items-center gap-4">
      <div>
        <div class="text-xl text-accentCyan font-semibold uppercase">S&P 500 - Forward PE Ratio</div>
        <p class="text-sm text-textMuted">Daily forward P/E from MacroMicro, indexed against ^GSPC closes.</p>
      </div>
      <div class="flex items-center gap-3">
        <TimeRangeSelector v-model="rangeKey" :options="rangeOptions" />
        <button
          class="h-10 w-10 rounded-full text-textMuted hover:text-white flex items-center justify-center hover:bg-white/10 transition-colors"
          @click="showFullscreen = true"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 9V5h4M20 9V5h-4M4 15v4h4m12-4v4h-4" />
          </svg>
        </button>
      </div>
    </div>

    <div class="relative flex-1 w-full min-h-[360px]">
      <div ref="containerRef" class="absolute inset-0" />
      <div
        v-if="hoverInfo"
        class="absolute bg-black/85 border border-white/20 rounded px-4 py-3 text-xs text-white pointer-events-none z-50 max-w-[240px] shadow-lg space-y-2"
        :style="tooltipStyle(hoverInfo.position, containerRef ?? null, 240)"
      >
        <div class="text-sm font-semibold">{{ hoverInfo.time }}</div>
        <div class="flex items-center justify-between gap-3">
          <span class="flex items-center gap-2">
            <span class="h-2.5 w-2.5 rounded-full bg-emerald-400"></span>
            Forward P/E
          </span>
          <span class="font-mono">
            {{ typeof hoverInfo.pe === 'number' ? hoverInfo.pe.toFixed(2) : '—' }}
          </span>
        </div>
        <div class="flex items-center justify-between gap-3">
          <span class="flex items-center gap-2">
            <span class="h-2.5 w-2.5 rounded-full bg-sky-400"></span>
            S&amp;P 500 (^GSPC)
          </span>
          <span class="font-mono">
            {{ typeof hoverInfo.spx === 'number' ? hoverInfo.spx.toFixed(2) : '—' }}
          </span>
        </div>
      </div>
    </div>

    <div class="mt-2 flex flex-wrap gap-4 text-xs text-slate-300">
      <div class="flex items-center gap-2">
        <span class="h-2.5 w-2.5 rounded-full bg-emerald-400"></span>
        <span>Forward P/E Ratio</span>
      </div>
      <div class="flex items-center gap-2">
        <span class="h-2.5 w-2.5 rounded-full bg-sky-400"></span>
        <span>S&amp;P 500 Index (^GSPC)</span>
      </div>
    </div>

    <FullscreenModal :open="showFullscreen" title="S&P 500 - Forward PE Ratio" @close="showFullscreen = false">
      <div class="flex flex-col gap-4 w-full h-full">
        <div class="relative flex-1 min-h-[420px]">
          <div ref="fullscreenContainerRef" class="absolute inset-0" />
          <div
            v-if="fullscreenHover"
            class="absolute bg-black/85 border border-white/20 rounded px-4 py-3 text-xs text-white pointer-events-none z-50 max-w-[260px] shadow-lg space-y-2"
            :style="tooltipStyle(fullscreenHover.position, fullscreenContainerRef ?? null, 260)"
          >
            <div class="text-sm font-semibold">{{ fullscreenHover.time }}</div>
            <div class="flex items-center justify-between gap-3">
              <span class="flex items-center gap-2">
                <span class="h-2.5 w-2.5 rounded-full bg-emerald-400"></span>
                Forward P/E
              </span>
              <span class="font-mono">
                {{ typeof fullscreenHover.pe === 'number' ? fullscreenHover.pe.toFixed(2) : '—' }}
              </span>
            </div>
            <div class="flex items-center justify-between gap-3">
              <span class="flex items-center gap-2">
                <span class="h-2.5 w-2.5 rounded-full bg-sky-400"></span>
                S&amp;P 500 (^GSPC)
              </span>
              <span class="font-mono">
                {{ typeof fullscreenHover.spx === 'number' ? fullscreenHover.spx.toFixed(2) : '—' }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </FullscreenModal>
  </div>
</template>
