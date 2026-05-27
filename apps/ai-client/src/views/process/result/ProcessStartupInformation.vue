<script setup lang="ts">
import { computed, inject, ref, type Ref } from 'vue';
import StartupComponent from "../../../components/result/StartupComponent.vue";
import type { SessionWithResultResponse } from "../../../models/Result.ts";
import {
  ArrowRightStartOnRectangleIcon, CheckIcon,
  ClockIcon,
  DocumentArrowDownIcon,
  DocumentDuplicateIcon, XCircleIcon
} from "@heroicons/vue/20/solid";

const sessionData = inject<Ref<SessionWithResultResponse | null>>("sessionData");
const documentReferences = inject<Ref<Array<{
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
}>>>("documentReferences");
const expandedDocumentNames = ref<string[]>([]);

const sessionLoaded = computed(() => sessionData !== null);
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
  const logs = sessionLoaded.value && sessionData?.value ? sessionData.value.session.logs : [];

  return logs.map((log, index) => {
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

const hasDocumentReferences = computed(() => (documentReferences?.value?.length ?? 0) > 0);

const isDocumentExpanded = (documentName: string) => expandedDocumentNames.value.includes(documentName);

const toggleDocumentExpanded = (documentName: string) => {
  if (isDocumentExpanded(documentName)) {
    expandedDocumentNames.value = expandedDocumentNames.value.filter((name) => name !== documentName);
    return;
  }

  expandedDocumentNames.value = [...expandedDocumentNames.value, documentName];
};
</script>

<template>
  <div v-if="sessionLoaded && sessionData" class="space-y-6">
    <div v-if="hasDocumentReferences" class="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <div class="border-b border-slate-200 px-4 py-4 sm:px-6">
        <h3 class="text-base font-semibold text-slate-900">PDF Document References</h3>
        <p class="mt-1 text-sm text-slate-600">
          Review which source documents and selected chunks contributed to this CRE result.
        </p>
      </div>

      <div class="divide-y divide-slate-200">
        <div
            v-for="document in documentReferences"
            :key="document.name"
            class="px-4 py-4 sm:px-6"
        >
          <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h4 class="text-sm font-semibold text-slate-900">{{ document.title }}</h4>
              <p class="mt-1 text-sm text-slate-600">
                {{ document.authors || document.filename || document.name }}
              </p>
              <p class="mt-1 text-xs text-slate-500">
                {{ document.year || 'Year n/a' }}<span v-if="document.pageCount"> • {{ document.pageCount }} pages</span><span v-if="document.subject"> • {{ document.subject }}</span>
              </p>
              <p v-if="document.doi" class="mt-1 text-xs text-slate-500">
                DOI: {{ document.doi }}
              </p>
            </div>
            <div class="flex items-center gap-3">
              <p class="text-xs text-slate-500">
                {{ document.selectedChunkCount }} selected chunks
              </p>
              <button
                  type="button"
                  class="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  @click="toggleDocumentExpanded(document.name)"
              >
                {{ isDocumentExpanded(document.name) ? 'Hide chunks' : 'Show chunks' }}
              </button>
            </div>
          </div>

          <div v-if="isDocumentExpanded(document.name)" class="mt-4 space-y-3">
            <div
                v-for="(chunkText, index) in document.chunkTexts"
                :key="`${document.name}-${index}`"
                class="rounded-lg border border-slate-200 bg-slate-50 p-3"
            >
              <p class="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
                Source chunk {{ index + 1 }}
              </p>
              <p class="whitespace-pre-wrap text-sm text-slate-800">
                {{ chunkText }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
    <!-- Linkerkant: StartupComponent -->
    <div>
      <StartupComponent
          :title="sessionData.session.title"
          :relevance-score-threshold="sessionData.session.relevance_score_threshold"
          :key-events="sessionData.session.key_events"
          :collection-name="'Collection ' + sessionData.session.collection_id"
          :selected-model="sessionData.session.model_name"
      />
    </div>

    <!-- Rechterkant: Timeline View -->
    <div class="overflow-hidden bg-white shadow-sm ring-1 ring-gray-900/5 sm:rounded-lg">
      <div class="flow-root">
        <div class="px-4 py-6 sm:px-6">
          <h2 class="text-base font-semibold text-gray-900">Status Log</h2>
          <p class="mt-1 max-w-2xl text-sm text-gray-500">Overview of all recent logs</p>
        </div>
        <div class="border-t border-gray-100">
          <div class="px-4 py-6 sm:px-6">
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
        </div>
      </div>
    </div>
    </div>
  </div>

  <div v-else>
    <p class="text-center text-gray-500">Loading session data...</p>
  </div>
</template>
