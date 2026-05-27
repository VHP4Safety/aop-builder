<script setup lang="ts">
import { ref, onMounted, onUnmounted, inject, computed } from 'vue';
import StartupComponent from "../../components/result/StartupComponent.vue";
import { useRouter, useRoute } from 'vue-router';
import {SessionService} from "../../service/SessionService.ts";
import {Session} from "../../models/Result.ts";
import {
  ArrowRightStartOnRectangleIcon,
  CheckIcon,
  ClockIcon,
  DocumentArrowDownIcon,
  DocumentDuplicateIcon,
  XCircleIcon
} from "@heroicons/vue/20/solid";

const router = useRouter();
const route = useRoute();
const sessionService = inject<SessionService>("sessionService");

if (!sessionService) {
  throw new Error("sessionService not provided");
}

const session = ref<Session | null>(null);
const isLoading = ref(true);
const isRefreshing = ref(false);
let pollingInterval: ReturnType<typeof setInterval> | null = null;
const statusLabels: Record<string, string> = {
  queued: 'queued',
  starting: 'preparing chunks',
  chunking: 'ready for chunk selection',
  waiting: 'queued for extraction',
  extracting: 'extracting relations',
  enriching: 'enriching and standardizing graph',
  finished: 'finished',
  canceled: 'canceled',
};

// **Haal de sessiegegevens op en blijf checken tot status 'finished' is**
const fetchSession = async () => {
  const sessionId = Number(route.params.id);
  if (!sessionId) {
    console.error("❌ Ongeldig sessie-ID.");
    return;
  }

  const isInitialLoad = session.value === null;

  try {
    if (isInitialLoad) {
      isLoading.value = true;
    } else {
      isRefreshing.value = true;
    }

    session.value = await sessionService.getSession(sessionId);

    // **Als de sessie klaar is, stop polling en navigeer**
    if (session.value && ["enriching", "finished"].includes(session.value.status)) {
      stopPolling();
      router.push({ name: 'ProcessStartupInformation' });
    }
  } catch (error) {
    console.error("❌ Fout bij ophalen sessie:", error);
  } finally {
    isLoading.value = false;
    isRefreshing.value = false;
  }
};

// **Start polling om status te controleren**
const startPolling = () => {
  if (pollingInterval) return; // Voorkom dubbele intervals

  pollingInterval = setInterval(() => {
    fetchSession();
  }, 3000); // **Elke 3 seconden ophalen**
};

// **Stop polling zodra de sessie 'finished' is**
const stopPolling = () => {
  if (pollingInterval) {
    clearInterval(pollingInterval);
    pollingInterval = null;
  }
};

// **Bij mount: Haal sessie op en start polling**
onMounted(() => {
  fetchSession();
  startPolling();
});

// **Stop polling bij unmount om memory leaks te voorkomen**
onUnmounted(stopPolling);

// **Statusmapping voor progressie**
const progressMapping: Record<string, number> = {
  queued: 0,
  starting: 33,
  chunking: 66,
  extracting: 80,
  enriching: 92,
  finished: 100,
  canceled: 0,
};

// **Compute waardes uit session om in de UI te gebruiken**
const inputTitle = computed(() => session.value?.title ?? "N/A");
const inputKeyEvents = computed(() => session.value?.key_events ?? []);
const inputCollectionName = computed(() => `Collection ${session.value?.collection_id ?? "N/A"}`);
const inputSelectedModel = computed(() => session.value?.model_name ?? "N/A");
const inputRelevanceScoreThreshold = computed(() => session.value?.relevance_score_threshold ?? 100);
const status = computed(() => session.value?.status ?? "queued");
const telemetry = computed(() => session.value?.telemetry ?? null);
const progress = computed(() => {
  if (status.value === "extracting" && telemetry.value?.total_chunks) {
    const extractionFraction = Math.min(1, telemetry.value.processed_chunks / telemetry.value.total_chunks);
    return Math.min(99, Math.round(66 + (34 * extractionFraction)));
  }

  return progressMapping[status.value] ?? 0;
});
const latestLog = computed(() => {
  const logs = session.value?.logs ?? [];
  return logs.length > 0 ? logs[logs.length - 1] : null;
});

const elapsedRuntime = computed(() => {
  if (!session.value?.created_at) {
    return "0m";
  }

  const created = new Date(session.value.created_at).getTime();
  const now = Date.now();
  const totalSeconds = Math.max(0, Math.floor((now - created) / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }

  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }

  return `${seconds}s`;
});

const phaseDetails: Record<string, { title: string; description: string; detail: string }> = {
  queued: {
    title: "Queued",
    description: "The run has been created and is waiting for background workers to pick it up.",
    detail: "No model work is happening yet. The queue will advance automatically."
  },
  starting: {
    title: "Preparing chunks",
    description: "The system is collecting the relevant text slices for this run.",
    detail: "This phase prepares the material that you or the extractor will use next."
  },
  chunking: {
    title: "Ready for chunk selection",
    description: "Relevant chunks have been prepared and are ready for your review.",
    detail: "Use the review step to confirm which chunks should be used for extraction."
  },
  waiting: {
    title: "Queued for extraction",
    description: "Your selected chunks were submitted successfully and are waiting for the extractor.",
    detail: "The extraction worker has not started model calls yet, but the run is in line."
  },
  extracting: {
    title: "Extracting relations",
    description: "The extractor is actively sending chunks to the language model and parsing causal relations.",
    detail: "This can take a while for larger selections because each chunk is processed individually."
  },
  enriching: {
    title: "Enriching graph",
    description: "Raw extracted relations are available and the app is now standardizing entities with ontology and AOP context.",
    detail: "The raw graph can already be inspected while ontology matching and AOP-Wiki linking continue in the background."
  },
  finished: {
    title: "Finished",
    description: "Extraction and enrichment completed and the result view is ready.",
    detail: "You can inspect the raw extraction, the standardized AOP graph, and supporting evidence."
  },
  canceled: {
    title: "Canceled",
    description: "The run stopped before completion.",
    detail: "This usually indicates a worker, connectivity, or model-service problem."
  },
};

const currentPhaseDetail = computed(() => {
  return phaseDetails[status.value] ?? {
    title: status.value,
    description: "The session is in an unknown state.",
    detail: "Check the logs or backend services for more information."
  };
});

const telemetrySummary = computed(() => {
  if (!telemetry.value?.total_chunks) {
    return null;
  }

  return {
    totalChunks: telemetry.value.total_chunks,
    processedChunks: telemetry.value.processed_chunks,
    successfulChunks: telemetry.value.successful_chunks,
    failedChunks: telemetry.value.failed_chunks,
    totalRelationships: telemetry.value.total_relationships,
    percentComplete: telemetry.value.percent_complete,
    lastChunkId: telemetry.value.last_chunk_id,
    lastMessage: telemetry.value.last_message,
    lastError: telemetry.value.last_error,
    updatedAt: telemetry.value.updated_at,
  };
});

const consoleMessages = computed(() => {
  const lines: Array<{ id: string; timestamp: string; message: string; kind: 'info' | 'success' | 'warning' | 'error' }> = [];
  const createdAt = session.value?.created_at;

  if (createdAt) {
    lines.push({
      id: `created-${createdAt}`,
      timestamp: createdAt,
      message: "Session created and added to the workflow queue.",
      kind: 'info',
    });
  }

  (session.value?.logs ?? []).forEach((log, index) => {
    const statusKey = log.status as string;
    const label = statusLabels[statusKey] ?? log.status;
    const messageMap: Record<string, string> = {
      queued: "Waiting for a worker to pick up the run.",
      starting: "Preparing relevant chunks from the selected collection.",
      chunking: "Chunk preparation finished. The run is ready for manual chunk review.",
      waiting: "Selected chunks were submitted and queued for extraction.",
      extracting: "Language model extraction is running on the selected chunks.",
      enriching: "Raw extraction finished. Ontology and AOP enrichment is now running.",
      finished: "Extraction and enrichment finished successfully. Results are now available.",
      canceled: "The run stopped before completion and needs attention.",
    };

    const kindMap: Record<string, 'info' | 'success' | 'warning' | 'error'> = {
      queued: 'info',
      starting: 'info',
      chunking: 'success',
      waiting: 'warning',
      extracting: 'warning',
      enriching: 'warning',
      finished: 'success',
      canceled: 'error',
    };

    lines.push({
      id: `${log.id}-${index}`,
      timestamp: log.timestamp,
      message: `${label}: ${messageMap[statusKey] ?? 'Status updated.'}`,
      kind: kindMap[statusKey] ?? 'info',
    });
  });

  if (status.value === 'extracting') {
    lines.push({
      id: 'extracting-hint',
      timestamp: latestLog.value?.timestamp ?? new Date().toISOString(),
      message: "The progress bar represents the current phase only. Extraction can stay at this phase for a while because chunks are processed one by one.",
      kind: 'warning',
    });
  }

  if (telemetrySummary.value) {
    lines.push({
      id: 'telemetry-progress',
      timestamp: telemetrySummary.value.updatedAt ?? new Date().toISOString(),
      message: `Telemetry: processed ${telemetrySummary.value.processedChunks} / ${telemetrySummary.value.totalChunks} chunks, ${telemetrySummary.value.successfulChunks} successful, ${telemetrySummary.value.failedChunks} failed, ${telemetrySummary.value.totalRelationships} relationships found so far.`,
      kind: telemetrySummary.value.failedChunks > 0 ? 'warning' : 'info',
    });

    if (telemetrySummary.value.lastChunkId) {
      lines.push({
        id: 'telemetry-last-chunk',
        timestamp: telemetrySummary.value.updatedAt ?? new Date().toISOString(),
        message: `Last processed chunk: ${telemetrySummary.value.lastChunkId}.`,
        kind: 'info',
      });
    }

    if (telemetrySummary.value.lastMessage) {
      lines.push({
        id: 'telemetry-last-message',
        timestamp: telemetrySummary.value.updatedAt ?? new Date().toISOString(),
        message: telemetrySummary.value.lastMessage,
        kind: telemetrySummary.value.lastError ? 'warning' : 'info',
      });
    }

    if (telemetrySummary.value.lastError) {
      lines.push({
        id: 'telemetry-last-error',
        timestamp: telemetrySummary.value.updatedAt ?? new Date().toISOString(),
        message: `Last backend error: ${telemetrySummary.value.lastError}`,
        kind: 'error',
      });
    }
  }

  if (status.value === 'waiting') {
    lines.push({
      id: 'waiting-hint',
      timestamp: latestLog.value?.timestamp ?? new Date().toISOString(),
      message: "The extractor has not started model calls yet. The run is waiting for the extraction worker to pick it up.",
      kind: 'info',
    });
  }

  if (status.value === 'enriching') {
    lines.push({
      id: 'enriching-hint',
      timestamp: latestLog.value?.timestamp ?? new Date().toISOString(),
      message: "The raw graph is ready. The enrichment worker is now standardizing entities through ontology lookup and optional AOP references.",
      kind: 'info',
    });
  }

  if (status.value === 'canceled') {
    lines.push({
      id: 'canceled-hint',
      timestamp: latestLog.value?.timestamp ?? new Date().toISOString(),
      message: "A canceled run usually means a worker or model-service issue interrupted execution. Starting a fresh run is often the fastest recovery path.",
      kind: 'error',
    });
  }

  return lines.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
});

const consoleLineClasses: Record<string, string> = {
  info: 'text-slate-200',
  success: 'text-emerald-300',
  warning: 'text-amber-300',
  error: 'text-rose-300',
};

// **Navigatie op basis van status**
const navigateBasedOnStatus = () => {
  if (status.value === "chunking") {
    router.push({ name: 'ViewProcessChunkingSelection' });
  } else if (["enriching", "finished"].includes(status.value)) {
    router.push({ name: 'ProcessStartupInformation' });
  }
};

const statusIcons: Record<string, any> = {
  queued: ClockIcon,
  starting: ArrowRightStartOnRectangleIcon,
  chunking: DocumentDuplicateIcon,
  waiting: DocumentArrowDownIcon,
  extracting: DocumentArrowDownIcon,
  enriching: DocumentArrowDownIcon,
  finished: CheckIcon,
  canceled: XCircleIcon,
};

const statusIconColors: Record<string, string> = {
  queued: 'bg-gray-400',
  starting: 'bg-blue-400',
  chunking: 'bg-blue-500',
  waiting: 'bg-yellow-500',
  extracting: 'bg-yellow-500',
  enriching: 'bg-amber-500',
  finished: 'bg-green-500',
  canceled: 'bg-red-400',
};

const statusTimeline = computed(() => {
  return (session.value?.logs ?? []).map((log, index) => {
    const statusKey = log.status as string;
    return {
      id: index,
      content: 'Status update:',
      target: statusLabels[statusKey] ?? log.status,
      href: '#',
      date: new Date(log.timestamp).toLocaleDateString(),
      datetime: new Date(log.timestamp).toISOString(),
      icon: statusIcons[statusKey] ?? ClockIcon,
      iconBackground: statusIconColors[statusKey] ?? 'bg-gray-400',
    };
  });
});
</script>

<template>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-8 items-start">
    <div v-if="isLoading" class="text-center text-gray-500 text-lg">Loading session data...</div>

    <template v-else>
      <!-- Left Card: Startup Information -->
      <StartupComponent
          :title="inputTitle"
          :keyEvents="inputKeyEvents"
          :collectionName="inputCollectionName"
          :selectedModel="inputSelectedModel"
          :relevanceScoreThreshold="inputRelevanceScoreThreshold"
      />

      <!-- Right Card: Process Status -->
      <div class="bg-white shadow-sm ring-1 ring-gray-900/5 sm:rounded-lg">
        <div class="p-6">
          <h2 class="text-base font-semibold text-gray-900 mb-4">Process Status</h2>

          <!-- Progress Bar -->
          <div class="mb-6">
            <div class="w-full bg-gray-200 rounded">
              <div class="bg-indigo-600 text-xs leading-none py-1 text-center text-white rounded"
                   :style="{ width: progress + '%' }">
                {{ progress }}%
              </div>
            </div>
            <p class="mt-2 text-sm text-gray-600">
              Current status: <span class="font-medium text-gray-900">{{ statusLabels[status] ?? status }}</span>
            </p>
            <p v-if="isRefreshing" class="mt-1 text-xs text-gray-500">
              Refreshing session status...
            </p>
            <p v-if="telemetrySummary" class="mt-1 text-sm text-gray-600">
              Extractor progress:
                <span class="font-medium text-gray-900">
                {{ telemetrySummary.processedChunks }} / {{ telemetrySummary.totalChunks }} chunks
                ({{ telemetrySummary.percentComplete.toFixed(1) }}%)
              </span>
            </p>
          </div>

          <div class="mb-6 rounded-lg border border-blue-200 bg-blue-50 p-4">
            <h3 class="text-sm font-semibold text-blue-900">Live Activity</h3>
            <p class="mt-2 text-sm text-blue-900">{{ currentPhaseDetail.title }}</p>
            <p class="mt-1 text-sm text-blue-800">{{ currentPhaseDetail.description }}</p>
            <p class="mt-2 text-sm text-blue-700">{{ currentPhaseDetail.detail }}</p>
            <div class="mt-3 grid grid-cols-1 gap-2 text-sm text-blue-900 sm:grid-cols-2">
              <p>
                Elapsed runtime:
                <span class="font-medium">{{ elapsedRuntime }}</span>
              </p>
              <p>
                Polling interval:
                <span class="font-medium">every 3 seconds</span>
              </p>
              <p v-if="latestLog">
                Last status update:
                <span class="font-medium">{{ new Date(latestLog.timestamp).toLocaleString() }}</span>
              </p>
              <p v-if="latestLog">
                Latest event:
                <span class="font-medium">{{ statusLabels[latestLog.status] ?? latestLog.status }}</span>
              </p>
              <p v-if="telemetrySummary">
                Processed chunks:
                <span class="font-medium">{{ telemetrySummary.processedChunks }} / {{ telemetrySummary.totalChunks }}</span>
              </p>
              <p v-if="telemetrySummary">
                Relationships found:
                <span class="font-medium">{{ telemetrySummary.totalRelationships }}</span>
              </p>
              <p v-if="telemetrySummary">
                Successful chunks:
                <span class="font-medium">{{ telemetrySummary.successfulChunks }}</span>
              </p>
              <p v-if="telemetrySummary">
                Failed chunks:
                <span class="font-medium">{{ telemetrySummary.failedChunks }}</span>
              </p>
              <p v-if="telemetrySummary?.lastChunkId" class="sm:col-span-2">
                Last chunk:
                <span class="font-medium break-all">{{ telemetrySummary.lastChunkId }}</span>
              </p>
              <p v-if="telemetrySummary?.lastMessage" class="sm:col-span-2">
                Backend note:
                <span class="font-medium">{{ telemetrySummary.lastMessage }}</span>
              </p>
              <p v-if="telemetrySummary?.lastError" class="sm:col-span-2 text-red-700">
                Last backend error:
                <span class="font-medium">{{ telemetrySummary.lastError }}</span>
              </p>
            </div>
          </div>

          <div class="mb-6 overflow-hidden rounded-lg border border-slate-800 bg-slate-950 shadow-sm">
            <div class="flex items-center justify-between border-b border-slate-800 px-4 py-3">
              <div>
                <h3 class="text-sm font-semibold text-slate-100">Process Console</h3>
                <p class="mt-1 text-xs text-slate-400">Timestamped workflow updates for this session</p>
              </div>
              <span class="rounded-full border border-slate-700 px-2 py-1 text-xs text-slate-300">
                {{ consoleMessages.length }} entries
              </span>
            </div>
            <div class="max-h-80 overflow-y-auto px-4 py-3 font-mono text-xs leading-6">
              <div v-if="consoleMessages.length === 0" class="text-slate-400">
                Waiting for the first workflow event...
              </div>
              <div
                  v-for="entry in consoleMessages"
                  :key="entry.id"
                  class="border-b border-slate-900 py-2 last:border-b-0"
              >
                <span class="mr-3 text-slate-500">[{{ new Date(entry.timestamp).toLocaleTimeString() }}]</span>
                <span :class="consoleLineClasses[entry.kind] ?? consoleLineClasses.info">{{ entry.message }}</span>
              </div>
            </div>
          </div>

          <!-- Timeline View -->
          <div class="flow-root mt-6">
            <ul role="list" class="-mb-8">
              <li v-for="(event, eventIdx) in statusTimeline" :key="event.id">
                <div class="relative pb-8">
                  <span v-if="eventIdx !== statusTimeline.length - 1"
                        class="absolute left-4 top-4 -ml-px h-full w-0.5 bg-gray-200"
                        aria-hidden="true" />
                  <div class="relative flex space-x-3">
                    <div>
                      <span :class="[event.iconBackground, 'flex size-8 items-center justify-center rounded-full ring-8 ring-white']">
                        <component :is="event.icon" class="size-5 text-white" aria-hidden="true" />
                      </span>
                    </div>
                    <div class="flex min-w-0 flex-1 justify-between space-x-4 pt-1.5">
                      <div>
                        <p class="text-sm text-gray-500">
                          {{ event.content }} <span class="font-medium text-gray-900">{{ event.target }}</span>
                        </p>
                      </div>
                      <div class="whitespace-nowrap text-right text-sm text-gray-500">
                        <time :datetime="event.datetime">{{ new Date(event.datetime).toLocaleString() }}</time>
                      </div>
                    </div>
                  </div>
                </div>
              </li>
            </ul>
          </div>

          <!-- Conditional Navigation Buttons -->
          <div class="mt-6 mb-3 flex justify-end space-x-2">
            <button
                v-if="status === 'chunking'"
                @click="navigateBasedOnStatus"
                class="rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus:outline-indigo-600">
              Review chunks
            </button>
            <button
                v-else-if="status === 'enriching' || status === 'finished'"
                @click="navigateBasedOnStatus"
                class="rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus:outline-indigo-600">
              View analysis
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* Additional styling if needed */
</style>
