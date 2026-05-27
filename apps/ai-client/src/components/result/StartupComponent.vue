<!-- StartupComponent.vue -->
<script setup lang="ts">
import { computed, defineProps } from 'vue';

const props = defineProps<{
  title: string,
  keyEvents: string[],
  collectionName: string,
  selectedModel: string,
  relevanceScoreThreshold: number | string,
}>();

const modelLabels: Record<string, string> = {
  qwen3_14b: 'Qwen 3 14B',
  deepseek_r1_14b: 'DeepSeek R1 14B',
  qwen3_8b: 'Qwen 3 8B',
  gpt_oss: 'Qwen 3 14B',
};

const selectedModelLabel = computed(
  () => modelLabels[props.selectedModel] ?? props.selectedModel ?? 'Model not set'
);
</script>

<template>
  <div class="overflow-hidden bg-white shadow-sm ring-1 ring-gray-900/5 sm:rounded-lg">
    <div class="px-4 py-6 sm:px-6">
      <h3 class="text-base font-semibold text-gray-900">CRE Session Input</h3>
      <p class="mt-1 max-w-2xl text-sm text-gray-500">The provided input for this CRE session.</p>
    </div>
    <div class="border-t border-gray-100">
      <dl class="divide-y divide-gray-100">
        <!-- Title -->
        <div class="px-4 py-6 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
          <dt class="text-sm font-medium text-gray-900">Title</dt>
          <dd class="mt-1 text-sm text-gray-700 sm:col-span-2 sm:mt-0">{{ title }}</dd>
        </div>
        <!-- Key Events -->
        <div class="px-4 py-6 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
          <dt class="text-sm font-medium text-gray-900">Key Events</dt>
          <dd class="mt-1 text-sm text-gray-700 sm:col-span-2 sm:mt-0">
            <ul>
              <li v-for="(event, index) in keyEvents" :key="index">{{ event }}</li>
            </ul>
          </dd>
        </div>
        <!-- Collection Name -->
        <div class="px-4 py-6 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
          <dt class="text-sm font-medium text-gray-900">Collection Name</dt>
          <dd class="mt-1 text-sm text-gray-700 sm:col-span-2 sm:mt-0">{{ collectionName }}</dd>
        </div>
        <!-- Selected Model -->
        <div class="px-4 py-6 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
          <dt class="text-sm font-medium text-gray-900">Selected Model</dt>
          <dd class="mt-1 text-sm text-gray-700 sm:col-span-2 sm:mt-0">{{ selectedModelLabel }}</dd>
        </div>
        <!-- Relevance Score Threshold -->
        <div class="px-4 py-6 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
          <dt class="text-sm font-medium text-gray-900">Relevance Score Threshold</dt>
          <dd class="mt-1 text-sm text-gray-700 sm:col-span-2 sm:mt-0">{{ relevanceScoreThreshold || 'Threshold not set' }}%</dd>
        </div>
      </dl>
    </div>
  </div>
</template>

<style scoped>
/* Additional styling if needed */
</style>
