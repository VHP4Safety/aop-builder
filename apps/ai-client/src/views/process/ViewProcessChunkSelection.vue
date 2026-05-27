<script setup lang="ts">
import {ref, computed, watch, inject, onMounted, onUnmounted} from 'vue';
import {useRoute, useRouter} from "vue-router";
import {SessionService} from "../../service/SessionService.ts";

const router = useRouter();
const route = useRoute();
const sessionService = inject<SessionService>("sessionService");

if (!sessionService) {
  throw new Error("sessionService not provided");
}

interface Chunk {
  id: string;
  text: string;
  relevance: number;
  selected: boolean;
  tokens: number;
  chunk_id: string;
  chunk: string;         // De tekst van de chunk
  heading: string;       // De kop/titel van de chunk
  document_id: string;   // De ID van het document waar de chunk bij hoort
  score: number;         // De relevantie score van de chunk
}

interface Document {
  document_id: string;
  name: string;
  chunks: Chunk[];
  expanded: boolean;
  done: boolean;
  threshold: number;
}

const documents = ref<Document[]>([]);
const globalThreshold = ref<number>(20);
const sessionId = Number(route.params.id);
const isSubmitting = ref(false);

const fetchSessionWithChunks = async () => {
  try {
    if (!sessionId) throw new Error("Session ID is missing from the route");

    const sessionData = await sessionService.getSessionWithChunks(sessionId);

    // 🚨 **Check of status niet "chunking" is, zo ja -> Redirect**
    if (sessionData.status !== "chunking") {
      console.warn(`⚠️ Sessie heeft status "${sessionData.status}", redirecting...`);
      router.push({ name: "ViewProcess", params: { id: sessionId } });
      return;
    }

    if (sessionData.documents) {
      globalThreshold.value = sessionData.relevance_score_threshold ?? 20;
      documents.value = sessionData.documents.map((doc: any) => ({
        document_id: doc.document_id,
        name: doc.name,
        chunks: doc.chunks.map((chunk: any) => ({
          id: chunk.chunk_id,
          text: chunk.chunk,
          relevance: chunk.score,
          selected: true,
          tokens: chunk.tokens ?? 300,  // fallback als tokens niet bestaan
          chunk_id: chunk.chunk_id,
          chunk: chunk.chunk,
          heading: chunk.heading ?? '',
          document_id: chunk.document_id,
          score: chunk.score
        })),
        expanded: false,
        done: false,
        threshold: sessionData.relevance_score_threshold ?? 20, // Gebruik standaard threshold
      }));
    }
  } catch (error) {
    console.error("❌ Fout bij ophalen van sessie met chunks:", error);
  }
};

onMounted(fetchSessionWithChunks);

// Global threshold slider (applies to all documents not yet included in analysis)
watch(globalThreshold, (newVal) => {
  documents.value.forEach(doc => {
    if (!doc.done) {
      doc.threshold = newVal;
      updateDocChunksByThreshold(doc);
    }
  });
});

// When a document's per-document threshold changes, update its chunks.
function updateDocThreshold(doc: Document) {
  if (!doc.done) {
    updateDocChunksByThreshold(doc);
  }
}

// This function sorts the chunks by descending relevance and selects only the top percentage.
function updateDocChunksByThreshold(doc: Document) {
  const sortedChunks = [...doc.chunks].sort((a, b) => b.relevance - a.relevance);
  const numToSelect = Math.ceil((doc.threshold / 100) * doc.chunks.length);
  doc.chunks.forEach(chunk => {
    const index = sortedChunks.findIndex(sc => sc.id === chunk.id);
    chunk.selected = index < numToSelect;
  });
}

// Reactive variable for sort order ("most" or "least")
const sortOrder = ref("most");

// Compute sorted documents based on sortOrder.
const sortedDocuments = computed(() => {
  let sorted = [...documents.value].sort((a, b) => {
    const avgA = a.chunks.length ? a.chunks.reduce((sum, c) => sum + c.relevance, 0) / a.chunks.length : 0;
    const avgB = b.chunks.length ? b.chunks.reduce((sum, c) => sum + c.relevance, 0) / b.chunks.length : 0;
    return avgB - avgA;
  });
  if (sortOrder.value === "least") {
    sorted = sorted.reverse();
  }
  return sorted;
});

// Toggle a document: only one document can be expanded at a time.
// When expanding, scroll its header into view with an extra 60px offset.
const toggleDocument = (doc: Document) => {
  if (!doc.expanded) {
    documents.value.forEach(d => {
      if (d !== doc && d.expanded) {
        d.expanded = false;
      }
    });
    doc.expanded = true;
    const docId = `doc-${doc.name.replace(/\s+/g, '-')}`;
    const element = document.getElementById(docId);
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "start" });
      setTimeout(() => {
        window.scrollBy({ top: -60, behavior: "smooth" });
      }, 300);
    }
  } else {
    doc.expanded = false;
  }
};

// When a document is marked as included in analysis, collapse it.
const handleDocDoneChange = (doc: Document) => {
  if (doc.done && doc.expanded) {
    doc.expanded = false;
  }
};

// Toggle "Include All in Analysis" / "Deselect All" based on current state.
const allIncluded = computed(() => documents.value.every(doc => doc.done));
const toggleIncludeAll = () => {
  if (allIncluded.value) {
    documents.value.forEach(doc => {
      doc.done = false;
    });
  } else {
    documents.value.forEach(doc => {
      doc.done = true;
      doc.expanded = false;
    });
  }
};

// Submit selection.
const submitSelection = async () => {
  try {
    isSubmitting.value = true; // ✅ Toon de loading spinner

    // 🔍 Filter alleen de documenten die gemarkeerd zijn als "done"
    const selectedDocuments = documents.value
        .filter(doc => doc.done)
        .map(doc => ({
          document_id: doc.document_id,
          name: doc.name,
          chunks: doc.chunks
              .filter(chunk => chunk.selected)
              .map(chunk => ({
                id: chunk.id,
                text: chunk.text,
                relevance: chunk.relevance,
                selected: chunk.selected,
                tokens: chunk.tokens,
              })),
        }));

    if (selectedDocuments.length === 0) {
      isSubmitting.value = false;
      return;
    }

    // 📨 **Verstuur de geselecteerde documenten naar de backend**
    await sessionService.submitSelectedChunks(sessionId, selectedDocuments);

    // 🔀 **Navigeer naar ViewProcess met de sessie-ID**
    await router.push({name: "ViewProcess", params: {id: sessionId}});

  } catch (error) {
    console.error("❌ Fout bij submit:", error);
  } finally {
    isSubmitting.value = false; // ✅ Verberg de loading spinner
  }
};

// Scroll-to-top functionality.
const showScrollTop = ref(false);
const handleScroll = () => {
  showScrollTop.value = window.scrollY > 300;
};
const scrollToTop = () => {
  window.scrollTo({ top: 0, behavior: 'smooth' });
};
window.addEventListener('scroll', handleScroll);
onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll);
});
</script>

<template>
  <div class="space-y-8">
    <!-- Header Section with Global Description, Global Threshold Slider, and Submit Selection Button -->
    <div class="flex flex-col sm:flex-row justify-between items-start mb-6">
      <div class="max-w-7xl">
        <h2 class="text-base font-semibold text-gray-900 mb-2">Chunk Selection</h2>
        <p class="text-sm text-gray-600">
          Review the extracted chunks below. For each document, you can select or deselect the chunks before continuing.
          Documents are ordered by highest average relevance, and within each document the chunks are sorted by relevance (highest first).
          Each chunk shows its full text (≈300 tokens), its relevance score, and token count.
        </p>
        <!-- Global Threshold Slider (applies to all documents not yet included in analysis) -->
        <div class="mt-4">
          <label for="globalThreshold" class="block text-sm font-medium text-gray-700">
            Global Relevance Score Threshold (%)
          </label>
          <input
              id="globalThreshold"
              type="range"
              min="0"
              max="100"
              v-model.number="globalThreshold"
              class="mt-1 w-full"
          />
          <p class="text-xs text-gray-500">Current global threshold: {{ globalThreshold }}%</p>
        </div>
      </div>
      <div class="ml-4 mt-4 sm:mt-0">
        <button
            @click="submitSelection"
            :disabled="isSubmitting"
            class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus:outline-indigo-600 flex items-center"
        >
          <span v-if="isSubmitting" class="animate-spin border-2 border-white border-t-transparent rounded-full w-4 h-4 mr-2"></span>
          {{ isSubmitting ? "Submitting..." : "Submit Selection" }}
        </button>
      </div>
    </div>

    <!-- Global Controls: Toggle Include/Deselect All & Sort Order Dropdown -->
    <div class="flex justify-between items-center mb-4">
      <button
          @click="toggleIncludeAll"
          class="rounded-md bg-green-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-green-500 focus:outline-green-600"
      >
        {{ allIncluded ? 'Deselect All' : 'Include All in Analysis' }}
      </button>
      <div class="flex items-center">
        <label for="sortOrder" class="mr-2 text-sm text-gray-700">Sort by relevance:</label>
        <select
            id="sortOrder"
            v-model="sortOrder"
            class="rounded-md border-gray-300 focus:ring-indigo-500"
        >
          <option value="most">Most relevant first</option>
          <option value="least">Least relevant first</option>
        </select>
      </div>
    </div>

    <!-- CollectionDocuments List -->
    <div class="space-y-6">
      <div
          v-for="doc in sortedDocuments"
          :key="doc.name"
          :class="[
          'bg-white shadow-sm ring-1 ring-gray-900/5 sm:rounded-lg',
          doc.done ? 'border-4 border-green-500' : ''
        ]"
      >
        <!-- CollectionDocuments Header with Summary and Toggle Include in Analysis -->
        <div
            :id="`doc-${doc.name.replace(/\s+/g, '-')}`"
            class="flex flex-col sm:flex-row items-start sm:items-center justify-between px-4 py-4 border-b border-gray-200 cursor-pointer"
            @click="toggleDocument(doc)"
        >
          <div>
            <h3 class="text-lg font-medium text-gray-900">{{ doc.name }}</h3>
            <p class="text-sm text-gray-600">
              {{ doc.chunks.filter(chunk => chunk.selected).length }} of {{ doc.chunks.length }} chunks selected,
              Average Relevance: {{
                doc.chunks.length ? (doc.chunks.reduce((sum, chunk) => sum + chunk.relevance, 0) / doc.chunks.length).toFixed(1) : "0.0"
              }}%
            </p>
          </div>
          <div class="flex items-center space-x-4 mt-2 sm:mt-0">
            <!-- "Include in analysis" toggle (clicking toggles doc.done) -->
            <label class="flex items-center space-x-1 cursor-pointer" @click.stop>
              <input
                  type="checkbox"
                  v-model="doc.done"
                  @change="handleDocDoneChange(doc)"
                  class="h-5 w-5 text-green-600 border-gray-300 rounded-md focus:ring-2 focus:ring-green-500"
              />
              <span class="text-sm text-gray-700">
                {{ doc.done ? 'Remove from analysis' : 'Include in analysis' }}
              </span>
            </label>
            <div>
              <span class="text-sm text-gray-600">
                {{ doc.expanded ? 'Collapse' : 'Expand' }}
              </span>
            </div>
          </div>
        </div>

        <!-- Per-CollectionDocuments Threshold Slider (only for documents not included in analysis) -->
        <div v-if="!doc.done" class="px-4 py-2 border-b border-gray-200">
          <label :for="`threshold-${doc.name.replace(/\s+/g, '-')}`" class="block text-sm font-medium text-gray-700">
            Documents Relevance Threshold (%)
          </label>
          <input
              :id="`threshold-${doc.name.replace(/\s+/g, '-')}`"
              type="range"
              min="0"
              max="100"
              v-model.number="doc.threshold"
              @change="updateDocThreshold(doc)"
              class="mt-1 w-full"
          />
          <p class="text-xs text-gray-500">Current threshold: {{ doc.threshold }}%</p>
        </div>

        <!-- Collapsible Chunk List -->
        <div v-if="doc.expanded" class="px-4 pb-4">
          <div class="overflow-y-auto" :style="{ maxHeight: 'calc(100vh - 200px)' }">
            <ul class="divide-y divide-gray-200">
              <!-- Each document's chunks sorted by descending relevance -->
              <li
                  v-for="chunk in [...doc.chunks].sort((a, b) => b.relevance - a.relevance)"
                  :key="chunk.id"
                  class="flex items-center py-2 cursor-pointer"
                  @click="chunk.selected = !chunk.selected"
              >
                <!-- Chunk Checkbox on Left -->
                <div class="flex-shrink-0 mr-4">
                  <input
                      type="checkbox"
                      v-model="chunk.selected"
                      @click.stop
                      class="h-5 w-5 text-indigo-600 border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500"
                  >
                </div>
                <!-- Chunk Content -->
                <div class="flex-1">
                  <p class="font-bold text-sm text-gray-900">Text:</p>
                  <p class="text-sm text-gray-800 whitespace-pre-wrap break-words">
                    {{ chunk.text }}
                  </p>
                  <p class="text-xs text-gray-500">
                    Relevance: {{ chunk.relevance }}%
                  </p>
                </div>
              </li>
            </ul>
          </div>
        </div>

      </div>
    </div>

    <!-- Fixed Scroll to Top Button -->
    <button
        v-if="showScrollTop"
        @click="scrollToTop"
        class="fixed bottom-4 right-4 rounded-full bg-indigo-600 p-3 text-white shadow-lg hover:bg-indigo-500 focus:outline-indigo-600"
        aria-label="Scroll to top"
    >
      Scroll to top
    </button>
  </div>
</template>

<style scoped>
/* Additional styling if needed */
</style>
