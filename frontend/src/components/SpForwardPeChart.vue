<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
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
import { fetchForwardPeComparison } from '../services/api';

type LineSeries = ISeriesApi<'Line'>;

const rangeOptions = ['6M', 'YTD', '1Y', '5Y'];
const rangeKey = ref('1Y');

const { data, refetch } = useQuery({
  queryKey: computed(() => ['forward-pe', rangeKey.value]),
  queryFn: () => fetchForwardPeComparison(rangeKey.value),
});

watch(rangeKey, () => refetch());

const containerRef = ref<HTMLDivElement | null>(null);
let chart: IChartApi | null = null;
let peSeries: LineSeries | null = null;
let spxSeries: LineSeries | null = null;
let observer: ResizeObserver | null = null;
let crosshairHandler: ((param: MouseEventParams) => void) | null = null;

type HoverInfo = {
  time: string;
  pe?: number;
  spx?: number;
  position: { x: number; y: number };
} | null;

const hoverInfo = ref<HoverInfo>(null);

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
  },
  { immediate: true },
);

onMounted(() => {
  if (containerRef.value) {
    initChart();
  }
});

onBeforeUnmount(disposeChart);
</script>

<template>
  <div class="rounded-2xl border border-white/5 bg-white/5 bg-gradient-to-br from-white/5 via-white/0 to-white/5 p-6 shadow-xl">
    <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div>
        <p class="text-sm uppercase tracking-[0.18em] text-slate-400">Valuation Pulse</p>
        <h3 class="text-2xl font-semibold text-white">S&amp;P 500 - Forward P/E vs Index</h3>
        <p class="text-xs text-slate-400">Daily forward P/E from MacroMicro, indexed against ^GSPC closes.</p>
      </div>
      <TimeRangeSelector v-model="rangeKey" :options="rangeOptions" />
    </div>

    <div class="relative mt-4 h-[420px] rounded-xl bg-[#0b0b0f]">
      <div ref="containerRef" class="absolute inset-0" />
      <div
        v-if="hoverInfo"
        class="pointer-events-none absolute z-20 w-64 rounded-xl border border-white/10 bg-black/80 p-3 text-sm backdrop-blur"
        :style="tooltipStyle(hoverInfo.position, containerRef ?? null)"
      >
        <div class="text-white font-semibold">{{ hoverInfo.time }}</div>
        <div class="mt-2 space-y-1.5">
          <div class="flex items-center justify-between text-slate-100">
            <span class="flex items-center gap-2">
              <span class="h-2.5 w-2.5 rounded-full bg-emerald-400"></span>
              Forward P/E
            </span>
            <span class="font-mono">
              {{ typeof hoverInfo.pe === 'number' ? hoverInfo.pe.toFixed(2) : '—' }}
            </span>
          </div>
          <div class="flex items-center justify-between text-slate-100">
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
    </div>

    <div class="mt-4 flex flex-wrap gap-4 text-xs text-slate-300">
      <div class="flex items-center gap-2">
        <span class="h-2.5 w-2.5 rounded-full bg-emerald-400"></span>
        <span>Forward P/E Ratio</span>
      </div>
      <div class="flex items-center gap-2">
        <span class="h-2.5 w-2.5 rounded-full bg-sky-400"></span>
        <span>S&amp;P 500 Index (^GSPC)</span>
      </div>
    </div>
  </div>
</template>
