<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import * as echarts from 'echarts';

export interface HistogramBar {
  symbol: string;
  value: number;
}

const props = defineProps<{
  title?: string;
  bars: HistogramBar[];
  bare?: boolean;
}>();

const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;

const renderChart = () => {
  if (!chartRef.value) return;
  if (!chart) {
    chart = echarts.init(chartRef.value);
    window.addEventListener('resize', resizeChart);
  }
  const option = {
    grid: { top: 30, left: 20, right: 10, bottom: 40, containLabel: true },
    xAxis: {
      type: 'category',
      data: props.bars.map((bar) => bar.symbol),
      axisLabel: { color: '#f8fafc', fontSize: 12 },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: '{value}%', color: '#f8fafc' },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      valueFormatter: (value: number) => `${value.toFixed(2)}%`,
    },
    series: [
      {
        type: 'bar',
        data: props.bars.map((bar) => ({
          value: bar.value,
          itemStyle: { color: bar.value >= 0 ? '#22c55e' : '#ef4444' },
          label: {
            show: true,
            position: bar.value >= 0 ? 'top' : 'insideBottom',
            formatter: `${bar.value.toFixed(2)}%`,
            fontSize: 11,
            color: '#f8fafc',
            distance: bar.value >= 0 ? 6 : 2,
          },
        })),
      },
    ],
  };
  chart.setOption(option, true);
};

const resizeChart = () => {
  chart?.resize();
};

watch(
  () => props.bars,
  () => {
    if (props.bars.length === 0) return;
    renderChart();
  },
  { deep: true },
);

onMounted(() => {
  if (props.bars.length) {
    renderChart();
  }
});

onBeforeUnmount(() => {
  if (chart) {
    window.removeEventListener('resize', resizeChart);
    chart.dispose();
    chart = null;
  }
});
</script>

<template>
  <div
    :class="
      bare
        ? 'flex flex-col gap-4 h-full'
        : 'bg-panel border border-white/10 rounded-xl p-4 flex flex-col gap-4'
    "
  >
    <div v-if="!bare && title" class="text-lg text-accentCyan font-semibold uppercase">
      {{ title }}
    </div>
    <div ref="chartRef" class="w-full flex-1 min-h-[320px]"></div>
  </div>
</template>
