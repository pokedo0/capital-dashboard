<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { fetchLeveragedETFCalculation } from '../services/api';
import type { LeveragedETFItem } from '../types/api';

// State
const underlyingInput = ref('QQQ');
const searchTicker = ref('QQQ');
const targetPriceInput = ref<string>('');
const targetPrice = ref<number | undefined>(undefined);
const isEditing = ref(false);

// Query
const { data, isLoading, error, refetch } = useQuery({
  queryKey: ['leveraged-etf', searchTicker, targetPrice],
  queryFn: () => fetchLeveragedETFCalculation(searchTicker.value, targetPrice.value),
  refetchInterval: 60 * 1000, // Refetch every 1 minute for realtime data
  enabled: computed(() => searchTicker.value.length > 0),
});

// When data loads, set default target price if not set
watch(data, (newData) => {
  if (newData && !isEditing.value && !targetPriceInput.value) {
    targetPriceInput.value = newData.underlying.current_price?.toFixed(2) || '';
  }
});

// All items (underlying + leveraged ETFs)
const allItems = computed<LeveragedETFItem[]>(() => {
  if (!data.value) return [];
  return [data.value.underlying, ...data.value.leveraged_etfs];
});

// Format helpers
const formatPrice = (price: number | null): string => {
  if (price === null || price === undefined) return '-';
  return price.toFixed(2);
};

const formatPercent = (pct: number | null): string => {
  if (pct === null || pct === undefined) return '-';
  const sign = pct >= 0 ? '+' : '';
  return `${sign}${pct.toFixed(2)}%`;
};

const getChangeClass = (pct: number | null): string => {
  if (pct === null || pct === undefined) return '';
  return pct >= 0 ? 'text-green-400' : 'text-red-400';
};

const getDirectionLabel = (item: LeveragedETFItem): string => {
  if (item.direction === 'underlying') return 'Base';
  const dir = item.direction === 'long' ? 'Long' : 'Short';
  return `${item.leverage.toUpperCase()} ${dir}`;
};

const getDirectionClass = (direction: string): string => {
  if (direction === 'underlying') return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
  if (direction === 'long') return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
  return 'bg-rose-500/20 text-rose-300 border-rose-500/30';
};

// Actions
const handleSearch = () => {
  const val = underlyingInput.value.trim().toUpperCase();
  if (!val) return;
  searchTicker.value = val;
  targetPriceInput.value = '';
  targetPrice.value = undefined;
};

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter') {
    handleSearch();
  }
};

const handleTargetPriceChange = () => {
  isEditing.value = false;
  const val = parseFloat(targetPriceInput.value);
  if (!isNaN(val) && val > 0) {
    targetPrice.value = val;
  } else {
    targetPrice.value = undefined;
    targetPriceInput.value = data.value?.underlying.current_price?.toFixed(2) || '';
  }
};

const handleTargetPriceKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter') {
    handleTargetPriceChange();
    (e.target as HTMLInputElement).blur();
  }
};

const handleTargetPriceFocus = () => {
  isEditing.value = true;
};

onMounted(() => {
  handleSearch();
});
</script>

<template>
  <div class="bg-panel border border-white/10 rounded-xl p-4 flex flex-col gap-4 w-full">
    <!-- Header -->
    <div class="flex flex-wrap justify-between items-center gap-4">
      <div class="text-xl font-semibold uppercase" style="color: #67f0d6">
        Leveraged ETF Price Calculator
      </div>
      
      <div class="flex flex-wrap items-center gap-3">
        <!-- Search Input -->
        <div class="flex items-center gap-2 bg-black/20 border border-white/10 rounded px-2 py-1">
          <input
            v-model="underlyingInput"
            type="text"
            placeholder="UNDERLYING"
            class="bg-transparent border-none outline-none text-white w-20 text-xs uppercase placeholder-white/30"
            @keydown="handleKeydown"
          />
          <button
            @click="handleSearch"
            class="text-accentCyan hover:text-white transition-colors"
            title="Search"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>

        <!-- Target Price Input -->
        <div class="flex items-center gap-2 bg-black/20 border border-white/10 rounded px-2 py-1">
          <span class="text-white/50 text-xs">Target:</span>
          <input
            v-model="targetPriceInput"
            type="number"
            step="0.01"
            placeholder="Price"
            class="bg-transparent border-none outline-none text-white w-20 text-xs placeholder-white/30"
            @blur="handleTargetPriceChange"
            @keydown="handleTargetPriceKeydown"
            @focus="handleTargetPriceFocus"
          />
        </div>

        <!-- Refresh Button -->
        <button
          @click="() => refetch()"
          :disabled="isLoading"
          class="text-accentCyan hover:text-white transition-colors disabled:opacity-50"
          title="Refresh"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" :class="{ 'animate-spin': isLoading }" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Current Symbol Info -->
    <div v-if="data" class="flex items-center gap-3 text-sm">
      <span class="text-white/70">Showing leveraged ETFs for:</span>
      <span class="font-bold text-accentCyan">{{ searchTicker }}</span>
      <span class="text-white/50">|</span>
      <span class="text-white/70">Current:</span>
      <span class="font-mono text-white">${{ formatPrice(data.underlying.current_price) }}</span>
      <span :class="getChangeClass(data.underlying.current_change_pct)" class="font-mono">
        {{ formatPercent(data.underlying.current_change_pct) }}
      </span>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading && !data" class="flex items-center justify-center py-8">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-accentCyan"></div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="text-red-400 text-center py-8">
      <p>Failed to load data: {{ (error as Error).message }}</p>
      <button @click="() => refetch()" class="mt-2 text-accentCyan hover:text-white underline">
        Retry
      </button>
    </div>

    <!-- Data Table -->
    <div v-else-if="data" class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-white/10 text-white/50 text-left">
            <th class="py-2 px-2 font-medium">Ticker</th>
            <th class="py-2 px-2 font-medium">Name</th>
            <th class="py-2 px-2 font-medium text-center">Type</th>
            <th class="py-2 px-2 font-medium text-right">Current Price</th>
            <th class="py-2 px-2 font-medium text-right">Current Change</th>
            <th class="py-2 px-2 font-medium text-right">YTD Return</th>
            <th class="py-2 px-2 font-medium text-right">Target Price</th>
            <th class="py-2 px-2 font-medium text-right">Target Change</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="item in allItems"
            :key="item.ticker"
            class="border-b border-white/5 hover:bg-white/5 transition-colors"
            :class="item.direction === 'underlying' ? 'bg-blue-500/5' : ''"
          >
            <td class="py-2.5 px-2 font-mono font-bold text-white">{{ item.ticker }}</td>
            <td class="py-2.5 px-2 text-white/70 max-w-[200px] truncate" :title="item.name">
              {{ item.name }}
            </td>
            <td class="py-2.5 px-2 text-center">
              <span
                class="inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase border"
                :class="getDirectionClass(item.direction)"
              >
                {{ getDirectionLabel(item) }}
              </span>
            </td>
            <td class="py-2.5 px-2 text-right font-mono text-white">
              ${{ formatPrice(item.current_price) }}
            </td>
            <td class="py-2.5 px-2 text-right font-mono" :class="getChangeClass(item.current_change_pct)">
              {{ formatPercent(item.current_change_pct) }}
            </td>
            <td class="py-2.5 px-2 text-right font-mono" :class="getChangeClass(item.ytd_return)">
              {{ formatPercent(item.ytd_return) }}
            </td>
            <td class="py-2.5 px-2 text-right font-mono text-amber-300">
              ${{ formatPrice(item.target_price) }}
            </td>
            <td class="py-2.5 px-2 text-right font-mono" :class="getChangeClass(item.target_change_pct)">
              {{ formatPercent(item.target_change_pct) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- No Data State -->
    <div v-else class="text-white/50 text-center py-8">
      Enter an underlying ticker to search for leveraged ETFs.
    </div>

    <!-- Footer Note -->
    <div class="text-white/30 text-xs mt-2">
      * Prices are realtime. Target calculations assume daily leverage reset mechanism.
      Data refreshes every minute.
    </div>
  </div>
</template>
