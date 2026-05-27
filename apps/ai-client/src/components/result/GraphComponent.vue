<script setup lang="ts">
import { Dialog, DialogPanel, DialogTitle, TransitionChild, TransitionRoot } from '@headlessui/vue'
import { XMarkIcon } from '@heroicons/vue/24/outline'
import {computed, inject, onMounted, onUnmounted, ref, type Ref, watch} from "vue";
import cytoscape from "cytoscape";
import { useRoute, useRouter } from "vue-router";
import {SessionService} from "../../service/SessionService.ts";
import type { CausalRelation } from "../../models/Session";
import {SessionWithResultResponse} from "../../models/Result.ts";

const cyContainer = ref<HTMLDivElement | null>(null);
const showLegend = ref(false);
const drawer = ref(false)
const selectedNodeId = ref<string | null>(null);
const cyInstance = ref<cytoscape.Core | null>(null);

const route = useRoute();
const router = useRouter();
const sessionData = ref<SessionWithResultResponse | null>(null);
const providedSessionData = inject<Ref<SessionWithResultResponse | null> | null>("sessionData", null);
const sessionService = inject<SessionService>("sessionService");

if (!sessionService) {
  throw new Error("sessionService not provided");
}

const fetchSessionData = async () => {
  try {
    if (providedSessionData?.value) {
      sessionData.value = providedSessionData.value;
      initializeGraph();
      return;
    }

    const sessionId = Number(route.params.id);
    const data = await sessionService.getSessionWithResult(sessionId);

    if (!['enriching', 'finished'].includes(data.session.status)) {
      router.push({ name: 'Home' });
      return;
    }

    sessionData.value = data;
    initializeGraph();

  } catch (error) {
    console.error("Error fetching session data:", error);
    router.push({ name: 'Home' });
  }
};

const findRelationsForNode = (nodeId: string) => {
  const relations: CausalRelation[] = [];

  sessionData.value?.extracted_causal_relations?.forEach(item => {
    item.output?.relationships?.forEach(rel => {
      const relation = rel as CausalRelation;
      if (relation.subject === nodeId || relation.object === nodeId) {
        relations.push(relation);
      }
    });
  });

  return relations;
};

const relatedChunks = computed(() => {
  if (!selectedNodeId.value || !sessionData.value) return [];

  const chunkMap = new Map<string, string>(); // chunkId -> text

  // 1. Verzamel alle chunk teksten die relevant zijn voor de geselecteerde node
  sessionData.value.extracted_causal_relations?.forEach(item => {
    const match = item.output.relationships?.some(
        rel => rel.subject === selectedNodeId.value || rel.object === selectedNodeId.value
    );

    if (match && item.id && item.text) {
      chunkMap.set(item.id, item.text);
    }
  });

  // 2. Groepeer per document
  const result: { documentName: string; chunks: string[] }[] = [];

  sessionData.value.selected_chunks.forEach(doc => {
    const relevantChunks = doc.chunks.filter(chunk => chunkMap.has(chunk.id));
    if (relevantChunks.length > 0) {
      result.push({
        documentName: doc.name,
        chunks: relevantChunks.map(chunk => chunkMap.get(chunk.id)!)
      });
    }
  });

  return result;
});

const initializeGraph = () => {
  if (!sessionData.value || !sessionData.value.extracted_causal_relations || !cyContainer.value) return;

  cyInstance.value?.destroy();

  const elements: cytoscape.ElementDefinition[] = [];
  const nodeSet = new Set<string>();
  const edgeSet = new Set<string>();

  sessionData.value.extracted_causal_relations?.forEach((item) => {
    item.output?.relationships?.forEach((relation) => {
      const { subject, verb, object, causal_connection } = relation as CausalRelation;

      if (!subject?.trim() || !object?.trim() || !verb?.trim()) {
        console.warn("❗ Ongeldige relatie overgeslagen:", relation);
        return;
      }

      if (!nodeSet.has(subject)) {
        nodeSet.add(subject);
        elements.push({
          data: { id: subject, label: subject },
          classes: 'subject'
        });
      }

      if (!nodeSet.has(object)) {
        nodeSet.add(object);
        elements.push({
          data: { id: object, label: object },
        });
      }

      const edgeId = `${subject}_${object}_${verb}`;
      if (!edgeSet.has(edgeId)) {
        edgeSet.add(edgeId);
        const edgeClass =
            causal_connection === "Positive" ? "positive" :
                causal_connection === "Negative" ? "negative" :
                    causal_connection === "Not existing" ? "neutral" : "";

        elements.push({
          data: {
            id: edgeId,
            source: subject,
            target: object,
            label: verb
          },
          classes: edgeClass
        });
      }
    });
  });

  const styles: cytoscape.Stylesheet[] = [
    {
      selector: "node",
      style: {
        "background-color": "#d59898",
        "width": "label",
        "height": "label",
        "padding": "10px",
        "shape": "roundrectangle",
        "font-size": 12,
        "text-valign": "center",
        "text-halign": "center",
        "text-wrap": "wrap",
        "text-max-width": "80px",
        label: "data(label)",
      } as cytoscape.Css.Node,
    },
    {
      selector: "node.subject",
      style: {
        "background-color": "#3b82f6",
        color: "#fff",
      } as cytoscape.Css.Node,
    },
    {
      selector: "edge",
      style: {
        width: 4,
        label: "data(label)",
        "font-size": 12,
        "text-rotation": "autorotate",
        "text-margin-y": -10,
        "text-background-color": "#000000",
        "text-background-opacity": 0.8,
        "text-background-shape": "roundrectangle",
        "text-background-padding": "2px 4px",
        "text-outline-color": "#000000",
        "text-outline-width": 1,
        "color": "#ffffff",
        "curve-style": "bezier",
        "target-arrow-shape": "triangle",
        "arrow-scale": 1,
      } as cytoscape.Css.Edge,
    },
    {
      selector: "edge.positive",
      style: {
        "line-color": "#16a34a",
        "target-arrow-color": "#16a34a",
      } as cytoscape.Css.Edge,
    },
    {
      selector: "edge.negative",
      style: {
        "line-color": "#dc2626",
        "target-arrow-color": "#dc2626",
      } as cytoscape.Css.Edge,
    },
    {
      selector: "edge.neutral",
      style: {
        "line-color": "#6b7280",
        "target-arrow-color": "#6b7280",
      } as cytoscape.Css.Edge,
    },
  ];

  cyInstance.value = cytoscape({
    container: cyContainer.value,
    elements,
    layout: {
      name: "cose",
      animate: true,
      nodeRepulsion: () => 100000,
      idealEdgeLength: () => 200,
      edgeElasticity: () => 200,
    },
    style: styles,
  });

  cyInstance.value.on("tap", "node", (event: cytoscape.EventObject) => {
    const nodeId = event.target.id();
    selectedNodeId.value = nodeId;
    drawer.value = true;
  });
};

onMounted(fetchSessionData);
onUnmounted(() => {
  cyInstance.value?.destroy();
});

watch(() => route.params.id, () => {
  fetchSessionData();
});

watch(
    () => providedSessionData?.value,
    (nextValue) => {
      if (nextValue) {
        sessionData.value = nextValue;
        initializeGraph();
      }
    },
    { deep: true }
);
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
              <DialogPanel class="pointer-events-auto w-screen max-w-md">
                <div class="flex h-full flex-col overflow-y-scroll bg-white py-6 shadow-xl">
                  <div class="px-4 sm:px-6">
                    <div class="flex items-start justify-between">
                      <DialogTitle class="text-base font-semibold text-gray-900">Bronverwijzing</DialogTitle>
                      <div class="ml-3 flex h-7 items-center">
                        <button type="button" class="relative rounded-md bg-white text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2" @click="drawer = false; selectedNodeId = null">
                          <span class="absolute -inset-2.5" />
                          <span class="sr-only">Sluiten</span>
                          <XMarkIcon class="size-6" aria-hidden="true" />
                        </button>
                      </div>
                    </div>
                  </div>
                  <div class="relative mt-6 flex-1 px-4 sm:px-6">
                    <div v-if="selectedNodeId">
                      <p class="mb-2 font-semibold">Relaties waarin deze node voorkomt:</p>
                      <div v-for="(rel, index) in findRelationsForNode(selectedNodeId)" :key="index" class="mb-2 p-3 rounded border bg-gray-50 border-gray-200 shadow-sm">
                        <div class="flex flex-wrap items-center justify-between">
                          <div class="text-sm">
                            <span class="font-medium text-blue-700">{{ rel.subject }}</span>
                            <span class="mx-1 text-gray-500">—</span>
                            <span class="italic text-gray-700">{{ rel.verb }}</span>
                            <span class="mx-1 text-gray-500">→</span>
                            <span class="text-purple-700">{{ rel.object }}</span>
                          </div>
                          <span
                              class="ml-2 text-xs font-semibold px-2 py-0.5 rounded"
                              :class="{
                                'bg-green-100 text-green-800': rel.causal_connection === 'Positive',
                                'bg-red-100 text-red-800': rel.causal_connection === 'Negative',
                                'bg-gray-200 text-gray-800': rel.causal_connection === 'Not existing'
                              }"
                                                  >
                              {{ rel.causal_connection }}
                            </span>
                        </div>
                      </div>

                      <div v-if="relatedChunks.length" class="mt-6">
                        <p class="mb-2 font-semibold">Fragmenten per document:</p>
                        <div
                            v-for="(group, docIndex) in relatedChunks"
                            :key="docIndex"
                            class="mb-4"
                        >
                          <h4 class="text-sm font-bold mb-1 text-indigo-600">
                            📄 {{ group.documentName }}
                          </h4>
                          <div
                              v-for="(chunk, chunkIndex) in group.chunks"
                              :key="chunkIndex"
                              class="bg-gray-100 text-sm p-3 rounded mb-2 border border-gray-300 whitespace-pre-wrap"
                          >
                            {{ chunk }}
                          </div>
                        </div>
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
  <div class="relative w-full h-screen bg-gray-100">
    <div class="absolute top-4 right-4 z-10">
      <button
          @click="showLegend = true"
          class="bg-indigo-600 text-white px-4 py-2 rounded shadow hover:bg-indigo-500"
      >
        Legenda
      </button>
    </div>

    <div ref="cyContainer" class="w-full h-full" />

    <!-- Dialog -->
    <div v-if="showLegend" class="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-20">
      <div class="bg-white p-6 rounded-lg shadow-lg max-w-md w-full relative">
        <h2 class="text-lg font-bold mb-4">🧭 Legenda</h2>
        <ul class="space-y-2 text-sm">
          <li><span class="inline-block w-4 h-4 rounded-full bg-green-600 mr-2"></span> Positieve relatie</li>
          <li><span class="inline-block w-4 h-4 rounded-full bg-red-600 mr-2"></span> Negatieve relatie</li>
          <li><span class="inline-block w-4 h-4 rounded-full bg-gray-600 mr-2"></span> Geen relatie (Not existing)</li>
          <li><span class="inline-block w-4 h-4 rounded-full bg-blue-600 mr-2"></span> Subject</li>
          <li><span class="inline-block w-4 h-4 rounded-full mr-2" style="background-color: #d59898"></span> Object</li>
        </ul>
        <button
            @click="showLegend = false"
            class="absolute top-2 right-2 text-gray-500 hover:text-black"
        >
          ✕
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
</style>
