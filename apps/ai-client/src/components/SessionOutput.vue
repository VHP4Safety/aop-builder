<script setup lang="ts">
import { withDefaults, defineProps } from 'vue';

interface SessionStat {
  name: string;
  initials: string;
  suffix: string;
  href: string;
  amount: number;
  bgColor: string;
}

const props = withDefaults(defineProps<{
  sessionStats: SessionStat[];
}>(), {
  sessionStats: () => [
    { name: 'PDF Documents', initials: 'PDF', suffix: 'analyzed', href: '#', amount: 50, bgColor: 'bg-pink-600' },
    { name: 'Chunks Selected', initials: 'ENT', suffix: 'selected', href: '#', amount: 12, bgColor: 'bg-purple-600' },
    { name: 'Connections', initials: 'COR', suffix: 'identified', href: '#', amount: 16, bgColor: 'bg-yellow-500' },
    { name: 'Duration', initials: 'TIME', suffix: 'minutes', href: '#', amount: 8, bgColor: 'bg-green-500' },
  ],
});
</script>

<template>
  <div class="mb-5">
    <ul role="list" class="mt-3 grid grid-cols-1 gap-5 sm:grid-cols-2 sm:gap-6 lg:grid-cols-4">
      <li v-for="stat in props.sessionStats" :key="stat.name" class="col-span-1 flex rounded-md shadow-sm">
        <div :class="[stat.bgColor, 'flex w-16 shrink-0 items-center justify-center rounded-l-md text-sm font-medium text-white']">
          {{ stat.initials }}
        </div>
        <div class="flex flex-1 items-center justify-between truncate rounded-r-md border border-gray-200 bg-white">
          <div class="flex-1 truncate px-4 py-2 text-sm">
            <a :href="stat.href" class="font-medium text-gray-900 hover:text-gray-600">
              {{ stat.name }}
            </a>
            <p class="text-gray-500">{{ stat.amount }} {{ stat.suffix }}</p>
          </div>
        </div>
      </li>
    </ul>
  </div>
</template>

<style scoped>
/* Additional styling if needed */
</style>
