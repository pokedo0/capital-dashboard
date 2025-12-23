<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import * as echarts from 'echarts';
import { useQuery } from '@tanstack/vue-query';
import { fetchRelativePerformance } from '../services/api';

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

const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;

const { data } = useQuery({
  queryKey: computed(() => ['relative', 'custom-group', props.symbols.join(','), props.range]),
  queryFn: () => {
    if (!props.symbols.length) return Promise.resolve([]);
    return fetchRelativePerformance(props.symbols, props.range);
  },
  enabled: computed(() => props.symbols.length > 0),
});

const seriesData = computed(() => {
  if (!data.value) return [];
  
  // Calculate cutoff for YTD
  const cutoff = new Date(new Date().getFullYear(), 0, 1);
  
  return data.value
    .map((series) => {
      let points = series.points;
      if (props.range === 'YTD') {
        points = points.filter((point) => new Date(point.time) >= cutoff);
      } else if (props.range === '5Y' || props.range === '3Y') {
        points = downsampleWeekly(points);
      }
      
      if (!points.length) return null;
      
      const first = points[0];
      const last = points[points.length - 1];
      if (!first || !last || typeof first.value !== 'number' || typeof last.value !== 'number') {
        return null;
      }
      
      // Check if symbol is still in props (might be deleted rapidly)
      if (!props.symbols.includes(series.symbol)) return null;

      // Filter out hidden symbols
      if (props.hiddenSymbols?.has(series.symbol)) return null;

      const change = last.value - first.value;
      return { symbol: series.symbol, change };
    })
    .filter((item): item is { symbol: string; change: number } => !!item)
    .sort((a, b) => b.change - a.change);
});

const renderChart = () => {
  if (!chartRef.value) return;
  if (!chart) {
    chart = echarts.init(chartRef.value);
    const resizeChart = () => chart?.resize();
    window.addEventListener('resize', resizeChart);
  }
  
  const payload = seriesData.value;
  const isMobile = window.innerWidth < 768;
  
  const option = {
    grid: {
      left: 10,
      right: 10,
      top: 30,
      bottom: 20,
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: payload.map((item) => item.symbol),
      axisLabel: { color: '#f8fafc', margin: 10, interval: 0, fontSize: 10 },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
      axisLabel: { color: '#94a3b8', formatter: '{value}%', fontSize: 10 },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(0,0,0,0.8)',
      borderColor: 'rgba(255,255,255,0.2)',
      textStyle: { color: '#fff' },
      formatter: (params: any) => {
        const item = params[0];
        if (!item) return '';
        return `${item.name}: <span style="color:${item.color}">${item.value.toFixed(2)}%</span>`;
      },
    },
    series: [
      {
        type: 'bar',
        data: payload.map((item) => {
          return {
            value: item.change,
            itemStyle: {
              color: item.change >= 0 ? '#22c55e' : '#ef4444',
            },
            label: {
              show: true,
              position: item.change >= 0 ? 'top' : 'insideBottom',
              formatter: `${item.change.toFixed(2)}%`,
              color: '#f8fafc',
              fontSize: 10,
              distance: 4,
            },
          };
        }),
      },
    ],
  };
  chart.setOption(option, true);
};

watch(
  [seriesData, () => props.colors, () => props.symbols],
  () => {
    // Small delay to allow container resize if needed
    setTimeout(() => renderChart(), 0);
  },
  { deep: true }
);

onBeforeUnmount(() => {
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div class="h-full w-full flex flex-col">
    <div ref="chartRef" class="w-full flex-1 aspect-[4/3] md:aspect-auto md:min-h-[360px]"></div>
  </div>
</template>
