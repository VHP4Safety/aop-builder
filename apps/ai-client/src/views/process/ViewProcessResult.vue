<script setup lang="ts">
import { ref, computed, inject, onMounted, onUnmounted, watch, provide } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import SessionOutput from "../../components/SessionOutput.vue";
import { ChevronDownIcon } from '@heroicons/vue/16/solid';
import {SessionService} from "../../service/SessionService.ts";
import {SessionWithResultResponse} from "../../models/Result.ts";

const sessionService = inject<SessionService>("sessionService");

if (!sessionService) {
  throw new Error("sessionService not provided");
}

const route = useRoute();
const router = useRouter();

const sessionData = ref<SessionWithResultResponse | null>(null);
const documentReferences = ref<Array<{
  name: string;
  title: string;
  authors: string | null;
  doi: string | null;
  year: number | null;
  subject: string | null;
  filename: string | null;
  uploadDate: string | null;
  pageCount: number | null;
  selectedChunkCount: number;
  chunkIds: string[];
  chunkTexts: string[];
}>>([]);
const mySessionStats = ref([
  { name: 'PDF Documents', initials: 'PDF', suffix: 'analyzed', href: '#', amount: 0, bgColor: 'bg-pink-600' },
  { name: 'Chunks Selected', initials: 'ENT', suffix: 'selected', href: '#', amount: 0, bgColor: 'bg-purple-600' },
  { name: 'Connections', initials: 'COR', suffix: 'identified', href: '#', amount: 0, bgColor: 'bg-yellow-500' },
  { name: 'Duration', initials: 'TIME', suffix: 'minutes', href: '#', amount: 0, bgColor: 'bg-green-500' },
]);

const tabs = [
  { name: 'Startup information', route: 'ProcessStartupInformation', current: false },
  { name: 'Chunks', route: 'ProcessSelectedChunkInformation', current: false },
  { name: 'Raw Extracted Graph', route: 'ProcessVisualInformation', current: false },
  { name: 'Enriched AOP Graph', route: 'ProcessEnrichedGraphInformation', current: false }
];

let pollingInterval: ReturnType<typeof setInterval> | null = null;

const computedTabs = computed(() =>
    tabs.map(tab => ({
      ...tab,
      current: tab.route === route.name
    }))
);

// **Functie om sessiegegevens op te halen**
const fetchSessionData = async () => {
  const sessionId = Number(route.params.id);
  if (!sessionId) {
    router.push({ name: 'Home' });
    return;
  }

  try {
    const data = await sessionService.getSessionWithResult(sessionId);

    if (!['enriching', 'finished'].includes(data.session.status)) {
      router.push({ name: 'Home' });
      return;
    }

    sessionData.value = data;

    // **Berekent statistieken**
    const pdfDocuments = data.selected_chunks.length;
    const totalChunks = data.selected_chunks.reduce((acc, doc) => acc + doc.chunks.length, 0);
    const totalConnections = data.extracted_causal_relations.reduce(
        (acc, doc) => acc + (doc.output.relationships ? doc.output.relationships.length : 0),
        0
    );
    const standardizedEdges = data.enriched_graph?.summary?.standardized_edges ?? 0;

    documentReferences.value = data.selected_chunks.map((doc) => ({
      name: doc.name,
      title: doc.reference?.title ?? doc.name,
      authors: doc.reference?.authors ?? null,
      doi: doc.reference?.doi ?? null,
      year: doc.reference?.year ?? null,
      subject: doc.reference?.subject ?? null,
      filename: doc.reference?.filename ?? doc.name,
      uploadDate: doc.reference?.upload_date ?? null,
      pageCount: doc.reference?.page_count ?? null,
      selectedChunkCount: doc.chunks.length,
      chunkIds: doc.chunks.map((chunk) => chunk.id),
      chunkTexts: doc.chunks.map((chunk) => chunk.text),
    }));

    mySessionStats.value = [
      { name: 'PDF Documents', initials: 'PDF', suffix: 'analyzed', href: '#', amount: pdfDocuments, bgColor: 'bg-pink-600' },
      { name: 'Chunks Selected', initials: 'ENT', suffix: 'selected', href: '#', amount: totalChunks, bgColor: 'bg-purple-600' },
      { name: 'Raw Connections', initials: 'RAW', suffix: 'identified', href: '#', amount: totalConnections, bgColor: 'bg-yellow-500' },
      { name: 'Enriched Edges', initials: 'AOP', suffix: 'standardized', href: '#', amount: standardizedEdges, bgColor: 'bg-green-500' },
    ];
  } catch (error) {
    console.error("Error fetching session data:", error);
    router.push({ name: 'Home' });
  }
};

const startPolling = () => {
  if (pollingInterval) {
    return;
  }

  pollingInterval = setInterval(async () => {
    await fetchSessionData();
    if (sessionData.value?.session.status === 'finished') {
      stopPolling();
    }
  }, 4000);
};

const stopPolling = () => {
  if (pollingInterval) {
    clearInterval(pollingInterval);
    pollingInterval = null;
  }
};

// **Provide sessionData zodat de child-componenten deze krijgen**
provide("sessionData", sessionData);
provide("documentReferences", documentReferences);

// **Ophalen bij het laden**
onMounted(async () => {
  await fetchSessionData();
  if (sessionData.value?.session.status === 'enriching') {
    startPolling();
  }
});

onUnmounted(stopPolling);

// **Zorg dat de data behouden blijft als alleen de child-route verandert**
watch(() => route.name, () => {
  if (!sessionData.value) {
    fetchSessionData();
  }
});

watch(() => sessionData.value?.session.status, (nextStatus) => {
  if (nextStatus === 'enriching') {
    startPolling();
  } else if (nextStatus === 'finished') {
    stopPolling();
  }
});
</script>

<template>
  <div class="mb-5">
    <div class="grid grid-cols-1 sm:hidden">
      <select aria-label="Select a tab" class="col-start-1 row-start-1 w-full appearance-none rounded-md bg-white py-2 pl-3 pr-8 text-base text-gray-900 outline outline-1 -outline-offset-1 outline-gray-300 focus:outline-indigo-600">
        <option v-for="tab in computedTabs" :key="tab.name" :selected="tab.current">{{ tab.name }}</option>
      </select>
      <ChevronDownIcon class="pointer-events-none col-start-1 row-start-1 mr-2 size-5 self-center justify-self-end fill-gray-500" aria-hidden="true" />
    </div>
    <div class="hidden sm:block">
      <nav class="isolate flex divide-x divide-gray-200 rounded-lg shadow" aria-label="Tabs">
        <router-link
            v-for="(tab, tabIdx) in computedTabs"
            :key="tab.name"
            :to="{ name: tab.route }"
            :class="[tab.current ? 'text-gray-900' : 'text-gray-500 hover:text-gray-700', tabIdx === 0 ? 'rounded-l-lg' : '', tabIdx === computedTabs.length - 1 ? 'rounded-r-lg' : '', 'group relative min-w-0 flex-1 overflow-hidden bg-white px-4 py-4 text-center text-sm font-medium hover:bg-gray-50 focus:z-10']"
            :aria-current="tab.current ? 'page' : undefined">
          <span>{{ tab.name }}</span>
          <span aria-hidden="true" :class="[tab.current ? 'bg-indigo-500' : 'bg-transparent', 'absolute inset-x-0 bottom-0 h-0.5']" />
        </router-link>
      </nav>
    </div>
  </div>
  <SessionOutput :sessionStats="mySessionStats" />
  <router-view />
</template>
