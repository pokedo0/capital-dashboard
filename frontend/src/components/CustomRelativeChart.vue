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
import FullscreenModal from './FullscreenModal.vue';
import { fetchRelativePerformance } from '../services/api';

type LineSeries = ISeriesApi<'Line'>;

const props = defineProps<{
  symbols: string[];
  hiddenSymbols?: Set<string>;
  range: string;
  colors: string[];
}>();

// Map symbol to color based on index
const getColor = (symbol: string) => {
  const index = props.symbols.indexOf(symbol);
  return index >= 0 ? props.colors[index % props.colors.length] : '#ffffff';
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

const showFullscreen = ref(false);

const { data } = useQuery({
  queryKey: computed(() => ['relative', 'custom-group', props.symbols.join(','), props.range]),
  queryFn: () => {
    if (!props.symbols.length) return Promise.resolve([]);
    return fetchRelativePerformance(props.symbols, props.range);
  },
  enabled: computed(() => props.symbols.length > 0),
});

const transformedData = computed(() => {
  if (!data.value) return null;
  return data.value.map((series) => {
    let points = series.points;
    if (props.range === '5Y' || props.range === '3Y') {
      points = downsampleWeekly(points);
    }
    return { ...series, points };
  });
});

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
      horzLines: { color: 'rgba(255,255,255,0.05)' },
      vertLines: { color: 'rgba(255,255,255,0.05)' },
    },
    rightPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false, timeVisible: true },
    crosshair: {
      vertLine: {
        color: 'rgba(255, 255, 255, 0.2)',
        labelBackgroundColor: '#2B2B43',
      },
      horzLine: {
        color: 'rgba(255, 255, 255, 0.2)',
        labelBackgroundColor: '#2B2B43',
      },
    },
  });
};

const ensureSeries = (chart: IChartApi | null, map: Map<string, LineSeries>, symbol: string) => {
  if (!chart) return null;
  if (map.has(symbol)) return map.get(symbol)!;
  const series = chart.addSeries(LineSeriesDefinition, {
    color: getColor(symbol),
    lineWidth: 2,
    priceLineVisible: false,
  });
  map.set(symbol, series);
  return series;
};

const syncVisibility = (map: Map<string, LineSeries>) => {
  map.forEach((series, symbol) => {
    const isHidden = props.hiddenSymbols?.has(symbol) ?? false;
    series.applyOptions({ visible: !isHidden });
  });
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
  if (!chart) return;
  
  // Clean up removed symbols
  const currentSymbols = new Set(payload?.map(p => p.symbol) || []);
  for (const [symbol, series] of map.entries()) {
    if (!currentSymbols.has(symbol)) {
      chart.removeSeries(series);
      map.delete(symbol);
    }
  }

  // Add/Update symbols
  if (payload) {
    payload.forEach((seriesData) => {
      const series = ensureSeries(chart, map, seriesData.symbol);
      series?.applyOptions({ color: getColor(seriesData.symbol) }); // Update color if changed
      series?.setData(seriesData.points.map((point) => ({ time: point.time, value: point.value })));
    });
  }

  syncVisibility(map);
  resetViewport(chart);
  attachCrosshair(chart, map, hoverTarget, type);
};

const attachResize = (chart: IChartApi | null, container: HTMLDivElement | null, existing: ResizeObserver | null) => {
  existing?.disconnect();
  if (!chart || !container) return null;
  const observer = new ResizeObserver(() => {
    chart.applyOptions({ width: container.clientWidth, height: measureHeight(container) });
  });
  observer.observe(container);
  return observer;
};

// Watch for hiddenSymbols changes specifically
watch(
  () => props.hiddenSymbols,
  () => {
    syncVisibility(seriesMap);
    syncVisibility(fullscreenSeriesMap);
  },
  { deep: true }
);

// Watch for data AND symbols changes
watch(
  [() => transformedData.value, () => props.symbols, () => props.colors],
  async () => {
    const seriesPayload = transformedData.value;
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
  { immediate: true, deep: true },
);

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
    
    const entries = Array.from(map.entries())
      .filter(([symbol]) => !props.hiddenSymbols?.has(symbol))
      .map(([symbol, series]) => {
        const value = param.seriesData.get(series);
        return {
          label: symbol,
          color: getColor(symbol) ?? '#ffffff',
          value: extractValue(value),
        };
      })
      .filter(e => e.value !== undefined) // Only show lines with data at this point
      .sort((a, b) => (b.value ?? Number.NEGATIVE_INFINITY) - (a.value ?? Number.NEGATIVE_INFINITY));
    hoverTarget.value = { time, entries, position: { x: param.point.x, y: param.point.y } };
  };
  
  const existing = type === 'main' ? mainCrosshairHandler : fullscreenCrosshairHandler;
  if (existing) chart.unsubscribeCrosshairMove(existing);

  chart.subscribeCrosshairMove(handler);
  
  if (type === 'main') mainCrosshairHandler = handler;
  else fullscreenCrosshairHandler = handler;
};
</script>

<template>
  <div class="h-full w-full flex flex-col">
    <div class="relative flex-1 w-full aspect-[4/3] md:aspect-auto md:min-h-[360px]">
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
      <!-- Fullscreen Button Overlay -->
      <button
          class="absolute top-2 right-2 h-8 w-8 rounded-full text-textMuted hover:text-white flex items-center justify-center hover:bg-white/10 transition-colors z-20"
          @click="openFullscreen"
          title="Fullscreen"
        >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 9V5h4M20 9V5h-4M4 15v4h4m12-4v4h-4" />
        </svg>
      </button>
    </div>

    <FullscreenModal :open="showFullscreen" title="Custom Asset Relative Performance" @close="showFullscreen = false">
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
      </div>
    </FullscreenModal>
  </div>
</template>
