<script setup lang="ts">
import { ref, onMounted, onUnmounted, inject } from "vue";
import EmptyLibraryComponent from "../components/EmptyLibraryComponent.vue";
import {Collection} from "../models/Collection.ts";
import {CollectionService} from "../service/CollectionService.ts";

const collectionService = inject<CollectionService>("collectionService");
if (!collectionService) {
  throw new Error("collectionService not provided");
}

const collections = ref<Collection[]>([]);
const scanningCollectionIds = ref<number[]>([]);
let pollingInterval: number | null = null;

// 🔹 Fetch collections from API
const fetchCollections = async () => {
  try {
    collections.value = await collectionService.getCollections();

    // 🔹 Controleer of er collecties zijn die in verwerking zijn bij een pagina-refresh
    const activeScanning = collections.value.some(c => c.status !== "unscanned" && c.status !== "scanned");

    if (activeScanning) {
      startPolling();
    }
  } catch (error) {
    console.error("Error fetching collections:", error);
  }
};

// 🔹 Scan a collection and start polling for updates
const scanCollection = async (collectionId: number) => {
  try {
    scanningCollectionIds.value.push(collectionId);
    await collectionService.scanCollection(collectionId);
    startPolling(); // Start polling na het starten van een scan
  } catch (error) {
    console.error(`Error scanning collection ${collectionId}:`, error);
  }
};

// 🔹 Start polling om de status van collecties bij te werken
const startPolling = () => {
  if (!pollingInterval) {
    pollingInterval = window.setInterval(async () => {
      await fetchCollections();

      // 🔸 Blijf collecties tracken die nog niet "scanned" zijn
      scanningCollectionIds.value = collections.value
          .filter((c) => c.status !== "unscanned" && c.status !== "scanned")
          .map((c) => c.id)

      // 🔹 Stop polling als alle collecties "scanned" zijn
      if (scanningCollectionIds.value.length === 0) {
        stopPolling();
      }
    }, 5000);
  }
};

// 🔹 Stop polling function
const stopPolling = () => {
  if (pollingInterval) {
    clearInterval(pollingInterval);
    pollingInterval = null;
  }
};

// Fetch collections on mount
onMounted(fetchCollections);
onUnmounted(stopPolling);
</script>

<template>
  <EmptyLibraryComponent v-if="collections.length === 0" />
  <div v-else class="bg-white shadow-sm ring-1 ring-gray-900/5 sm:rounded-xl">
    <div class="px-4 py-6 sm:p-8">
      <!-- Info Block -->
      <div class="mb-6 p-4 bg-blue-100 border border-blue-300 rounded-md">
        <h2 class="text-lg font-semibold text-blue-900">Collection Scanning Process</h2>
        <p class="mt-1 text-sm text-blue-800">
          Each collection must be scanned before it can be used. Click the "Scan" button to start.
          The collection will go through preprocessing, chunking, and then be ready for analysis.
        </p>
      </div>

      <div class="sm:flex sm:items-center">
        <div class="sm:flex-auto">
          <h1 class="text-base font-semibold text-gray-900">Collections</h1>
          <p class="mt-2 text-sm text-gray-700">
            A list of collections that you have created in your library.
          </p>
        </div>
        <div class="mt-4 sm:ml-16 sm:mt-0 sm:flex-none">
          <router-link
              :to="{ name: 'CreateLibrary' }"
              class="block rounded-md bg-indigo-600 px-3 py-2 text-center text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible-outline-2 focus-visible-outline-offset-2 focus-visible-outline-indigo-600"
          >
            New collection
          </router-link>
        </div>
      </div>

      <div class="mt-8 flow-root">
        <div class="-mx-4 -my-2 overflow-x-auto sm:-mx-6 lg:-mx-8">
          <div class="inline-block min-w-full py-2 align-middle sm:px-6 lg:px-8">
            <div class="overflow-hidden shadow ring-1 ring-black/5 sm:rounded-lg">
              <table class="min-w-full divide-y divide-gray-300">
                <thead class="bg-gray-50">
                <tr>
                  <th class="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 sm:pl-6">
                    Title
                  </th>
                  <th class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                    Description
                  </th>
                  <th class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                    Number of documents
                  </th>
                  <th class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                    Status
                  </th>
                  <th class="relative py-3.5 pl-3 pr-4 sm:pr-6">
                    <span class="sr-only">Actions</span>
                  </th>
                </tr>
                </thead>
                <tbody class="divide-y divide-gray-200 bg-white">
                <tr v-for="collection in collections" :key="collection.id">
                  <td class="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6">
                    {{ collection.name }}
                  </td>
                  <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                    {{ collection.description }}
                  </td>
                  <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                    {{ collection.pdf_ids ? collection.pdf_ids.length : 0 }}
                  </td>
                  <td class="whitespace-nowrap px-3 py-4 text-sm font-medium flex items-center">
                      <span
                          class="px-2 py-1 rounded text-xs font-semibold flex items-center"
                          :class="{
                          'bg-red-100 text-red-800': collection.status === 'unscanned',
                          'bg-blue-100 text-blue-800': collection.status === 'pre_processing' || collection.status === 'queued_preprocessing',
                          'bg-purple-100 text-purple-800': collection.status === 'chunking',
                          'bg-green-100 text-green-800': collection.status === 'scanned',
                        }"
                      >
                        <!-- 🔹 Toon de spinner ALLEEN bij 'pre_processing' of 'chunking' -->
                        <svg v-if="collection.status === 'pre_processing' || collection.status === 'chunking'"
                             class="animate-spin h-4 w-4 mr-1 text-gray-600"
                             viewBox="0 0 24 24"
                             fill="none"
                             xmlns="http://www.w3.org/2000/svg">
                          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                        </svg>
                        <!-- ✅ Toon checkmark als de collectie gescand is -->
                        <svg v-if="collection.status === 'scanned'" class="h-4 w-4 mr-1 text-green-800" fill="none"
                             stroke="currentColor"
                             stroke-width="2"
                             viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"></path>
                        </svg>
                        {{ collection.status.replace("_", " ") }}
                      </span>
                  </td>
                  <td class="relative whitespace-nowrap py-4 pl-3 pr-4 text-right text-sm font-medium sm:pr-6">
                    <button
                        v-if="collection.status === 'unscanned'"
                        @click="scanCollection(collection.id)"
                        :disabled="scanningCollectionIds.includes(collection.id)"
                        class="rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 flex items-center"
                    >
                      <svg
                          v-if="scanningCollectionIds.includes(collection.id)"
                          class="animate-spin h-4 w-4 mr-2 text-white"
                          viewBox="0 0 24 24"
                          fill="none"
                          xmlns="http://www.w3.org/2000/svg"
                      >
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                      </svg>
                      Scan
                    </button>
                  </td>
                </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

