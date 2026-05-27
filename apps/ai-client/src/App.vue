<script setup lang="ts">
import {onMounted} from "vue";

const addHtmlBodyClasses = (): void => {
  document.documentElement.classList.add('h-full', 'bg-gray-50');
  document.body.classList.add('h-full');
};

onMounted((): void => {
  addHtmlBodyClasses();
});
</script>

<template>
  <router-view />
</template>

<style scoped>
</style>
