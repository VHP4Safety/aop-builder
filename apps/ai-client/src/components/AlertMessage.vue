<template>
  <div :class="['mt-4 rounded-md p-4', bgClass]">
    <div class="flex">
      <div class="shrink-0">
        <component
            :is="iconComponent"
            class="h-5 w-5"
            :class="iconColorClass"
            aria-hidden="true"
        />
      </div>
      <div class="ml-3">
        <h3 class="text-sm font-medium" :class="textTitleClass">
          {{ title }}
        </h3>
        <div class="mt-2 text-sm" :class="textColorClass">
          <p>{{ message }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
} from '@heroicons/vue/20/solid';
import { computed, defineProps } from 'vue';

const props = defineProps<{
  type: 'success' | 'warning' | 'error';
  message: string;
}>();

const bgClass = computed(() => ({
  success: 'bg-green-50',
  warning: 'bg-yellow-50',
  error: 'bg-red-50',
}[props.type]));

const textColorClass = computed(() => ({
  success: 'text-green-700',
  warning: 'text-yellow-700',
  error: 'text-red-700',
}[props.type]));

const textTitleClass = computed(() => ({
  success: 'text-green-800',
  warning: 'text-yellow-800',
  error: 'text-red-800',
}[props.type]));

const iconColorClass = computed(() => ({
  success: 'text-green-400',
  warning: 'text-yellow-400',
  error: 'text-red-400',
}[props.type]));

const iconComponent = computed(() => ({
  success: CheckCircleIcon,
  warning: ExclamationTriangleIcon,
  error: XCircleIcon,
}[props.type]));

const title = computed(() => ({
  success: 'Success',
  warning: 'Warning',
  error: 'Error',
}[props.type]));
</script>
