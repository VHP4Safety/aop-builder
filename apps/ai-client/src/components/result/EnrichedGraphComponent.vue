<script setup lang="ts">
import { Dialog, DialogPanel, DialogTitle, TransitionChild, TransitionRoot } from '@headlessui/vue';
import { XMarkIcon } from '@heroicons/vue/24/outline';
import { computed, inject, onMounted, onUnmounted, ref, type Ref, watch } from 'vue';
import cytoscape from 'cytoscape';
import type { EnrichedGraphEdge, EnrichedGraphNode, SessionWithResultResponse } from '../../models/Result.ts';

const cyContainer = ref<HTMLDivElement | null>(null);
const drawer = ref(false);
const selectedNodeId = ref<string | null>(null);
const cyInstance = ref<cytoscape.Core | null>(null);
const sessionData = inject<Ref<SessionWithResultResponse | null>>('sessionData');

if (!sessionData) {
  throw new Error('sessionData not provided');
}

const enrichedGraph = computed(() => sessionData.value?.enriched_graph ?? null);

const selectedNode = computed<EnrichedGraphNode | null>(() => {
  if (!selectedNodeId.value || !enrichedGraph.value) {
    return null;
  }

  return enrichedGraph.value.nodes.find((node) => node.id === selectedNodeId.value) ?? null;
});

const relatedEdges = computed<EnrichedGraphEdge[]>(() => {
  if (!selectedNodeId.value || !enrichedGraph.value) {
    return [];
  }

  return enrichedGraph.value.edges.filter(
      (edge) => edge.source === selectedNodeId.value || edge.target === selectedNodeId.value
  );
});

const enrichmentStatusMessage = computed(() => {
  if (enrichedGraph.value) {
    return null;
  }

  if (sessionData.value?.session.status === 'enriching') {
    return sessionData.value.session.telemetry?.last_message
        ?? 'The raw graph is ready. Ontology lookup and AOP standardization are still running.';
  }

  return 'No enriched graph is available for this session yet.';
});

const initializeGraph = () => {
  if (!enrichedGraph.value || !cyContainer.value) {
    cyInstance.value?.destroy();
    cyInstance.value = null;
    return;
  }

  cyInstance.value?.destroy();

  const elements: cytoscape.ElementDefinition[] = [
    ...enrichedGraph.value.nodes.map((node) => ({
      data: {
        id: node.id,
        label: node.display_label,
        rawLabel: node.raw_label,
        ontologyCurie: node.ontology_term?.curie ?? '',
        hasOntology: Boolean(node.ontology_term),
        hasAopLinks: (node.aop_wiki_links?.length ?? 0) > 0,
      },
      classes: [
        node.ontology_term ? 'ontology-match' : '',
        (node.aop_wiki_links?.length ?? 0) > 0 ? 'aop-linked' : '',
      ].filter(Boolean).join(' '),
    })),
    ...enrichedGraph.value.edges.map((edge) => ({
      data: {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.predicate,
      },
      classes:
          edge.causal_connection === 'Positive'
              ? 'positive'
              : edge.causal_connection === 'Negative'
                  ? 'negative'
                  : 'neutral',
    })),
  ];

  cyInstance.value = cytoscape({
    container: cyContainer.value,
    elements,
    layout: {
      name: 'cose',
      animate: true,
      nodeRepulsion: () => 140000,
      idealEdgeLength: () => 190,
      edgeElasticity: () => 180,
    },
    style: [
      {
        selector: 'node',
        style: {
          'background-color': '#0f766e',
          'width': 'label',
          'height': 'label',
          'padding': '12px',
          'shape': 'roundrectangle',
          'font-size': 12,
          'text-valign': 'center',
          'text-halign': 'center',
          'text-wrap': 'wrap',
          'text-max-width': '110px',
          'border-width': 2,
          'border-color': '#134e4a',
          'color': '#ffffff',
          label: 'data(label)',
        } as cytoscape.Css.Node,
      },
      {
        selector: 'node.ontology-match',
        style: {
          'background-color': '#1d4ed8',
          'border-color': '#1e3a8a',
        } as cytoscape.Css.Node,
      },
      {
        selector: 'node.aop-linked',
        style: {
          'border-color': '#f59e0b',
          'border-width': 4,
        } as cytoscape.Css.Node,
      },
      {
        selector: 'edge',
        style: {
          width: 4,
          label: 'data(label)',
          'font-size': 11,
          'text-rotation': 'autorotate',
          'text-margin-y': -10,
          'text-background-color': '#0f172a',
          'text-background-opacity': 0.8,
          'text-background-shape': 'roundrectangle',
          'text-background-padding': '2px 4px',
          'text-outline-color': '#0f172a',
          'text-outline-width': 1,
          color: '#ffffff',
          'curve-style': 'bezier',
          'target-arrow-shape': 'triangle',
          'arrow-scale': 1,
        } as cytoscape.Css.Edge,
      },
      {
        selector: 'edge.positive',
        style: {
          'line-color': '#16a34a',
          'target-arrow-color': '#16a34a',
        } as cytoscape.Css.Edge,
      },
      {
        selector: 'edge.negative',
        style: {
          'line-color': '#dc2626',
          'target-arrow-color': '#dc2626',
        } as cytoscape.Css.Edge,
      },
      {
        selector: 'edge.neutral',
        style: {
          'line-color': '#6b7280',
          'target-arrow-color': '#6b7280',
        } as cytoscape.Css.Edge,
      },
    ],
  });

  cyInstance.value.on('tap', 'node', (event: cytoscape.EventObject) => {
    selectedNodeId.value = event.target.id();
    drawer.value = true;
  });
};

onMounted(initializeGraph);
onUnmounted(() => {
  cyInstance.value?.destroy();
});

watch(enrichedGraph, () => {
  initializeGraph();
}, { deep: true });
</script>

<template>
  <TransitionRoot as="template" :show="drawer">
    <Dialog class="relative z-50" @close="drawer = false">
      <TransitionChild as="template" enter="ease-in-out duration-500" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in-out duration-500" leave-from="opacity-100" leave-to="opacity-0">
        <div class="fixed inset-0 bg-gray-500/75 transition-opacity" />
      </TransitionChild>

      <div class="fixed inset-0 overflow-hidden">
        <div class="absolute inset-0 overflow-hidden">
          <div class="pointer-events-none fixed inset-y-0 right-0 flex max-w-full pl-10">
            <TransitionChild as="template" enter="transform transition ease-in-out duration-500 sm:duration-700" enter-from="translate-x-full" enter-to="translate-x-0" leave="transform transition ease-in-out duration-500 sm:duration-700" leave-from="translate-x-0" leave-to="translate-x-full">
              <DialogPanel class="pointer-events-auto w-screen max-w-xl">
                <div class="flex h-full flex-col overflow-y-scroll bg-white py-6 shadow-xl">
                  <div class="px-4 sm:px-6">
                    <div class="flex items-start justify-between">
                      <DialogTitle class="text-base font-semibold text-gray-900">Enriched Node Details</DialogTitle>
                      <div class="ml-3 flex h-7 items-center">
                        <button type="button" class="relative rounded-md bg-white text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2" @click="drawer = false; selectedNodeId = null">
                          <span class="absolute -inset-2.5" />
                          <span class="sr-only">Close panel</span>
                          <XMarkIcon class="size-6" aria-hidden="true" />
                        </button>
                      </div>
                    </div>
                  </div>

                  <div v-if="selectedNode" class="relative mt-6 flex-1 px-4 sm:px-6">
                    <div class="space-y-6">
                      <div class="rounded-lg border border-slate-200 bg-slate-50 p-4">
                        <h3 class="text-sm font-semibold text-slate-900">Entity</h3>
                        <p class="mt-2 text-base font-medium text-slate-900">{{ selectedNode.display_label }}</p>
                        <p class="mt-1 text-sm text-slate-600">Raw label: {{ selectedNode.raw_label }}</p>
                        <p class="mt-1 text-sm text-slate-600">Normalized key: {{ selectedNode.normalized_label }}</p>
                      </div>

                      <div class="rounded-lg border border-blue-200 bg-blue-50 p-4">
                        <h3 class="text-sm font-semibold text-blue-900">Ontology Match</h3>
                        <div v-if="selectedNode.ontology_term" class="mt-2 space-y-2 text-sm text-blue-900">
                          <p><span class="font-medium">Label:</span> {{ selectedNode.ontology_term.label ?? 'n/a' }}</p>
                          <p><span class="font-medium">CURIE:</span> {{ selectedNode.ontology_term.curie ?? 'n/a' }}</p>
                          <p><span class="font-medium">Ontology:</span> {{ selectedNode.ontology_term.ontology_name ?? 'n/a' }}</p>
                          <p><span class="font-medium">Match score:</span> {{ selectedNode.ontology_term.match_score ?? 'n/a' }}</p>
                          <p v-if="selectedNode.ontology_term.description"><span class="font-medium">Description:</span> {{ selectedNode.ontology_term.description }}</p>
                          <a
                              v-if="selectedNode.ontology_term.iri"
                              :href="selectedNode.ontology_term.iri"
                              target="_blank"
                              rel="noreferrer"
                              class="inline-flex text-sm font-medium text-blue-700 hover:text-blue-600"
                          >
                            Open ontology term
                          </a>
                        </div>
                        <p v-else class="mt-2 text-sm text-blue-800">No ontology match was attached to this node.</p>
                      </div>

                      <div class="rounded-lg border border-amber-200 bg-amber-50 p-4">
                        <h3 class="text-sm font-semibold text-amber-900">AOP-Wiki Links</h3>
                        <ul v-if="selectedNode.aop_wiki_links?.length" class="mt-2 space-y-2">
                          <li v-for="link in selectedNode.aop_wiki_links" :key="link.url">
                            <a :href="link.url" target="_blank" rel="noreferrer" class="text-sm font-medium text-amber-900 hover:text-amber-700">
                              {{ link.label || link.url }}
                            </a>
                          </li>
                        </ul>
                        <p v-else class="mt-2 text-sm text-amber-800">No AOP-Wiki links were attached to this node.</p>
                      </div>

                      <div class="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
                        <h3 class="text-sm font-semibold text-emerald-900">Connected Evidence</h3>
                        <div v-if="relatedEdges.length" class="mt-3 space-y-4">
                          <div v-for="edge in relatedEdges" :key="edge.id" class="rounded-lg border border-emerald-100 bg-white p-3">
                            <p class="text-sm font-medium text-emerald-900">
                              {{ edge.source_label }} {{ edge.predicate }} {{ edge.target_label }}
                            </p>
                            <p class="mt-1 text-xs uppercase tracking-wide text-emerald-700">{{ edge.causal_connection }}</p>
                            <ul class="mt-3 space-y-3">
                              <li v-for="(evidence, index) in edge.evidence" :key="`${edge.id}-${index}`" class="rounded border border-slate-200 bg-slate-50 p-3">
                                <p class="text-xs font-medium uppercase tracking-wide text-slate-500">{{ evidence.document_name ?? 'Unknown document' }}</p>
                                <p class="mt-2 whitespace-pre-wrap text-sm text-slate-800">{{ evidence.chunk_text ?? 'No chunk text stored.' }}</p>
                              </li>
                            </ul>
                          </div>
                        </div>
                        <p v-else class="mt-2 text-sm text-emerald-800">No edge evidence is attached to this node.</p>
                      </div>
                    </div>
                  </div>
                </div>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </div>
    </Dialog>
  </TransitionRoot>

  <div class="space-y-4">
    <div class="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h2 class="text-base font-semibold text-slate-900">Enriched AOP Graph</h2>
      <p class="mt-1 text-sm text-slate-600">
        This step standardizes the raw extraction with ontology terms, AOP-Wiki links, and evidence-backed edges.
      </p>
      <div v-if="enrichedGraph?.summary" class="mt-4 grid grid-cols-1 gap-3 text-sm text-slate-700 sm:grid-cols-2 lg:grid-cols-4">
        <p><span class="font-medium text-slate-900">Standardized nodes:</span> {{ enrichedGraph.summary.standardized_nodes }}</p>
        <p><span class="font-medium text-slate-900">Standardized edges:</span> {{ enrichedGraph.summary.standardized_edges }}</p>
        <p><span class="font-medium text-slate-900">Ontology matches:</span> {{ enrichedGraph.summary.nodes_with_ontology_match }}</p>
        <p><span class="font-medium text-slate-900">AOP-linked nodes:</span> {{ enrichedGraph.summary.nodes_with_aop_links }}</p>
      </div>
      <p v-if="enrichmentStatusMessage" class="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        {{ enrichmentStatusMessage }}
      </p>
    </div>

    <div v-if="enrichedGraph" class="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <div ref="cyContainer" class="h-[42rem] w-full" />
    </div>
  </div>
</template>
