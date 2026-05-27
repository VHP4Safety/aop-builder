<script setup lang="ts">
import {computed, inject, ref, watchEffect} from 'vue';
import { useRoute } from 'vue-router';
import { Menu, MenuButton, MenuItem, MenuItems, Dialog, DialogPanel, TransitionChild, TransitionRoot } from '@headlessui/vue'
import { ChevronDownIcon, InformationCircleIcon } from '@heroicons/vue/20/solid'
import {
  Bars3Icon,
  Cog6ToothIcon,
  FolderIcon,
  HomeIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'
import { PlusIcon } from '@heroicons/vue/20/solid'
import router from "../routing/router.ts";
import store from "../store";
import {AuthService} from "../service/AuthService.ts";
// import logoRIVM from "../assets/RIVM-logo-white.png"
import logo from "../assets/logo-aop-builder.png"
import {User} from "../models/User.ts";

const authService = inject<AuthService>("authService");

if (!authService) {
  throw new Error('authService is not provided')
}

const route = useRoute();
const sidebarOpen = ref(false)

const navigation = ref([
  { name: 'My overview', routeName: 'Home', icon: HomeIcon, current: true },
  { name: 'My library', routeName: 'Library', icon: FolderIcon, current: false },
])

interface UserWithImage extends User {
  imageUri: string;
}

const authenticatedUser = computed<UserWithImage>(() => {
  const user = (store.state as { auth?: { user: User | null } }).auth?.user ?? null;

  return {
    id: user?.id ?? null,
    username: user?.username ?? 'User',
    imageUri: 'https://static.vecteezy.com/system/resources/previews/009/292/244/non_2x/default-avatar-icon-of-social-media-user-vector.jpg'
  };
});

const updateNavigation = () => {
  const currentRouteName = route.name;

  navigation.value.forEach(item => {
    item.current = item.routeName === currentRouteName;
  });

  sidebarOpen.value = false
};

const logout = async () => {
  await authService.logout();
  await store.dispatch('auth/signOut')

  return router.push({ name: 'Login' })
}

// Watch for route changes and update navigation
watchEffect(() => {
  updateNavigation();
});

const createAOPModel = ref(false)
const sessionTitle = ref("")
const keyEvents = ref<string[]>([]);
const newKeyEvent = ref<string>('')
const selectedLibrary = ref("");
const libraries = ref(["Library 1", "Library 2", "Library 3"]);

const addKeyEvent = () => {
  if (newKeyEvent.value.trim()) {
    keyEvents.value.push(newKeyEvent.value.trim());
    newKeyEvent.value = "";
  }
};

const startProcess = () => {
  alert(`Key Events: ${keyEvents.value.join(", ")}\nLibrary: ${selectedLibrary.value}`);
  createAOPModel.value = false
};
</script>

<template>
  <div>
    <TransitionRoot as="template" :show="sidebarOpen">
      <Dialog class="relative z-50 lg:hidden" @close="sidebarOpen = false">
        <TransitionChild as="template" enter="transition-opacity ease-linear duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="transition-opacity ease-linear duration-300" leave-from="opacity-100" leave-to="opacity-0">
          <div class="fixed inset-0 bg-gray-900/80" />
        </TransitionChild>

        <div class="fixed inset-0 flex">
          <TransitionChild as="template" enter="transition ease-in-out duration-300 transform" enter-from="-translate-x-full" enter-to="translate-x-0" leave="transition ease-in-out duration-300 transform" leave-from="translate-x-0" leave-to="-translate-x-full">
            <DialogPanel class="relative mr-16 flex w-full max-w-xs flex-1">
              <TransitionChild as="template" enter="ease-in-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in-out duration-300" leave-from="opacity-100" leave-to="opacity-0">
                <div class="absolute left-full top-0 flex w-16 justify-center pt-5">
                  <button type="button" class="-m-2.5 p-2.5" @click="sidebarOpen = false">
                    <span class="sr-only">Close sidebar</span>
                    <XMarkIcon class="size-6 text-white" aria-hidden="true" />
                  </button>
                </div>
              </TransitionChild>
              <div class="flex grow flex-col gap-y-5 overflow-y-auto bg-gray-900 px-6 pb-4 ring-1 ring-white/10">
                <div class="flex h-16 shrink-0 items-center">
                  <img class="h-8 w-auto" :src="logo" alt="AOP-Builder" />
                </div>
                <nav class="flex flex-1 flex-col">
                  <ul role="list" class="flex flex-1 flex-col gap-y-7">
                    <li>
                      <ul role="list" class="-mx-2 space-y-1">
                        <li v-for="item in navigation" :key="item.name">
                          <router-link :to="{ name: item.routeName }" :class="[item.current ? 'bg-gray-800 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white', 'group flex gap-x-3 rounded-md p-2 text-sm/6 font-semibold']">
                            <component :is="item.icon" class="size-6 shrink-0" aria-hidden="true" />
                            {{ item.name }}
                          </router-link>
                        </li>
                      </ul>
                    </li>
                    <li class="mt-auto">
                      <router-link :to="{ name: 'ExplainabilityModule' }" class="group -mx-2 flex gap-x-3 rounded-md p-2 text-sm/6 font-semibold text-gray-400 hover:bg-gray-800 hover:text-white">
                        <InformationCircleIcon class="size-6 shrink-0" aria-hidden="true" />
                        How does it work?
                      </router-link>
                    </li>
                    <li class="mt-1">
                      <a href="#" class="group -mx-2 flex gap-x-3 rounded-md p-2 text-sm/6 font-semibold text-gray-400 hover:bg-gray-800 hover:text-white">
                        <Cog6ToothIcon class="size-6 shrink-0" aria-hidden="true" />
                        Settings
                      </a>
                    </li>
                  </ul>
                </nav>
              </div>
            </DialogPanel>
          </TransitionChild>
        </div>
      </Dialog>
    </TransitionRoot>
    <div class="hidden lg:fixed lg:inset-y-0 lg:z-50 lg:flex lg:w-72 lg:flex-col">
      <div class="flex grow flex-col gap-y-5 overflow-y-auto bg-gray-900 px-6 py-4">
        <div class="flex shrink-0 items-center bg-white rounded-xl">
          <img class="w-auto" :src="logo" alt="AOP-Builder" />
        </div>
        <nav class="flex flex-1 flex-col">
          <ul role="list" class="flex flex-1 flex-col gap-y-7">
            <li>
              <ul role="list" class="-mx-2 space-y-1">
                <li v-for="item in navigation" :key="item.name">
                  <router-link :to="{ name: item.routeName }" :class="[item.current ? 'bg-gray-800 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white', 'group flex gap-x-3 rounded-md p-2 text-sm/6 font-semibold']">
                    <component :is="item.icon" class="size-6 shrink-0" aria-hidden="true" />
                    {{ item.name }}
                  </router-link>
                </li>
              </ul>
            </li>
            <ul class="mt-auto">
              <li>
                <router-link :to="{ name: 'ExplainabilityModule' }" class="group -mx-2 flex gap-x-3 rounded-md p-2 text-sm/6 font-semibold text-gray-400 hover:bg-gray-800 hover:text-white">
                  <InformationCircleIcon class="size-6 shrink-0" aria-hidden="true" />
                  How does it work?
                </router-link>
              </li>
              <li class="mt-1">
                <a href="#" class="group -mx-2 flex gap-x-3 rounded-md p-2 text-sm/6 font-semibold text-gray-400 hover:bg-gray-800 hover:text-white">
                  <Cog6ToothIcon class="size-6 shrink-0" aria-hidden="true" />
                  Settings
                </a>
              </li>
            </ul>
          </ul>
        </nav>
      </div>
    </div>
  </div>

  <div class="lg:pl-72">
    <div class="sticky top-0 z-40 flex h-16 shrink-0 items-center gap-x-4 border-b border-gray-200 bg-white px-4 shadow-sm sm:gap-x-6 sm:px-6 lg:px-8">
      <button type="button" class="-m-2.5 p-2.5 text-gray-700 lg:hidden" @click="sidebarOpen = true">
        <span class="sr-only">Open sidebar</span>
        <Bars3Icon class="size-6" aria-hidden="true" />
      </button>

      <div class="h-6 w-px bg-gray-900/10 lg:hidden" aria-hidden="true"></div>

      <div class="flex flex-1 justify-end items-center gap-x-4 lg:gap-x-6">

        <router-link :to="{ name: 'StartProcess' }"
            class="inline-flex items-center gap-x-1.5 rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600">
            Start CRE process
          <PlusIcon class="-mr-0.5 size-5" aria-hidden="true" />
        </router-link>

        <div class="hidden lg:block lg:h-6 lg:w-px lg:bg-gray-900/10" aria-hidden="true"></div>

        <Menu as="div" class="relative">
          <MenuButton class="-m-1.5 flex items-center p-1.5">
            <span class="sr-only">Open user menu</span>
            <img class="size-8 rounded-full bg-gray-50" :src="authenticatedUser.imageUri" alt="" />
            <span class="hidden lg:flex lg:items-center">
              <span class="ml-4 text-sm/6 font-semibold text-gray-900" aria-hidden="true">{{ authenticatedUser.username }}</span>
              <ChevronDownIcon class="ml-2 size-5 text-gray-400" aria-hidden="true" />
            </span>
          </MenuButton>

          <TransitionRoot as="template" :show="createAOPModel">
            <Dialog class="relative z-10" @close="createAOPModel = false">
              <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
                <div class="fixed inset-0 bg-gray-500/75 transition-opacity" />
              </TransitionChild>

              <div class="fixed inset-0 z-10 w-screen overflow-y-auto">
                <div class="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
                  <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95" enter-to="opacity-100 translate-y-0 sm:scale-100" leave="ease-in duration-200" leave-from="opacity-100 translate-y-0 sm:scale-100" leave-to="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95">
                    <DialogPanel class="relative transform overflow-hidden rounded-lg bg-white px-4 pb-4 pt-5 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg sm:p-6">
                      <div class="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-6">
                        <!-- Key Events Input -->
                        <div class="col-span-full">
                          <label for="title" class="block text-sm font-medium text-gray-900">Title</label>
                          <div class="mt-2">
                            <input
                                v-model="sessionTitle"
                                id="title"
                                type="text"
                                placeholder="Voer een titel in om deze sessie makkelijker terug te vinden"
                                class="block w-full rounded-md bg-white px-3 py-1.5 text-base text-gray-900 outline outline-1 outline-gray-300 placeholder:text-gray-400 focus:outline-indigo-600 sm:text-sm"
                            />
                          </div>
                        </div>

                        <!-- Key Events Input -->
                        <div class="col-span-full">
                          <label for="key-events" class="block text-sm font-medium text-gray-900">Key Events</label>
                          <div class="mt-2">
                            <input
                                v-model="newKeyEvent"
                                id="key-events"
                                type="text"
                                placeholder="Voer een key event in en druk op enter"
                                class="block w-full rounded-md bg-white px-3 py-1.5 text-base text-gray-900 outline outline-1 outline-gray-300 placeholder:text-gray-400 focus:outline-indigo-600 sm:text-sm"
                                @keyup.enter="addKeyEvent"
                            />
                          </div>
                          <ul class="mt-3 list-disc pl-5 text-sm text-gray-600">
                            <li v-for="(event, index) in keyEvents" :key="index">
                              {{ event }}
                            </li>
                          </ul>
                        </div>

                        <!-- Select Library -->
                        <div class="col-span-full">
                          <label for="library" class="block text-sm font-medium text-gray-900">Select a collection</label>
                          <div class="mt-2">
                            <select
                                v-model="selectedLibrary"
                                id="library"
                                class="block w-full rounded-md bg-white px-3 py-1.5 text-base text-gray-900 outline outline-1 outline-gray-300 placeholder:text-gray-400 focus:outline-indigo-600 sm:text-sm"
                            >
                              <option v-for="library in libraries" :key="library" :value="library">{{ library }}</option>
                            </select>
                          </div>
                        </div>
                      </div>
                      <div class="mt-5 sm:mt-6 sm:grid sm:grid-flow-row-dense sm:grid-cols-2 sm:gap-3">
                        <button type="button" class="inline-flex w-full justify-center rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 sm:col-start-2" @click="startProcess">Schedule</button>
                        <button type="button" class="mt-3 inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 sm:col-start-1 sm:mt-0" @click="createAOPModel = false" ref="cancelButtonRef">Close</button>
                      </div>
                    </DialogPanel>
                  </TransitionChild>
                </div>
              </div>
            </Dialog>
          </TransitionRoot>
          <transition enter-active-class="transition ease-out duration-100" enter-from-class="transform opacity-0 scale-95" enter-to-class="transform opacity-100 scale-100" leave-active-class="transition ease-in duration-75" leave-from-class="transform opacity-100 scale-100" leave-to-class="transform opacity-0 scale-95">
            <MenuItems class="absolute right-0 z-10 mt-2.5 w-32 origin-top-right rounded-md bg-white py-2 shadow-lg ring-1 ring-gray-900/5 focus:outline-none">
              <MenuItem v-slot="{ active }">
                <a
                    href="#"
                    @click.prevent="logout"
                    :class="[active ? 'bg-gray-50 outline-none' : '', 'block px-3 py-1 text-sm/6 text-gray-900']"
                >
                  Logout
                </a>
              </MenuItem>
            </MenuItems>
          </transition>
        </Menu>
      </div>
    </div>
    <main class="py-8">
      <div class="px-4 sm:px-6 lg:px-8">
        <router-view />
      </div>
    </main>
  </div>
</template>

<style scoped>

</style>
