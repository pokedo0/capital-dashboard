<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import {
  LineSeries as LineSeriesDefinition,
  createChart,
  PriceScaleMode,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type MouseEventParams,
  type Time,
  type BusinessDay,
} from "lightweight-charts";
import { useQuery } from "@tanstack/vue-query";
import TimeRangeSelector from "./TimeRangeSelector.vue";
import FullscreenModal from "./FullscreenModal.vue";
import { fetchSpyRspRatio } from "../services/api";

type LineSeries = ISeriesApi<"Line">;

const rangeOptions = ["6M", "YTD", "1Y", "3Y", "5Y"];
const rangeKey = ref("1Y");
const showFullscreen = ref(false);

// Threshold line at 3.5
const THRESHOLD_LINE = {
  value: 3.5,
  label: "Threshold",
  color: "#2b228c",
} as const;

const { data, refetch } = useQuery({
  queryKey: computed(() => ["spy-rsp-ratio", rangeKey.value]),
  queryFn: () => fetchSpyRspRatio(rangeKey.value),
});

watch(rangeKey, () => refetch());

const containerRef = ref<HTMLDivElement | null>(null);
const fullscreenContainerRef = ref<HTMLDivElement | null>(null);
let chart: IChartApi | null = null;
let ratioSeries: LineSeries | null = null;
let magsSeries: LineSeries | null = null;
let observer: ResizeObserver | null = null;
let crosshairHandler: ((param: MouseEventParams) => void) | null = null;
let fullscreenChart: IChartApi | null = null;
let fullscreenRatioSeries: LineSeries | null = null;
let fullscreenMagsSeries: LineSeries | null = null;
let fullscreenObserver: ResizeObserver | null = null;
let fullscreenCrosshairHandler: ((param: MouseEventParams) => void) | null =
  null;

type HoverInfo = {
  time: string;
  ratio?: number;
  mags?: number;
  position: { x: number; y: number };
} | null;

const hoverInfo = ref<HoverInfo>(null);
const fullscreenHover = ref<HoverInfo>(null);

const measureSize = (element: HTMLElement) => {
  const rect = element.getBoundingClientRect();
  return {
    width: rect.width || element.clientWidth || element.offsetWidth || 0,
    height: rect.height || element.clientHeight || element.offsetHeight || 420,
  };
};

const extractValue = (point: unknown): number | undefined => {
  if (typeof point === "object" && point && "value" in point) {
    const value = (point as { value?: number }).value;
    return typeof value === "number" ? value : undefined;
  }
  return undefined;
};

const formatTime = (value: Time) => {
  if (typeof value === "string") return value;
  if (typeof value === "number") {
    const date = new Date(value * 1000);
    return date.toISOString().split("T")[0] ?? "";
  }
  const day = String((value as BusinessDay).day).padStart(2, "0");
  const month = String((value as BusinessDay).month).padStart(2, "0");
  return `${(value as BusinessDay).year}-${month}-${day}`;
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
  const maxLeft = containerWidth
    ? containerWidth - width - padding - rightAxisGuard
    : baseLeft;
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
  ratioSeries = null;
  magsSeries = null;
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
  fullscreenRatioSeries = null;
  fullscreenMagsSeries = null;
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
      background: { color: "#050505" },
      textColor: "#f8fafc",
      fontFamily: "'IBM Plex Sans', Inter, ui-sans-serif",
    },
    leftPriceScale: {
      borderVisible: true,
      visible: true,
      autoScale: true,
      mode: PriceScaleMode.Normal,
      entireTextOnly: true,
    },
    rightPriceScale: {
      borderVisible: true,
      autoScale: true,
      mode: PriceScaleMode.Normal,
    },
    timeScale: { borderVisible: false, timeVisible: true },
    grid: {
      horzLines: { color: "rgba(255,255,255,0.05)" },
      vertLines: { color: "rgba(255,255,255,0.05)" },
    },
    crosshair: { mode: 1 },
  });
  chart.applyOptions({ width: size.width, height: size.height });

  ratioSeries = chart.addSeries(LineSeriesDefinition, {
    color: "#f04949",
    lineWidth: 2,
    priceLineVisible: false,
    priceScaleId: "left",
    lastValueVisible: true,
  });
  ratioSeries.applyOptions({
    priceFormat: {
      type: "custom",
      formatter: (value: number) => value.toFixed(3),
    },
  });

  // Add threshold line at 3.5
  ratioSeries.createPriceLine({
    price: THRESHOLD_LINE.value,
    color: THRESHOLD_LINE.color,
    lineWidth: 1,
    lineStyle: LineStyle.Dashed,
    axisLabelVisible: true,
    title: THRESHOLD_LINE.label,
  });

  magsSeries = chart.addSeries(LineSeriesDefinition, {
    color: "#bdc3c7",
    lineWidth: 2,
    priceLineVisible: false,
    priceScaleId: "right",
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
    if (!param.time || !param.point || !ratioSeries || !magsSeries) {
      hoverInfo.value = null;
      return;
    }
    const ratioPoint = param.seriesData.get(ratioSeries);
    const magsPoint = param.seriesData.get(magsSeries);
    hoverInfo.value = {
      time: formatTime(param.time),
      ratio: extractValue(ratioPoint),
      mags: extractValue(magsPoint),
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
      background: { color: "#050505" },
      textColor: "#f8fafc",
      fontFamily: "'IBM Plex Sans', Inter, ui-sans-serif",
    },
    leftPriceScale: {
      borderVisible: true,
      visible: true,
      autoScale: true,
      mode: PriceScaleMode.Normal,
      entireTextOnly: true,
    },
    rightPriceScale: {
      borderVisible: true,
      autoScale: true,
      mode: PriceScaleMode.Normal,
    },
    timeScale: { borderVisible: false, timeVisible: true },
    grid: {
      horzLines: { color: "rgba(255,255,255,0.05)" },
      vertLines: { color: "rgba(255,255,255,0.05)" },
    },
    crosshair: { mode: 1 },
  });
  fullscreenChart.applyOptions({ width: size.width, height: size.height });

  fullscreenRatioSeries = fullscreenChart.addSeries(LineSeriesDefinition, {
    color: "#f04949",
    lineWidth: 2,
    priceLineVisible: false,
    priceScaleId: "left",
    lastValueVisible: true,
  });
  fullscreenRatioSeries.applyOptions({
    priceFormat: {
      type: "custom",
      formatter: (value: number) => value.toFixed(3),
    },
  });

  // Add threshold line at 3.5
  fullscreenRatioSeries.createPriceLine({
    price: THRESHOLD_LINE.value,
    color: THRESHOLD_LINE.color,
    lineWidth: 1,
    lineStyle: LineStyle.Dashed,
    axisLabelVisible: true,
    title: THRESHOLD_LINE.label,
  });

  fullscreenMagsSeries = fullscreenChart.addSeries(LineSeriesDefinition, {
    color: "#bdc3c7",
    lineWidth: 2,
    priceLineVisible: false,
    priceScaleId: "right",
    lastValueVisible: true,
  });

  fullscreenObserver = new ResizeObserver(() => {
    if (fullscreenContainerRef.value && fullscreenChart) {
      const nextSize = measureSize(fullscreenContainerRef.value);
      fullscreenChart.applyOptions({
        width: nextSize.width,
        height: nextSize.height,
      });
    }
  });
  fullscreenObserver.observe(fullscreenContainerRef.value);

  fullscreenCrosshairHandler = (param: MouseEventParams) => {
    if (
      !param.time ||
      !param.point ||
      !fullscreenRatioSeries ||
      !fullscreenMagsSeries
    ) {
      fullscreenHover.value = null;
      return;
    }
    const ratioPoint = param.seriesData.get(fullscreenRatioSeries);
    const magsPoint = param.seriesData.get(fullscreenMagsSeries);
    fullscreenHover.value = {
      time: formatTime(param.time),
      ratio: extractValue(ratioPoint),
      mags: extractValue(magsPoint),
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
    if (!chart || !ratioSeries || !magsSeries) return;
    ratioSeries.setData(
      payload.ratio.map((point) => ({ time: point.time, value: point.value })),
    );
    magsSeries.setData(
      payload.mags.map((point) => ({ time: point.time, value: point.value })),
    );
    chart.timeScale().fitContent();
    chart
      .priceScale("left")
      .applyOptions({ autoScale: true, visible: true, borderVisible: true });
    chart.priceScale("right").applyOptions({ autoScale: true });

    if (fullscreenChart && fullscreenRatioSeries && fullscreenMagsSeries) {
      fullscreenRatioSeries.setData(
        payload.ratio.map((point) => ({
          time: point.time,
          value: point.value,
        })),
      );
      fullscreenMagsSeries.setData(
        payload.mags.map((point) => ({ time: point.time, value: point.value })),
      );
      fullscreenChart.timeScale().fitContent();
      fullscreenChart.priceScale("left").applyOptions({
        autoScale: true,
        visible: true,
        borderVisible: true,
      });
      fullscreenChart.priceScale("right").applyOptions({ autoScale: true });
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
      if (
        data.value &&
        fullscreenRatioSeries &&
        fullscreenMagsSeries &&
        fullscreenChart
      ) {
        fullscreenRatioSeries.setData(
          data.value.ratio.map((point) => ({
            time: point.time,
            value: point.value,
          })),
        );
        fullscreenMagsSeries.setData(
          data.value.mags.map((point) => ({
            time: point.time,
            value: point.value,
          })),
        );
        fullscreenChart.timeScale().fitContent();
      }
    } else {
      disposeFullscreen();
    }
  },
);

// Computed for latest ratio value
const latestRatio = computed(() => {
  const series = data.value?.ratio;
  const latest =
    series && series.length ? series[series.length - 1] : undefined;
  if (
    latest &&
    typeof latest.value === "number" &&
    Number.isFinite(latest.value)
  ) {
    return latest.value.toFixed(3);
  }
  return "--";
});

const isAboveThreshold = computed(() => {
  const series = data.value?.ratio;
  const latest =
    series && series.length ? series[series.length - 1] : undefined;
  return (
    latest &&
    typeof latest.value === "number" &&
    latest.value >= THRESHOLD_LINE.value
  );
});

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
  <div
    class="bg-panel border border-white/10 rounded-xl p-4 flex flex-col gap-4 w-full"
  >
    <div class="flex flex-wrap justify-between items-center gap-4">
      <div>
        <div class="text-xl text-accentCyan font-semibold uppercase">
          SPY/RSP Ratio
        </div>
      </div>
      <div class="flex items-center gap-3">
        <TimeRangeSelector v-model="rangeKey" :options="rangeOptions" />
        <button
          class="h-10 w-10 rounded-full text-textMuted hover:text-white flex items-center justify-center hover:bg-white/10 transition-colors"
          @click="showFullscreen = true"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-6 w-6"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="1.8"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M4 9V5h4M20 9V5h-4M4 15v4h4m12-4v4h-4"
            />
          </svg>
        </button>
      </div>
    </div>

    <div
      class="flex flex-wrap gap-2 text-xs uppercase tracking-wide items-center"
    >
      <span class="text-textMuted flex items-center gap-1 text-sm">
        Current Ratio：
        <span
          :class="[
            'font-semibold text-base',
            isAboveThreshold ? 'text-red-400' : 'text-green-400',
          ]"
          >{{ latestRatio }}</span
        >
      </span>
      <span
        v-if="isAboveThreshold"
        class="px-2 py-0.5 rounded-full bg-red-500/30 text-red-200"
      >
        Above Threshold
      </span>
      <span
        v-else
        class="px-2 py-0.5 rounded-full bg-green-500/30 text-green-200"
      >
        Below Threshold
      </span>
    </div>

    <div
      class="relative flex-1 w-full aspect-[4/3] md:aspect-auto md:min-h-[360px]"
    >
      <div ref="containerRef" class="absolute inset-0" />
      <div
        v-if="hoverInfo"
        class="absolute bg-black/85 border border-white/20 rounded px-4 py-3 text-xs text-white pointer-events-none z-50 max-w-[240px] shadow-lg space-y-2"
        :style="tooltipStyle(hoverInfo.position, containerRef ?? null, 240)"
      >
        <div class="text-sm font-semibold">{{ hoverInfo.time }}</div>
        <div class="flex items-center justify-between gap-3">
          <span class="flex items-center gap-2">
            <span
              class="h-2.5 w-2.5 rounded-full"
              style="background-color: #f04949"
            ></span>
            SPY/RSP Ratio
          </span>
          <span class="font-mono">
            {{
              typeof hoverInfo.ratio === "number"
                ? hoverInfo.ratio.toFixed(3)
                : "—"
            }}
          </span>
        </div>
        <div class="flex items-center justify-between gap-3">
          <span class="flex items-center gap-2">
            <span
              class="h-2.5 w-2.5 rounded-full"
              style="background-color: #bdc3c7"
            ></span>
            MAGS ETF
          </span>
          <span class="font-mono">
            {{
              typeof hoverInfo.mags === "number"
                ? hoverInfo.mags.toFixed(2)
                : "—"
            }}
          </span>
        </div>
      </div>
    </div>

    <div class="mt-2 flex flex-wrap gap-4 text-xs text-slate-300">
      <div class="flex items-center gap-2">
        <span
          class="h-2.5 w-2.5 rounded-full"
          style="background-color: #f04949"
        ></span>
        <span>SPY/RSP Ratio (Left Axis)</span>
      </div>
      <div class="flex items-center gap-2">
        <span
          class="h-2.5 w-2.5 rounded-full"
          style="background-color: #bdc3c7"
        ></span>
        <span>MAGS ETF Price (Right Axis)</span>
      </div>
      <div class="flex items-center gap-2">
        <span class="h-0.5 w-4 bg-white"></span>
        <span>Threshold (3.5)</span>
      </div>
    </div>

    <FullscreenModal
      :open="showFullscreen"
      title="SPY/RSP Ratio"
      @close="showFullscreen = false"
    >
      <div class="flex flex-col gap-4 w-full h-full">
        <div class="relative flex-1 min-h-[420px]">
          <div ref="fullscreenContainerRef" class="absolute inset-0" />
          <div
            v-if="fullscreenHover"
            class="absolute bg-black/85 border border-white/20 rounded px-4 py-3 text-xs text-white pointer-events-none z-50 max-w-[260px] shadow-lg space-y-2"
            :style="
              tooltipStyle(
                fullscreenHover.position,
                fullscreenContainerRef ?? null,
                260,
              )
            "
          >
            <div class="text-sm font-semibold">{{ fullscreenHover.time }}</div>
            <div class="flex items-center justify-between gap-3">
              <span class="flex items-center gap-2">
                <span
                  class="h-2.5 w-2.5 rounded-full"
                  style="background-color: #f04949"
                ></span>
                SPY/RSP Ratio
              </span>
              <span class="font-mono">
                {{
                  typeof fullscreenHover.ratio === "number"
                    ? fullscreenHover.ratio.toFixed(3)
                    : "—"
                }}
              </span>
            </div>
            <div class="flex items-center justify-between gap-3">
              <span class="flex items-center gap-2">
                <span
                  class="h-2.5 w-2.5 rounded-full"
                  style="background-color: #bdc3c7"
                ></span>
                MAGS ETF
              </span>
              <span class="font-mono">
                {{
                  typeof fullscreenHover.mags === "number"
                    ? fullscreenHover.mags.toFixed(2)
                    : "—"
                }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </FullscreenModal>
  </div>
</template>
