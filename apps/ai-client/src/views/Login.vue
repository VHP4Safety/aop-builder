<script setup lang="ts">
import logo from "../assets/logo-aop-builder.png"
import {AuthService} from "../service/AuthService.ts";
import {inject, ref} from "vue";
import router from "../routing/router.ts";
import {Auth} from "../models/Auth.ts";
import {useStore} from "vuex";
import AlertMessage from "../components/AlertMessage.vue";

const authService = inject<AuthService>("authService");

if (!authService)
{
  throw new Error("AuthService failed to load")
}

const store = useStore();
const username = ref<string>('');
const password = ref<string>('');

const failedAuthentication = ref<boolean>(false)
const errorMessage = ref<string>('')

const submit = async () => {
  try {
    const auth: Auth = await authService.login(username.value, password.value)

    await store.dispatch('auth/login', auth)
    await router.push({ name: 'Home' })
  }
  catch (error) {
    failedAuthentication.value = true
    if (error instanceof Error) {
      errorMessage.value = error.message;
    } else {
      errorMessage.value = String(error);
    }
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center px-6 py-12 lg:px-8">
    <div class="bg-white shadow-sm ring-1 ring-gray-900/5 sm:rounded-xl p-12">
      <div class="sm:mx-auto sm:w-full sm:max-w-sm">
        <img class="mx-auto h-auto w-auto" :src="logo" alt="AOP-Builder" />
        <h2 class="mt-10 text-center text-2xl font-bold tracking-tight text-gray-900">Authenticate</h2>
      </div>

      <AlertMessage v-if="failedAuthentication" type="error" :message="errorMessage || ''" />

      <div class="mt-10 sm:mx-auto sm:w-full sm:max-w-sm">
        <form class="space-y-6" @submit.prevent="submit">
          <div>
            <label for="username" class="block text-sm font-medium text-gray-900">Username</label>
            <div class="mt-2">
              <input
                  type="text"
                  name="username"
                  id="username"
                  autocomplete="username"
                  required
                  class="block w-full rounded-md bg-white px-3 py-1.5 text-base text-gray-900 outline outline-1 outline-gray-300 placeholder:text-gray-400 focus:outline focus:outline-2 focus:outline-indigo-600 sm:text-sm"
                  v-model="username"
              />
            </div>
          </div>

          <div>
            <div class="flex items-center justify-between">
              <label for="password" class="block text-sm font-medium text-gray-900">Password</label>
            </div>
            <div class="mt-2">
              <input
                  type="password"
                  name="password"
                  id="password"
                  autocomplete="current-password"
                  required
                  class="block w-full rounded-md bg-white px-3 py-1.5 text-base text-gray-900 outline outline-1 outline-gray-300 placeholder:text-gray-400 focus:outline focus:outline-2 focus:outline-indigo-600 sm:text-sm"
                  v-model="password"
              />
            </div>
          </div>

          <div>
            <button
                type="submit"
                class="flex w-full justify-center rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
            >
              Login
            </button>
          </div>
        </form>

        <p class="mt-10 text-center text-sm text-gray-500">
          Don't have an account yet?
          <router-link :to="{ name: 'Register' }" class="font-semibold text-indigo-600 hover:text-indigo-500">
            Register an account here
          </router-link>
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>

</style>
