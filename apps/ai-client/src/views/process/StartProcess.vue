<script setup lang="ts">
import { ref, onMounted, inject, computed } from 'vue';
import { useRouter } from 'vue-router';
import {SessionService} from "../../service/SessionService.ts";
import {CollectionService} from "../../service/CollectionService.ts";

const sessionService = inject<SessionService>("sessionService");
const collectionService = inject<CollectionService>("collectionService");

if (!sessionService) {
  throw new Error("sessionService not provided");
}

if (!collectionService) {
  throw new Error("collectionService not provided");
}

const router = useRouter();

const title = ref('');
const currentKeyEvent = ref('');
const keyEvents = ref<string[]>([]);
const selectedCollection = ref<number | null>(null);
const collections = ref<Array<{ id: number; name: string; status: string; total_chunks: number }>>([]);
const selectedModel = ref('qwen3_14b');
const relevanceScore = ref(100);
const isSubmitting = ref(false);
const budgetAmount = ref(50);

const modelOptions = [
  {
    key: 'qwen3_14b',
    label: 'Qwen 3 14B',
    tagline: 'Balanced default for most runs',
    narrative:
      'Use this for most CRE runs. It gives the best balance of extraction quality, speed, and local fit on the current hardware.',
  },
  {
    key: 'deepseek_r1_14b',
    label: 'DeepSeek R1 14B',
    tagline: 'Reasoning-focused, slower but stronger on tricky passages',
    narrative:
      'Choose this when the texts are more ambiguous, technical, or logic-heavy and you want the model to spend more effort on reasoning.',
  },
  {
    key: 'qwen3_8b',
    label: 'Qwen 3 8B',
    tagline: 'Fast fallback for quicker turnaround',
    narrative:
      'Pick this when speed matters more than peak accuracy, for example during exploratory runs or when you want faster iteration on chunk selection.',
  },
] as const;

// **Fetch collections and filter only scanned ones**
const fetchCollections = async () => {
  try {
    const allCollections = await collectionService.getCollections();
    collections.value = allCollections.filter((col: any) => col.status === "scanned");
  } catch (error) {
    console.error("Error fetching collections:", error);
  }
};

onMounted(async () => {
  await fetchCollections();
  try {
    const result = await sessionService.getBudget();
    budgetAmount.value = result.budget;
  } catch (error) {
    console.error("Error fetching budget:", error);
  }
});

// **Handle key events**
const handleKeyEventKeyDown = (event: KeyboardEvent) => {
  if (event.key === 'Enter') {
    event.preventDefault();
    commitCurrentKeyEvent();
  }
};

const commitCurrentKeyEvent = () => {
  const trimmed = currentKeyEvent.value.trim();
  if (trimmed !== '' && !keyEvents.value.includes(trimmed)) {
    keyEvents.value.push(trimmed);
  }
  currentKeyEvent.value = '';
};

const modelInfo = {
  "qwen3_14b": {
    charToToken: 0.25,
    inputCostPer1000: 0,
    outputCostPer1000: 0,
    tokensPerSecond: 40,
    latencyPerChunk: 1.1
  },
  "deepseek_r1_14b": {
    charToToken: 0.3,
    inputCostPer1000: 0,
    outputCostPer1000: 0,
    tokensPerSecond: 22,
    latencyPerChunk: 1.8
  },
  "qwen3_8b": {
    charToToken: 0.25,
    inputCostPer1000: 0,
    outputCostPer1000: 0,
    tokensPerSecond: 60,
    latencyPerChunk: 0.7
  }
};

const selectedModelOption = computed(
  () => modelOptions.find((model) => model.key === selectedModel.value) ?? modelOptions[0]
);

// **Model informatie**
// const modelInfo = {
//   'gpt_4o': { charToToken: 0.25, inputCostPer1000: 0.005, outputCostPer1000: 0.015, tokensPerSecond: 62, latencyPerChunk: 0.67 },
//   'claude_3.7': { charToToken: 0.29, inputCostPer1000: 0.003, outputCostPer1000: 0.015, tokensPerSecond: 58, latencyPerChunk: 1.4 },
//   'deepseek_r1': { charToToken: 0.3, inputCostPer1000: 0.0007, outputCostPer1000: 0.0025, tokensPerSecond: 25, latencyPerChunk: 1.58 },
//   'gemini_2_pro': { charToToken: 0.25, inputCostPer1000: 0.0001, outputCostPer1000: 0.0004, tokensPerSecond: 161, latencyPerChunk: 0.5 }
// };

// **Dynamische berekening op basis van relevanceScore**
const costAndTime = computed(() => {
  if (!selectedCollection.value || !selectedModel.value) {
    return { cost: 0, time: "0:00:00" };
  }

  const model = modelInfo[selectedModel.value as keyof typeof modelInfo];

  if (!model) {
    console.error('Invalid model type');
    return { cost: 0, time: "0:00:00" };
  }

  const selectedColl = collections.value.find(col => col.id === selectedCollection.value);
  if (!selectedColl) return { cost: 0, time: "0:00:00" };

  // 🔥 **RelevanceScore toepassen: Neem alleen x% van de total chunks**
  const chunksToUse = Math.ceil((relevanceScore.value / 100) * selectedColl.total_chunks);
  const charsPerChunk = 1000;
  const outputChars = 500;

  const totalChars = chunksToUse * charsPerChunk;
  const totalTokens = totalChars * model.charToToken;
  const outputTokens = outputChars * chunksToUse * model.charToToken;

  const inputCost = (totalTokens / 1000) * model.inputCostPer1000;
  const outputCost = (outputTokens / 1000) * model.outputCostPer1000;
  const totalCost = inputCost + outputCost;

  const totalLatency = chunksToUse * model.latencyPerChunk;
  const totalTimeSeconds = (totalTokens + outputTokens) / model.tokensPerSecond + totalLatency;

  // **Omzetten naar uren, minuten en seconden**
  const hours = Math.floor(totalTimeSeconds / 3600);
  const minutes = Math.floor((totalTimeSeconds % 3600) / 60);
  const seconds = Math.floor(totalTimeSeconds % 60);

  return {
    cost: totalCost.toFixed(2),
    time: `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
  };
});

// **Save session and redirect user**
const saveSettings = async () => {
  commitCurrentKeyEvent();

  const missingFields: string[] = [];

  if (!title.value.trim()) {
    missingFields.push("title");
  }

  if (!selectedCollection.value) {
    missingFields.push("collection");
  }

  if (!selectedModel.value) {
    missingFields.push("model");
  }

  if (keyEvents.value.length === 0) {
    missingFields.push("at least one key event");
  }

  if (missingFields.length > 0) {
    alert(`Please fill in: ${missingFields.join(", ")}.`);
    return;
  }

  // @ts-ignore
  const estimatedCost = parseFloat(costAndTime.value.cost);

  if (estimatedCost > budgetAmount.value) {
    alert("The estimated cost exceeds the remaining shared budget. Please adjust your settings.");
    return;
  }

  isSubmitting.value = true;
  try {
    const session = await sessionService.create(
        1,
        Number(selectedCollection.value),
        title.value.trim(),
        keyEvents.value,
        selectedModel.value,
        relevanceScore.value
    );

    router.push({ name: 'ViewProcess', params: { id: session.id } });
  } catch (error: unknown) {
    console.error("Error creating session:", error);
    const message = error instanceof Error ? error.message : "An error occurred while creating the session.";
    alert(message);
  } finally {
    isSubmitting.value = false;
  }
};
</script>

<template>
  <div class="bg-yellow-100 border-l-4 border-yellow-500 text-yellow-700 p-4 mb-4" role="alert">
    <p class="font-bold">Shared budget notice</p>
    <p>
      Please be mindful when starting a causal relation extraction process. The remaining shared budget is <strong>${{ budgetAmount }}</strong>.
      Since usage is not tracked per user, we kindly ask you to coordinate with your colleagues to ensure fair and efficient use of resources.
    </p>
  </div>

  <form @submit.prevent="saveSettings">
    <div class="grid grid-cols-1 md:grid-cols-2 gap-8 items-start">
      <!-- Left Card: Input Fields and Schedule Button -->
      <div class="bg-white shadow-sm ring-1 ring-gray-900/5 sm:rounded-xl">
        <div class="p-6 space-y-8">
          <!-- Header with full-width border -->
          <div class="-mx-6 border-b border-gray-900/10 pb-6">
            <div class="px-6">
              <h2 class="text-base font-semibold text-gray-900">Causal Extraction Settings</h2>
              <p class="mt-1 text-sm text-gray-600">
                Configure the parameters for extracting and visualizing causal relationships.
              </p>
            </div>
          </div>
          <!-- Title Input -->
          <div>
            <label for="title" class="block text-sm font-medium text-gray-900">Title</label>
            <div class="mt-2">
              <input
                  v-model="title"
                  type="text"
                  id="title"
                  class="block w-full rounded-md bg-white px-3 py-1.5 text-base text-gray-900 outline outline-1 outline-gray-300 placeholder:text-gray-400 focus:outline-indigo-600 sm:text-sm"
                  placeholder="Enter a title"
                  required
              />
            </div>
          </div>
          <!-- Key Events Input -->
          <div>
            <label for="keyEventInput" class="block text-sm font-medium text-gray-900">Key Events</label>
            <p class="mt-1 text-sm text-gray-600">
              Please provide a short detailed description of the key event. The key events allow the AI to determine what text is relevant and what text is not relevant for your research.
            </p>
            <div class="mt-2">
              <input
                  v-model="currentKeyEvent"
                  id="keyEventInput"
                  type="text"
                  @keydown="handleKeyEventKeyDown"
                  class="block w-full rounded-md bg-white px-3 py-1.5 text-base text-gray-900 outline outline-1 outline-gray-300 placeholder:text-gray-400 focus:outline-indigo-600 sm:text-sm"
                  placeholder="Enter a key event and press Enter. Example key event: MCT8, cognition and motor function"
              />
            </div>
            <!-- Real-time list of key events -->
            <ul class="mt-2 list-disc pl-5 text-sm text-gray-600">
              <li v-for="(event, index) in keyEvents" :key="index">{{ event }}</li>
            </ul>
          </div>
          <!-- Collection and Model Selection -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <!-- Collection Selection -->
            <div>
              <label for="collection" class="block text-sm font-medium text-gray-900">Select Collection</label>
              <div class="mt-2">
                <select
                    v-model.number="selectedCollection"
                    id="collection"
                    class="block w-full rounded-md bg-white px-3 py-1.5 text-base text-gray-900 outline outline-1 outline-gray-300 focus:outline-indigo-600 sm:text-sm"
                >
                  <option value="" disabled>Select a collection</option>
                  <option v-for="(collection, index) in collections" :key="index" :value="collection.id">
                    {{ collection.name }}
                  </option>
                </select>
              </div>
              <p v-if="collections.length === 0" class="text-sm text-gray-500 mt-2">
                No scanned collections available. Please scan a collection first.
              </p>
            </div>
            <!-- Model Selection -->
            <div>
              <label for="model" class="block text-sm font-medium text-gray-900">Select Model</label>
              <div class="mt-2">
                <select
                    v-model="selectedModel"
                    id="model"
                    class="block w-full rounded-md bg-white px-3 py-1.5 text-base text-gray-900 outline outline-1 outline-gray-300 focus:outline-indigo-600 sm:text-sm"
                >
                  <option value="" disabled>Select a model</option>
                  <option v-for="model in modelOptions" :key="model.key" :value="model.key">
                    {{ model.label }}
                  </option>
                </select>
              </div>
              <div class="mt-3 rounded-lg border border-gray-200 bg-gray-50 p-3">
                <p class="text-sm font-medium text-gray-900">{{ selectedModelOption.label }}</p>
                <p class="mt-1 text-sm text-gray-700">{{ selectedModelOption.tagline }}</p>
                <p class="mt-2 text-sm text-gray-600">{{ selectedModelOption.narrative }}</p>
              </div>
            </div>
          </div>
          <!-- Relevance Score Slider -->
          <div>
            <label for="relevanceScore" class="block text-sm font-medium text-gray-900">Relevance Score Threshold (%)</label>
            <p class="mt-1 text-sm text-gray-600">
              The relevance score of chunks is calculated. By changing this slider you determine what top x% relevance of chunks are used by the model.
              Example: If you set the slider to top 20%, only the top 20% of the most relevant chunks will be considered.
            </p>
            <div class="mt-2">
              <input
                  v-model="relevanceScore"
                  type="range"
                  id="relevanceScore"
                  min="1"
                  max="100"
                  class="w-full"
              />
              <div class="mt-1 text-sm text-gray-600">
                <span>{{ relevanceScore }}%</span>
              </div>
            </div>
          </div>
          <!-- Schedule Button: Positioned under the form in the left card -->
          <button
              type="submit"
              :disabled="isSubmitting"
              class="w-full rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus:outline-indigo-600 flex items-center justify-center"
          >
            <svg v-if="isSubmitting" class="animate-spin h-4 w-4 mr-2 text-white" viewBox="0 0 24 24"
                 fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor"
                      stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor"
                    d="M4 12a8 8 0 018-8v8H4z"></path>
            </svg>
            Schedule
          </button>
        </div>
      </div>

      <!-- Right Card: Estimation Visualization -->
      <div>
        <div class="bg-white shadow-sm ring-1 ring-gray-900/5 sm:rounded-xl mb-8">
          <div class="p-6 space-y-6">
            <h3 class="text-base font-semibold text-gray-900">Estimation</h3>
            <div class="grid grid-cols-1 gap-4">
              <!-- Estimated Cost Card -->
              <div class="bg-gradient-to-r from-red-400 to-red-600 text-white p-6 rounded-lg shadow-lg flex items-center justify-between">
                <div>
                  <p class="text-lg font-medium">Estimated Cost</p>
                  <p class="text-2xl font-bold">${{ costAndTime.cost }}</p>
                </div>
                <div>
                  <!-- Creative dollar sign icon -->
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4zm0 10v2m0-16V2" />
                  </svg>
                </div>
              </div>
              <!-- Estimated Time Card -->
              <div class="bg-gradient-to-r from-green-400 to-green-600 text-white p-6 rounded-lg shadow-lg flex items-center justify-between">
                <div>
                  <p class="text-lg font-medium">Estimated Time</p>
                  <p class="text-2xl font-bold">{{ costAndTime.time }} hrs</p>
                </div>
                <div>
                  <!-- Creative clock icon -->
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="bg-white shadow-sm ring-1 ring-gray-900/5 sm:rounded-xl">
          <div class="p-6 space-y-4">
            <h3 class="text-base font-semibold text-gray-900">What model to choose?</h3>
            <p class="text-sm text-gray-700">
              Depending on your goals, you can choose from the following models:
            </p>
            <ul class="list-disc list-inside text-sm text-gray-700 space-y-1">
              <li>
                <strong>GPT-OSS</strong>: Best option for a <em>local, self-hosted workflow</em>. It avoids per-call cloud costs and keeps the extraction path on your own infrastructure, though throughput depends on the local Docker model service.
              </li>
              <li>
                <strong>Gemini Flash 2</strong>: Best option if you want <em>fast and cheap</em> results. Extremely affordable and fast, making it ideal for quick analyses with limited budget.
              </li>
              <li>
                <strong>GPT-4o</strong>: Offers the <em>best performance</em> and is relatively fast, but it's also <strong>significantly more expensive</strong> than the other options. Recommended only when top accuracy is essential.
              </li>
              <li>
                <strong>Deepseek V3</strong>: Delivers <em>strong performance</em> with the <em>best price-to-quality ratio</em>, though it's slower. A great choice for cost-efficient, deeper analyses when time is less critical.
              </li>
            </ul>
            <p class="text-sm text-gray-600">
              ⚠️ Note: GPT-4o may exceed your session budget quickly. GPT-OSS estimates assume a local model service and therefore show no API cost.
            </p>
          </div>
        </div>
      </div>
    </div>
  </form>
</template>

<style scoped>
/* Add any additional styling if needed */
</style>
