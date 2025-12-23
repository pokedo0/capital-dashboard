<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import {
  AreaSeries as AreaSeriesDefinition,
  LineSeries as LineSeriesDefinition,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type MouseEventParams,
  type Time,
} from 'lightweight-charts';
import { useQuery } from '@tanstack/vue-query';
import TimeRangeSelector from './TimeRangeSelector.vue';
import { fetchDrawdown } from '../services/api';

type AreaSeries = ISeriesApi<'Area'>;
type LineSeries = ISeriesApi<'Line'>;

const SYMBOLS = ['SPY', 'TSLA', 'NVDA', 'AAPL', 'MSFT', 'META'];

const selectedSymbol = ref('SPY');
const rangeKey = ref('1Y');
const chartContainer = ref<HTMLDivElement | null>(null);

const { data, refetch } = useQuery({
  queryKey: computed(() => ['drawdown', selectedSymbol.value, rangeKey.value]),
  queryFn: () => fetchDrawdown(selectedSymbol.value, rangeKey.value),
});

watch([selectedSymbol, rangeKey], () => refetch());

let chart: IChartApi | null = null;
let fillAreaSeries: AreaSeries | null = null;
let maskAreaSeries: AreaSeries | null = null;
let drawdownLineSeries: LineSeries | null = null;
let priceSeries: LineSeries | null = null;
let scaleAnchorSeries: LineSeries | null = null;
let observer: ResizeObserver | null = null;

type HoverInfo =
  | {
      time: string;
      drawdown?: number;
      price?: number;
      position: { x: number; y: number };
    }
  | null;
const hoverInfo = ref<HoverInfo>(null);

const resolveValue = (point: unknown): number | undefined => {
  if (typeof point === 'object' && point && 'value' in point) {
    const value = (point as { value?: number }).value;
    return typeof value === 'number' ? value : undefined;
  }
  return undefined;
};

let crosshairHandler: ((param: MouseEventParams) => void) | null = null;

const measureSize = (element: HTMLElement) => {
  const rect = element.getBoundingClientRect();
  const width = rect.width || element.clientWidth || element.offsetWidth || 0;
  const height = rect.height || element.clientHeight || element.offsetHeight || 360;
  return { width, height };
};

const initChart = () => {
  if (!chartContainer.value) return;
  disposeChart();
  const size = measureSize(chartContainer.value);
  chart = createChart(chartContainer.value, {
    height: size.height,
    layout: {
      background: { color: '#050505' },
      textColor: '#f8fafc',
      fontFamily: "'IBM Plex Sans', Inter, ui-sans-serif",
    },
    leftPriceScale: {
      visible: true,
      borderVisible: false,
      autoScale: true,
      scaleMargins: { top: 0.05, bottom: 0.05 },
    },
    rightPriceScale: {
      borderVisible: false,
      scaleMargins: { top: 0.1, bottom: 0.1 },
    },
    timeScale: {
      borderVisible: false,
      timeVisible: true,
    },
    grid: {
      horzLines: { color: 'rgba(255,255,255,0.05)' },
      vertLines: { color: 'rgba(255,255,255,0.05)' },
    },
  });
  chart.applyOptions({ width: size.width, height: size.height });
  chart.priceScale('left').applyOptions({
    borderVisible: false,
    scaleMargins: { top: 0.05, bottom: 0.05 },
  });

  fillAreaSeries = chart.addSeries(AreaSeriesDefinition, {
    priceScaleId: 'left',
    lineColor: 'rgba(37,99,235,0)',
    topColor: 'rgba(37,99,235,0.85)',
    bottomColor: 'rgba(37,99,235,0.85)',
    priceFormat: {
      type: 'custom',
      formatter: (price: number) => `${price.toFixed(0)}%`,
      minMove: 0.01,
    },
  });
  maskAreaSeries = chart.addSeries(AreaSeriesDefinition, {
    priceScaleId: 'left',
    lineColor: '#050505',
    topColor: '#050505',
    bottomColor: '#050505',
    priceFormat: {
      type: 'custom',
      formatter: (price: number) => `${price.toFixed(0)}%`,
      minMove: 0.01,
    },
  });
  drawdownLineSeries = chart.addSeries(LineSeriesDefinition, {
    priceScaleId: 'left',
    color: '#ffffff',
    lineWidth: 1,
    lineStyle: 2,
    crosshairMarkerVisible: true,
    crosshairMarkerBorderColor: '#ffffff',
    crosshairMarkerBackgroundColor: '#ffffff',
    crosshairMarkerRadius: 1,
    priceFormat: {
      type: 'custom',
      formatter: (price: number) => `${price.toFixed(0)}%`,
      minMove: 0.01,
    },
  });
  priceSeries = chart.addSeries(LineSeriesDefinition, {
    priceScaleId: 'right',
    color: '#f78c1f',
    lineWidth: 2,
  });
  scaleAnchorSeries = chart.addSeries(LineSeriesDefinition, {
    priceScaleId: 'left',
    color: 'rgba(0,0,0,0)',
    lineWidth: 1,
    priceLineVisible: false,
    lastValueVisible: false,
  });

  observer = new ResizeObserver(() => {
    if (chart && chartContainer.value) {
      const nextSize = measureSize(chartContainer.value);
      chart.applyOptions({ width: nextSize.width, height: nextSize.height });
    }
  });
  observer.observe(chartContainer.value);

  crosshairHandler = (param: MouseEventParams) => {
    if (!drawdownLineSeries || !priceSeries || !param.time || !param.point) {
      hoverInfo.value = null;
      return;
    }
    const drawdownPoint = param.seriesData.get(drawdownLineSeries);
    const pricePoint = param.seriesData.get(priceSeries);
    const time =
      typeof param.time === 'string'
        ? param.time
        : new Date((param.time as number) * 1000).toISOString().split('T')[0] || '';
    hoverInfo.value = {
      time,
      drawdown: resolveValue(drawdownPoint),
      price: resolveValue(pricePoint),
      position: { x: param.point.x, y: param.point.y },
    };
  };
  chart.subscribeCrosshairMove(crosshairHandler);
};

const disposeChart = () => {
  observer?.disconnect();
  observer = null;
  if (chart && crosshairHandler) {
    chart.unsubscribeCrosshairMove(crosshairHandler);
  }
  chart?.remove();
  chart = null;
  fillAreaSeries = null;
  maskAreaSeries = null;
  drawdownLineSeries = null;
  priceSeries = null;
  scaleAnchorSeries = null;
  crosshairHandler = null;
  hoverInfo.value = null;
};

onBeforeUnmount(disposeChart);

watch(
  () => data.value,
  (payload) => {
    if (!payload || !chartContainer.value) return;
    if (!chart) {
      initChart();
    }
    if (
      !chart ||
      !fillAreaSeries ||
      !maskAreaSeries ||
      !drawdownLineSeries ||
      !priceSeries
    ) {
      return;
    }

    const drawdownData = payload.drawdown.map((point) => ({ time: point.time, value: point.value }));
    const minValue = drawdownData.reduce((acc, point) => Math.min(acc, point.value ?? 0), 0);
    const step = 5;
    const lowerBound = Math.min(Math.floor(minValue / step) * step, -30);
    axisLowerBound.value = lowerBound;

    fillAreaSeries.setData(drawdownData.map((point) => ({ time: point.time, value: 0 })));
    maskAreaSeries.setData(drawdownData);
    drawdownLineSeries.setData(drawdownData);
    if (scaleAnchorSeries && drawdownData.length) {
      const fallbackTime = new Date().toISOString().split('T')[0] as Time;
      const firstTime =
        (drawdownData[0]?.time ?? payload.price[0]?.time ?? fallbackTime) as Time;
      const lastTime =
        (drawdownData[drawdownData.length - 1]?.time ??
          payload.price[payload.price.length - 1]?.time ??
          firstTime) as Time;
      scaleAnchorSeries.setData([
        { time: firstTime, value: 0 },
        { time: lastTime, value: lowerBound },
      ]);
    }
    priceSeries.setData(payload.price.map((point) => ({ time: point.time, value: point.value })));
    chart.timeScale().fitContent();
  },
  { immediate: true },
);

const currentDrawdown = computed(() => data.value?.current_drawdown ?? 0);
const maxDrawdown = computed(() => data.value?.max_drawdown ?? 0);
const axisLowerBound = ref(-40);
const yAxisValues = computed(() => {
  const values: number[] = [];
  for (let value = 0; value >= axisLowerBound.value; value -= 5) {
    values.push(value);
  }
  return values;
});
const symbolInput = computed({
  get: () => selectedSymbol.value,
  set: (val: string) => {
    selectedSymbol.value = val.trim().toUpperCase();
  },
});
</script>

<template>
  <div class="bg-panel border border-white/10 rounded-xl p-4 flex flex-col gap-4 relative w-full">
    <div class="flex flex-wrap justify-between items-center gap-4">
      <div>
        <div class="text-xl font-semibold uppercase">{{ selectedSymbol }} Drawdown</div>
        <div class="text-sm text-textMuted flex items-center gap-3">
          <span>
            Current drawdown:
            <span class="text-white font-semibold">{{ currentDrawdown.toFixed(2) }}%</span>
          </span>
          <span>
            Max drawdown:
            <span class="text-accentRed font-semibold">{{ maxDrawdown.toFixed(2) }}%</span>
          </span>
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-3">
        <div>
          <input
            v-model="symbolInput"
            list="drawdown-symbols"
            class="bg-panel border border-white/20 rounded px-3 py-1 text-white uppercase"
            placeholder="Enter symbol"
          />
          <datalist id="drawdown-symbols">
            <option v-for="symbol in SYMBOLS" :key="symbol" :value="symbol" />
          </datalist>
        </div>
        <TimeRangeSelector v-model="rangeKey" />
      </div>
    </div>
    <div class="relative w-full aspect-[4/3] md:aspect-auto md:min-h-[360px] flex-1">
      <div ref="chartContainer" class="absolute inset-0"></div>
        <div
        v-if="hoverInfo"
        class="absolute bg-black/80 border border-white/20 rounded px-3 py-2 text-xs text-white pointer-events-none z-50 shadow-lg"
        :style="{
          left: `calc(${hoverInfo.position.x}px + 12px)`,
          top: `calc(${hoverInfo.position.y}px - 40px)`,
        }"
      >
        <div>{{ hoverInfo.time }}</div>
        <div class="flex items-center justify-between gap-3">
          <span class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-[#1d4ed8]"></span>
            Drawdown
          </span>
          <span>{{ hoverInfo.drawdown?.toFixed(2) ?? '--' }}%</span>
        </div>
        <div class="flex items-center justify-between gap-3">
          <span class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-[#f78c1f]"></span>
            Price
          </span>
          <span>{{ hoverInfo.price?.toFixed(2) ?? '--' }}</span>
        </div>
    </div>
    </div>
    <div class="text-xs uppercase tracking-wide flex gap-4 text-textMuted">
      <span class="flex items-center gap-2">
        <span class="w-4 h-1 bg-[#1d4ed8] rounded-full"></span> Drawdown (%)
      </span>
      <span class="flex items-center gap-2">
        <span class="w-4 h-1 bg-[#f78c1f] rounded-full"></span> Price ($)
      </span>
    </div>
  </div>
</template>
