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
import FullscreenModal from './FullscreenModal.vue';
import { fetchMarketBreadth } from '../services/api';

type LineSeries = ISeriesApi<'Line'>;
type OptionItem = { value: string; label: string };

const FALLBACK_RANGES = ['1M', '3M', 'YTD', '1Y', '5Y'];
const BREADTH_COLOR = '#f04949';
const PRICE_COLOR = '#bdc3c7';

const props = defineProps<{
  title: string;
  options: OptionItem[];
  benchmarkSymbol: string;
  benchmarkLabel: string;
  defaultSymbol?: string;
  chartKey?: string;
  rangeOptions?: string[];
  defaultRange?: string;
}>();

const pickDefaultSymbol = (options: OptionItem[]): string => {
  if (props.defaultSymbol && options.some((option) => option.value === props.defaultSymbol)) {
    return props.defaultSymbol;
  }
  return options[0]?.value ?? '';
};

const resolvedRangeOptions = computed(() => props.rangeOptions ?? FALLBACK_RANGES);
const pickDefaultRange = (options: string[]): string => {
  if (props.defaultRange && options.includes(props.defaultRange)) {
    return props.defaultRange;
  }
  if (options.includes('1M')) return '1M';
  return options[0] ?? '1M';
};

const rangeKey = ref(pickDefaultRange(resolvedRangeOptions.value));
watch(resolvedRangeOptions, (next) => {
  if (!next.length) {
    rangeKey.value = '1M';
  } else if (!next.includes(rangeKey.value)) {
    rangeKey.value = pickDefaultRange(next);
  }
});

const selectedSymbol = ref(pickDefaultSymbol(props.options));

watch(
  [() => props.options, () => props.defaultSymbol],
  () => {
    const nextOptions = props.options;
    if (!nextOptions.length) {
      selectedSymbol.value = '';
      return;
    }
    if (!nextOptions.some((option) => option.value === selectedSymbol.value)) {
      selectedSymbol.value = pickDefaultSymbol(nextOptions);
    }
  },
  { immediate: false },
);

const selectedOption = computed(
  () => props.options.find((option) => option.value === selectedSymbol.value) ?? { value: '', label: '--' },
);

const isQueryEnabled = computed(() => Boolean(selectedSymbol.value));

const { data, refetch } = useQuery({
  queryKey: computed(() => [
    'market-breadth',
    props.chartKey ?? props.title,
    props.benchmarkSymbol,
    selectedSymbol.value,
    rangeKey.value,
  ]),
  queryFn: () => fetchMarketBreadth([selectedSymbol.value], rangeKey.value, props.benchmarkSymbol),
  enabled: isQueryEnabled,
});

watch([rangeKey, selectedSymbol, () => props.benchmarkSymbol], () => {
  if (isQueryEnabled.value) {
    refetch();
  }
});

type TooltipEntry = { label: string; color: string; value?: number; unit: 'percent' | 'index' };

const hoverInfo = ref<
  | {
      time: string;
      entries: TooltipEntry[];
      position: { x: number; y: number };
    }
  | null
>(null);

const fullscreenHover = ref<
  | {
      time: string;
      entries: TooltipEntry[];
      position: { x: number; y: number };
    }
  | null
>(null);

const container = ref<HTMLDivElement | null>(null);
const fullscreenContainer = ref<HTMLDivElement | null>(null);
const showFullscreen = ref(false);
let chart: IChartApi | null = null;
let fullscreenChart: IChartApi | null = null;
let resizeObserver: ResizeObserver | null = null;
let fullscreenObserver: ResizeObserver | null = null;
let crosshairHandler: ((param: MouseEventParams) => void) | null = null;
let fullscreenCrosshairHandler: ((param: MouseEventParams) => void) | null = null;
const mainBreadthState: { series: LineSeries | null; symbol: string | null } = { series: null, symbol: null };
const mainPriceState: { series: LineSeries | null } = { series: null };
const fullscreenBreadthState: { series: LineSeries | null; symbol: string | null } = { series: null, symbol: null };
const fullscreenPriceState: { series: LineSeries | null } = { series: null };

const measureHeight = (el: HTMLElement): number => el.getBoundingClientRect().height || 360;

const tooltipStyle = (position: { x: number; y: number }, container: HTMLElement | null) => {
  const padding = 12;
  const offsetX = 70;
  const offsetY = 15;
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

const ensureBreadthSeries = (targetChart: IChartApi | null, symbolState: { series: LineSeries | null; symbol: string | null }) => {
  if (!targetChart) return null;
  if (!symbolState.series || symbolState.symbol !== selectedSymbol.value) {
    if (symbolState.series) {
      targetChart.removeSeries(symbolState.series);
    }
    symbolState.series = targetChart.addSeries(LineSeriesDefinition, {
      color: BREADTH_COLOR,
      lineWidth: 2,
      priceScaleId: 'left',
    });
    symbolState.symbol = selectedSymbol.value;
  } else {
    symbolState.series.applyOptions({ color: BREADTH_COLOR });
  }
  return symbolState.series;
};

const ensurePriceSeries = (targetChart: IChartApi | null, state: { series: LineSeries | null }) => {
  if (!targetChart) return null;
  if (state.series) return state.series;
  state.series = targetChart.addSeries(LineSeriesDefinition, {
    color: PRICE_COLOR,
    lineWidth: 2,
    priceScaleId: 'right',
  });
  return state.series;
};

const applyData = (
  targetChart: IChartApi | null,
  breadthState: { series: LineSeries | null; symbol: string | null },
  priceState: { series: LineSeries | null },
  hoverStore: typeof hoverInfo,
  store: 'main' | 'fullscreen',
) => {
  if (!targetChart || !data.value) return;
  const breadth = data.value.series[0];
  if (!breadth) return;
  const breadthLine = ensureBreadthSeries(targetChart, breadthState);
  breadthLine?.setData(
    (breadth?.points ?? []).map((point) => ({ time: point.time, value: point.value })),
  );

  const ndxPriceSeries = ensurePriceSeries(targetChart, priceState);
  ndxPriceSeries?.setData(
    data.value.benchmark_price.map((point) => ({ time: point.time, value: point.value })),
  );
  targetChart.priceScale('left').applyOptions({ autoScale: true, borderVisible: false });
  targetChart.priceScale('right').applyOptions({ autoScale: true, borderVisible: false });

  targetChart.timeScale().fitContent();
  attachCrosshair(targetChart, breadthLine, ndxPriceSeries, hoverStore, store);
};

const attachResize = (targetChart: IChartApi | null, el: HTMLDivElement | null, current: ResizeObserver | null) => {
  current?.disconnect();
  if (!targetChart || !el) return null;
  const observer = new ResizeObserver(() => {
    targetChart.applyOptions({ width: el.clientWidth, height: measureHeight(el) });
  });
  observer.observe(el);
  return observer;
};

const extractValue = (value: unknown): number | undefined => {
  if (typeof value === 'object' && value && 'value' in value) {
    const candidate = (value as { value?: number }).value;
    return typeof candidate === 'number' ? candidate : undefined;
  }
  return undefined;
};

const attachCrosshair = (
  targetChart: IChartApi | null,
  breadthLine: LineSeries | null,
  priceLine: LineSeries | null,
  hoverStore: typeof hoverInfo,
  store: 'main' | 'fullscreen',
) => {
  if (!targetChart) return;
  const existing = store === 'main' ? crosshairHandler : fullscreenCrosshairHandler;
  if (existing) targetChart.unsubscribeCrosshairMove(existing);
  const handler = (param: MouseEventParams) => {
    if (!param.time || !param.point) {
      hoverStore.value = null;
      return;
    }
    const time =
      typeof param.time === 'string'
        ? param.time
        : new Date((param.time as number) * 1000).toISOString().split('T')[0] || '';
    const entries: TooltipEntry[] = [];
    if (breadthLine) {
      const breadthValue = param.seriesData.get(breadthLine);
      entries.push({
        label: selectedOption.value.label,
        color: BREADTH_COLOR,
        value: extractValue(breadthValue),
        unit: 'percent',
      });
    }
    if (priceLine) {
      const priceValue = param.seriesData.get(priceLine);
      entries.push({
        label: props.benchmarkLabel,
        color: PRICE_COLOR,
        value: extractValue(priceValue),
        unit: 'index',
      });
    }
    hoverStore.value = {
      time,
      entries,
      position: { x: param.point.x, y: param.point.y },
    };
  };
  targetChart.subscribeCrosshairMove(handler);
  if (store === 'main') {
    crosshairHandler = handler;
  } else {
    fullscreenCrosshairHandler = handler;
  }
};

watch(
  () => data.value,
  async (payload) => {
    if (!payload) return;
    if (container.value && !chart) {
      await nextTick();
      if (container.value && !chart) {
        chart = initChart(container.value);
        resizeObserver = attachResize(chart, container.value, resizeObserver);
      }
    }
    applyData(chart, mainBreadthState, mainPriceState, hoverInfo, 'main');
    if (showFullscreen.value) {
      await nextTick();
      if (fullscreenContainer.value && !fullscreenChart) {
        fullscreenChart = initChart(fullscreenContainer.value);
        fullscreenObserver = attachResize(fullscreenChart, fullscreenContainer.value, fullscreenObserver);
      }
      applyData(fullscreenChart, fullscreenBreadthState, fullscreenPriceState, fullscreenHover, 'fullscreen');
    }
  },
  { immediate: true },
);

const openFullscreen = async () => {
  showFullscreen.value = true;
  await nextTick();
  if (fullscreenContainer.value && !fullscreenChart) {
    fullscreenChart = initChart(fullscreenContainer.value);
    fullscreenObserver = attachResize(fullscreenChart, fullscreenContainer.value, fullscreenObserver);
  }
  applyData(fullscreenChart, fullscreenBreadthState, fullscreenPriceState, fullscreenHover, 'fullscreen');
};

watch(showFullscreen, (open) => {
  if (!open && fullscreenChart) {
    if (fullscreenCrosshairHandler) {
      fullscreenChart.unsubscribeCrosshairMove(fullscreenCrosshairHandler);
      fullscreenCrosshairHandler = null;
    }
    fullscreenObserver?.disconnect();
    fullscreenChart.remove();
    fullscreenChart = null;
    fullscreenBreadthState.series = null;
    fullscreenBreadthState.symbol = null;
    fullscreenPriceState.series = null;
    fullscreenHover.value = null;
  }
});

onBeforeUnmount(() => {
  if (chart && crosshairHandler) {
    chart.unsubscribeCrosshairMove(crosshairHandler);
  }
  chart?.remove();
  resizeObserver?.disconnect();
  if (fullscreenChart && fullscreenCrosshairHandler) {
    fullscreenChart.unsubscribeCrosshairMove(fullscreenCrosshairHandler);
  }
  fullscreenChart?.remove();
  fullscreenObserver?.disconnect();
});
</script>

<template>
  <div class="bg-panel border border-white/10 rounded-xl p-4 flex flex-col gap-4 h-full w-full">
    <div class="flex flex-wrap justify-between items-center gap-4">
      <div>
        <div class="text-xl text-accentCyan font-semibold uppercase">
          {{ props.title }}
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-4">
        <label class="text-sm uppercase tracking-wide text-textMuted flex flex-col gap-1">
          Breadth Indicator
          <select
            v-model="selectedSymbol"
            :disabled="!props.options.length"
            class="bg-black/40 border border-white/20 rounded px-2 py-1 text-white text-sm focus:outline-none"
          >
            <option v-for="option in props.options" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>
        <TimeRangeSelector v-model="rangeKey" :options="resolvedRangeOptions" />
        <button
          class="h-10 w-10 rounded-full text-textMuted hover:text-white flex items-center justify-center hover:bg-white/10 transition-colors"
          @click="openFullscreen"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 9V5h4M20 9V5h-4M4 15v4h4m12-4v4h-4" />
          </svg>
        </button>
      </div>
    </div>
    <div class="relative flex-1 w-full aspect-[4/3] md:aspect-auto md:min-h-[360px]">
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
    <div class="text-xs text-textMuted flex flex-wrap items-center gap-4">
      <span class="flex items-center gap-2">
        <span
          class="w-4 h-1 rounded-full"
          :style="{ backgroundColor: BREADTH_COLOR }"
        ></span>
        <span>{{ selectedOption.label }} (Left Axis)</span>
      </span>
      <span class="flex items-center gap-2">
        <span class="w-4 h-1 rounded-full" :style="{ backgroundColor: PRICE_COLOR }"></span>
        <span>{{ props.benchmarkLabel }} (Right Axis)</span>
      </span>
    </div>
    <FullscreenModal :open="showFullscreen" :title="props.title" @close="showFullscreen = false">
      <div class="relative flex-1 min-h-[70vh] w-full">
        <div ref="fullscreenContainer" class="absolute inset-0"></div>
        <div
          v-if="fullscreenHover"
          class="absolute bg-black/80 border border-white/20 rounded px-3 py-2 text-xs text-white pointer-events-none z-50 max-w-[220px]"
          :style="tooltipStyle(fullscreenHover.position, fullscreenContainer)"
        >
          <div>{{ fullscreenHover.time }}</div>
          <div v-for="entry in fullscreenHover.entries" :key="entry.label" class="flex justify-between gap-3">
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
      <div class="text-xs text-textMuted flex flex-wrap items-center gap-4 px-4 pb-4">
        <span class="flex items-center gap-2">
          <span
            class="w-4 h-1 rounded-full"
            :style="{ backgroundColor: BREADTH_COLOR }"
          ></span>
          <span>{{ selectedOption.label }} (Left Axis)</span>
        </span>
        <span class="flex items-center gap-2">
          <span class="w-4 h-1 rounded-full" :style="{ backgroundColor: PRICE_COLOR }"></span>
          <span>{{ props.benchmarkLabel }} (Right Axis)</span>
        </span>
      </div>
    </FullscreenModal>
  </div>
</template>
