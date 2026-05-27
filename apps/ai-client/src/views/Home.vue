<template>
  <div class="grid grid-cols-1 gap-6">
    <!-- Main Content Only -->
    <div>
      <div v-if="sessions.length === 0">
        <div class="mx-auto max-w-lg">
          <div class="bg-white shadow-sm ring-1 ring-gray-900/5 sm:rounded-lg">
            <div class="p-9">
              <h2 class="text-base font-semibold text-gray-900">Start your first analysis</h2>
              <p class="mt-1 text-sm text-gray-500">
                Analyze toxicological literature to extract and visualize causal relationships. Start by uploading
                documents, launching a causal relation extraction (CRE) process, or learn more about how the system works.
              </p>
              <ul role="list" class="mt-6 divide-y divide-gray-200 border-b border-t border-gray-200">
                <li v-for="(item, itemIdx) in items" :key="itemIdx">
                  <div class="group relative flex items-start space-x-3 py-4">
                    <div class="shrink-0">
                      <span :class="[item.iconColor, 'inline-flex size-10 items-center justify-center rounded-lg']">
                        <component :is="item.icon" class="size-6 text-white" aria-hidden="true" />
                      </span>
                    </div>
                    <div class="min-w-0 flex-1">
                      <div class="text-sm font-medium text-gray-900">
                        <router-link :to="{ name: item.href }">
                          <span class="absolute inset-0" aria-hidden="true" />
                          {{ item.name }}
                        </router-link>
                      </div>
                      <p class="text-sm text-gray-500">{{ item.description }}</p>
                    </div>
                    <div class="shrink-0 self-center">
                      <ChevronRightIcon class="size-5 text-gray-400 group-hover:text-gray-500" aria-hidden="true" />
                    </div>
                  </div>
                </li>
              </ul>
              <div class="mt-6 flex">
                <a
                    href="https://www.hu.nl/onderzoek/projecten/vhp4safety"
                    target="_blank"
                    class="text-sm font-medium text-indigo-600 hover:text-indigo-500"
                >
                  Or read more about VHP4Safety
                  <span aria-hidden="true"> &rarr;</span>
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>

      <ul v-else class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3" role="list">
        <li
            v-for="session in sessions"
            :key="session.id"
            class="col-span-1 divide-y divide-gray-200 rounded-lg bg-white shadow"
        >
          <div class="flex w-full items-center justify-between space-x-6 p-6">
            <div class="flex-1 truncate">
              <div class="flex items-center space-x-3">
                <h3 class="truncate text-sm font-medium text-gray-900">{{ session.title }}</h3>
                <span
                    class="inline-flex shrink-0 items-center rounded-full px-2 py-1 text-xs font-medium"
                    :class="{
                    'bg-green-100 text-green-800': session.status === 'finished',
                    'bg-yellow-100 text-yellow-800': session.status === 'extracting' || session.status === 'enriching',
                    'bg-purple-100 text-purple-800': session.status === 'pre_processing',
                    'bg-blue-100 text-blue-800': session.status === 'chunking' || session.status === 'queued' || session.status === 'starting',
                    'bg-red-100 text-red-800': session.status === 'canceled',
                  }"
                >
                  {{ statusLabels[session.status] ?? session.status.replace('_', ' ') }}
                </span>
                <span
                    v-if="isStaleSession(session)"
                    class="inline-flex shrink-0 items-center rounded-full bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700 ring-1 ring-inset ring-amber-200"
                >
                  stale
                </span>
              </div>
              <p class="mt-1 truncate text-sm text-gray-500">
                Key Events: {{ session.key_events.join(', ') || 'No key events' }}
              </p>
            </div>
          </div>
          <div class="border-t border-gray-200 px-4 py-4">
            <div class="flex flex-wrap gap-2">
              <router-link
                  :to="{ name: 'ViewProcess', params: { id: session.id } }"
                  class="inline-flex flex-1 items-center justify-center gap-x-2 rounded-md bg-gray-900 px-3 py-2 text-sm font-semibold text-white hover:bg-gray-800"
              >
                <ArrowRightStartOnRectangleIcon aria-hidden="true" class="size-5 text-white" />
                Open
              </router-link>
              <button
                  v-if="canResubmit(session)"
                  type="button"
                  :disabled="Boolean(busySessionIds[session.id])"
                  @click="resubmitSession(session)"
                  class="inline-flex items-center justify-center rounded-md bg-amber-100 px-3 py-2 text-sm font-semibold text-amber-800 hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {{ busySessionIds[session.id] === 'resubmit' ? 'Restarting...' : resubmitLabel(session) }}
              </button>
              <button
                  type="button"
                  :disabled="Boolean(busySessionIds[session.id])"
                  @click="removeSession(session.id)"
                  class="inline-flex items-center justify-center rounded-md bg-red-50 px-3 py-2 text-sm font-semibold text-red-700 hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {{ busySessionIds[session.id] === 'remove' ? 'Removing...' : 'Remove' }}
              </button>
            </div>
          </div>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, inject } from 'vue';
import { useRouter } from 'vue-router';
import {
  ArrowRightStartOnRectangleIcon,
  ChevronRightIcon,
  DocumentPlusIcon,
  BoltIcon,
  InformationCircleIcon,
} from '@heroicons/vue/20/solid';
import { SessionService } from '../service/SessionService.ts';
import type { Session } from '../models/Result.ts';

const STALE_SESSION_MINUTES = 10;

const sessionService = inject<SessionService>('sessionService');
if (!sessionService) throw new Error('sessionService not provided');
const router = useRouter();

const sessions = ref<Session[]>([]);
const busySessionIds = ref<Record<number, 'resubmit' | 'remove' | undefined>>({});
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

const items = [
  {
    name: 'Create a document collection',
    description: 'Upload toxicological PDFs to prepare them for analysis.',
    href: 'Library',
    iconColor: 'bg-indigo-500',
    icon: DocumentPlusIcon,
  },
  {
    name: 'Run causal relation extraction (CRE)',
    description: 'Use AI to automatically extract causal links from toxicological texts.',
    href: 'StartProcess',
    iconColor: 'bg-green-500',
    icon: BoltIcon,
  },
  {
    name: 'How does it work?',
    description: 'Learn how the system processes documents and finds causal relationships.',
    href: 'ExplainabilityModule',
    iconColor: 'bg-blue-500',
    icon: InformationCircleIcon,
  },
];

const fetchSessions = async () => {
  try {
    sessions.value = await sessionService.getSessions();
  } catch (error) {
    console.error('Error fetching sessions:', error);
  }
};

const getSessionActivityTimestamp = (session: Session) => {
  if (session.status === 'extracting' && session.telemetry?.updated_at) {
    return session.telemetry.updated_at;
  }

  return session.updated_at;
};

const isStaleSession = (session: Session) => {
  if (!['waiting', 'extracting', 'enriching'].includes(session.status)) {
    return false;
  }

  const timestamp = getSessionActivityTimestamp(session);
  if (!timestamp) {
    return false;
  }

  const lastActivity = new Date(timestamp).getTime();
  if (Number.isNaN(lastActivity)) {
    return false;
  }

  return Date.now() - lastActivity >= STALE_SESSION_MINUTES * 60 * 1000;
};

const canResubmit = (session: Session) => session.status === 'canceled' || isStaleSession(session);

const resubmitLabel = (session: Session) => (session.status === 'canceled' ? 'Resubmit' : 'Restart');

const resubmitSession = async (session: Session) => {
  const sessionId = session.id;
  const force = isStaleSession(session);

  try {
    busySessionIds.value[sessionId] = 'resubmit';
    await sessionService.resubmit(sessionId, force);
    await fetchSessions();
    await router.push({ name: 'ViewProcess', params: { id: sessionId } });
  } catch (error: any) {
    window.alert(error.message || 'An error occurred while resubmitting the session.');
  } finally {
    delete busySessionIds.value[sessionId];
  }
};

const removeSession = async (sessionId: number) => {
  const confirmed = window.confirm('Remove this session and its stored results? This cannot be undone.');
  if (!confirmed) {
    return;
  }

  try {
    busySessionIds.value[sessionId] = 'remove';
    await sessionService.remove(sessionId);
    sessions.value = sessions.value.filter((session) => session.id !== sessionId);
  } catch (error: any) {
    window.alert(error.message || 'An error occurred while deleting the session.');
  } finally {
    delete busySessionIds.value[sessionId];
  }
};

onMounted(fetchSessions);
</script>
