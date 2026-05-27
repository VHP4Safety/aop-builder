<script setup lang="ts">
import { inject, ref } from 'vue';
import router from "../routing/router.ts";
import {CollectionService} from "../service/CollectionService.ts";

const collectionService = inject<CollectionService>("collectionService");

if (!collectionService) {
  throw new Error("collectionService is not provided");
}

const title = ref('');
const description = ref('');
const uploadedFiles = ref<File[]>([]);
const showWarningModal = ref(false);

// Nieuwe reactive variabelen voor de uploadprogressie
const uploadProgress = ref<number>(0); // Percentage (0-100)
const isUploading = ref(false);

const MAX_FILES = 5;
const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;

const handleFileUpload = (event: Event) => {
  const target = event.target as HTMLInputElement;
  if (!target.files) return;

  const selectedFiles = Array.from(target.files);

  if (uploadedFiles.value.length + selectedFiles.length > MAX_FILES) {
    alert(`You can upload a maximum of ${MAX_FILES} documents per collection.`);
    return;
  }

  for (const file of selectedFiles) {
    if (file.type !== 'application/pdf') {
      alert('Only PDF files are allowed.');
      continue;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      alert(`"${file.name}" is larger than 10MB and cannot be uploaded.`);
      continue;
    }

    if (file.type === 'application/pdf') {
      uploadedFiles.value.push(file);
    }
  }

  showWarningModal.value = true;
};

const closeWarningModal = () => {
  showWarningModal.value = false;
};

const goToExplainabilityModule = () => {
  window.open('/explainability', '_blank');
};

const saveCollection = async () => {
  if (!title.value || !description.value) {
    alert('Please fill in all required fields.');
    return;
  }

  isUploading.value = true;
  uploadProgress.value = 0;

  try {
    // Eerst de collectie aanmaken (zonder de bestanden)
    const collectionData = {
      title: title.value,
      description: description.value
    };
    const createResponse = await collectionService.create(collectionData.title, collectionData.description);
    const createdCollectionId = createResponse.id;

    // Bereken het totaal aantal bestanden dat geüpload moet worden
    const totalFiles = uploadedFiles.value.length;

    // Upload de documenten één voor één
    for (let i = 0; i < totalFiles; i++) {
      const file = uploadedFiles.value[i];
      const uploadResponse = await collectionService.uploadPdfDocument(createdCollectionId, file);
      console.log(`Uploaded ${file.name}:`, uploadResponse);

      // Update de progressie
      uploadProgress.value = Math.floor(((i + 1) / totalFiles) * 100);
    }

    alert('Collection and all documents successfully created!');

    // Reset de velden
    title.value = '';
    description.value = '';
    uploadedFiles.value = [];
    uploadProgress.value = 0;
    isUploading.value = false;

    await router.push({ name: 'Library' });
  } catch (error) {
    console.error('Error saving collection or uploading files:', error);
    const message = error instanceof Error ? error.message : 'Er is een fout opgetreden.';
    alert(message);
    isUploading.value = false;
  }
};
</script>

<template>
  <div class="bg-yellow-100 border-l-4 border-yellow-500 text-yellow-700 p-4 mb-4" role="alert">
    <p class="font-bold">Upload limit notice</p>
    <p>You can upload a maximum of 5 documents per collection due to system constraints.</p>
  </div>

  <form class="bg-white shadow-sm ring-1 ring-gray-900/5 sm:rounded-xl md:col-span-2" @submit.prevent="saveCollection">
    <div class="px-4 py-6 sm:p-8">
      <div class="space-y-12">
        <div class="border-b border-gray-900/10 pb-12">
          <h2 class="text-base font-semibold text-gray-900">Create Collection</h2>
          <p class="mt-1 text-sm text-gray-600">
            Add a name, a short description, and documents to your collection.
          </p>

          <div class="mt-10 grid grid-cols-1 gap-x-6 gap-y-8 sm:grid-cols-6">
            <div class="sm:col-span-3">
              <label for="title" class="block text-sm font-medium text-gray-900">Title</label>
              <div class="mt-2">
                <input
                    v-model="title"
                    type="text"
                    id="title"
                    class="block w-full rounded-md bg-white px-3 py-1.5 text-base text-gray-900 outline outline-1 outline-gray-300 placeholder:text-gray-400 focus:outline-indigo-600 sm:text-sm"
                    placeholder="Name of the collection"
                    required
                />
              </div>
            </div>

            <div class="col-span-full">
              <label for="description" class="block text-sm font-medium text-gray-900">Description</label>
              <div class="mt-2">
                <textarea
                    v-model="description"
                    id="description"
                    rows="3"
                    class="block w-full rounded-md bg-white px-3 py-1.5 text-base text-gray-900 outline outline-1 outline-gray-300 placeholder:text-gray-400 focus:outline-indigo-600 sm:text-sm"
                    placeholder="Short description of the collection"
                    required
                ></textarea>
              </div>
            </div>

            <div class="col-span-full">
              <label class="block text-sm font-medium text-gray-900">Upload documents</label>
              <div class="mt-2 flex justify-center rounded-lg border border-dashed border-gray-900/25 px-6 py-10">
                <div class="text-center">
                  <div class="mt-4 flex text-sm text-gray-600">
                    <label for="file-upload"
                           class="relative cursor-pointer rounded-md bg-white font-semibold text-indigo-600 hover:text-indigo-500">
                      <span>Choose files</span>
                      <input
                          id="file-upload"
                          type="file"
                          multiple
                          class="sr-only"
                          @change="handleFileUpload"
                      />
                    </label>
                    <p class="pl-1">or drag them here</p>
                  </div>
                  <p class="text-xs text-gray-600">Only PDF files, maximum 10MB per file</p>
                </div>
              </div>

              <div v-if="uploadedFiles.length" class="mt-6">
                <h3 class="text-sm font-semibold text-gray-900">Uploaded documents:</h3>
                <ul class="mt-2 list-disc pl-5 text-sm text-gray-600">
                  <li v-for="(file, index) in uploadedFiles" :key="index">{{ file.name }}</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Toon progressie-indicator wanneer er geüpload wordt -->
      <div v-if="isUploading" class="mt-4">
        <p class="text-sm text-gray-700">Uploading documents: {{ uploadProgress }}% complete</p>
        <div class="w-full bg-gray-200 rounded">
          <div
              class="bg-indigo-600 text-xs leading-none py-1 text-center text-white rounded"
              :style="{ width: uploadProgress + '%' }"
          >
            {{ uploadProgress }}%
          </div>
        </div>
      </div>

      <div class="mt-6 flex items-center justify-end gap-x-6">
        <router-link :to="{ name: 'Library' }" type="button" class="text-sm font-semibold text-gray-900">
          Back to my library
        </router-link>
        <button type="submit"
                class="rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus:outline-indigo-600">
          Save
        </button>
      </div>
    </div>

    <!-- Modal for warning -->
    <div v-if="showWarningModal" class="fixed z-10 inset-0 overflow-y-auto">
      <div class="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
        <div class="fixed inset-0 transition-opacity" aria-hidden="true">
          <div class="absolute inset-0 bg-gray-500 opacity-75"></div>
        </div>
        <span class="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>
        <div class="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
          <div class="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
            <div class="sm:flex sm:items-start">
              <div class="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-red-100 sm:mx-0 sm:h-10 sm:w-10">
                <svg class="h-6 w-6 text-red-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m0-4h.01M12 2a10 10 0 100 20 10 10 0 000-20z" />
                </svg>
              </div>
              <div class="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left">
                <h3 class="text-lg leading-6 font-medium text-gray-900" id="modal-title">
                  Privacy Warning
                </h3>
                <div class="mt-2">
                  <p class="text-sm text-gray-500">
                    Be careful when uploading privacy-sensitive papers, as we use cloud models for processing.
                  </p>
                </div>
              </div>
            </div>
          </div>
          <div class="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
            <button @click="closeWarningModal" type="button" class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-indigo-600 text-base font-medium text-white hover:bg-indigo-500 focus:outline-none sm:ml-3 sm:w-auto sm:text-sm">
              OK
            </button>
            <button @click="goToExplainabilityModule" type="button" class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm">
              Learn More
            </button>
          </div>
        </div>
      </div>
    </div>
  </form>
</template>

<style scoped>
/* Voeg hier eventuele extra styling toe */
</style>
