<script setup lang="ts">
import { ref, computed, inject, onMounted } from 'vue';
import { useRoute, useRouter } from "vue-router";
import {SessionService} from "../../../service/SessionService.ts";

const sessionService = inject<SessionService>("sessionService")

if (!sessionService) {
  throw new Error("sessionService not provided");
}

const route = useRoute();
const router = useRouter();

interface Chunk {
  id: string;
  text: string;
  relevance: number;
  selected: boolean;
  tokens: number;
}

interface Document {
  document_id: string;
  name: string;
  chunks: Chunk[];
  expanded: boolean;
  done: boolean;
  threshold: number;
}

interface SessionData {
  session: {
    id: number;
    relevance_score_threshold: number;
    status: string;
  };
  selected_chunks: Document[];
}

const globalThreshold = ref(20);
const documents = ref<Document[]>([]);
const sessionData = ref<SessionData | null>(null);

const fetchSessionData = async () => {
  try {
    const sessionId = Number(route.params.id);
    const data = await sessionService.getSessionWithResult(sessionId);

    if (!['enriching', 'finished'].includes(data.session.status)) {
      router.push({ name: 'Home' });
      return;
    }

    sessionData.value = {
      session: data.session,
      selected_chunks: data.selected_chunks.map((doc) => ({
        ...doc,
        expanded: false,
        done: false,
        threshold: data.session.relevance_score_threshold ?? 20,
        chunks: doc.chunks.map((chunk) => ({
          ...chunk,
          selected: true,
          tokens: 300,
        })),
      }))
    };
    globalThreshold.value = data.session.relevance_score_threshold;

    documents.value = data.selected_chunks.map((doc: any) => ({
      document_id: doc.document_id,
      name: doc.name,
      chunks: doc.chunks.map((chunk: any) => ({
        id: chunk.id,
        text: chunk.text,
        relevance: chunk.relevance,
        selected: true,
        tokens: 300,
      })),
      expanded: false,
      done: false,
      threshold: data.session.relevance_score_threshold ?? 20,
    }));
  } catch (error) {
    console.error("Error fetching session data:", error);
    router.push({ name: 'Home' });
  }
};

onMounted(fetchSessionData);

const sortOrder = ref("most");

const sortedDocuments = computed(() => {
  return [...documents.value].sort((a, b) => {
    const avgA = a.chunks.reduce((sum, c) => sum + c.relevance, 0) / (a.chunks.length || 1);
    const avgB = b.chunks.reduce((sum, c) => sum + c.relevance, 0) / (b.chunks.length || 1);
    return sortOrder.value === "most" ? avgB - avgA : avgA - avgB;
  });
});

const toggleDocument = (doc: Document) => {
  doc.expanded = !doc.expanded;
  if (doc.expanded) {
    documents.value.forEach(d => {
      if (d !== doc) d.expanded = false;
    });
  }
};

const showScrollTop = ref(false);
const handleScroll = () => {
  showScrollTop.value = window.scrollY > 300;
};
const scrollToTop = () => {
  window.scrollTo({ top: 0, behavior: 'smooth' });
};
window.addEventListener('scroll', handleScroll);
</script>

<template>
  <div v-if="sessionData" class="space-y-8">
    <!-- Controls -->
    <div class="flex justify-between items-center mb-4">
      <div class="flex items-center">
        <label for="sortOrder" class="mr-2 text-sm text-gray-700">Sort by relevance:</label>
        <select id="sortOrder" v-model="sortOrder" class="rounded-md border-gray-300 focus:ring-indigo-500">
          <option value="most">Most relevant first</option>
          <option value="least">Least relevant first</option>
        </select>
      </div>
    </div>

    <!-- Document List -->
    <div class="space-y-6">
      <div v-for="doc in sortedDocuments" :key="doc.name" class="bg-white shadow-sm ring-1 ring-gray-900/5 sm:rounded-lg">
        <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between px-4 py-4 border-b border-gray-200 cursor-pointer" @click="toggleDocument(doc)">
          <div>
            <h3 class="text-lg font-medium text-gray-900">{{ doc.name }}</h3>
            <p class="text-sm text-gray-600">
              {{ doc.chunks.filter(chunk => chunk.selected).length }} of {{ doc.chunks.length }} chunks selected,
              Avg Relevance: {{ doc.chunks.length ? (doc.chunks.reduce((sum, chunk) => sum + chunk.relevance, 0) / doc.chunks.length).toFixed(1) : "0.0" }}%
            </p>
          </div>
        </div>

        <!-- Chunk List -->
        <div v-if="doc.expanded" class="px-4 pb-4">
          <div class="overflow-y-auto" :style="{ maxHeight: 'calc(100vh - 200px)' }">
            <ul class="divide-y divide-gray-200">
              <li v-for="chunk in doc.chunks" :key="chunk.id" class="flex items-center py-2 cursor-pointer" @click="chunk.selected = !chunk.selected">
                <div class="flex-1">
                  <p class="font-bold text-sm text-gray-900">Text:</p>
                  <p class="text-sm text-gray-800 whitespace-pre-wrap break-words">{{ chunk.text }}</p>
                  <p class="text-xs text-gray-500">Relevance: {{ chunk.relevance }}% | Tokens: {{ chunk.tokens }}</p>
                </div>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <!-- Scroll to Top Button -->
    <button v-if="showScrollTop" @click="scrollToTop" class="fixed bottom-4 right-4 rounded-full bg-indigo-600 p-3 text-white shadow-lg hover:bg-indigo-500 focus:outline-indigo-600">
      Scroll to top
    </button>
  </div>
  <div v-else>
    <p class="text-center text-gray-500">Loading session data...</p>
  </div>
</template>
