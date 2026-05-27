import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './routing/router.ts'
import { authService } from "./service/impl/AuthServiceImpl.ts";
import store from "./store";
import {Token} from "./models/Token.ts";
import {User} from "./models/User.ts";
import {Auth} from "./models/Auth.ts";
import {collectionService} from "./service/impl/CollectionServiceImpl.ts";
import axios from "axios";
import {sessionService} from "./service/impl/SessionServiceImpl.ts";

axios.defaults.baseURL = import.meta.env.VITE_API_URL || ""

const isAlreadyAuthenticated = async () => {
    const tokenObject = localStorage.getItem('token');
    const userObject = localStorage.getItem('user');

    if (tokenObject && userObject)
    {
        const token: Token = JSON.parse(tokenObject);
        const user: User = JSON.parse(userObject);
        const auth: Auth = { user, token };

        await store.dispatch('auth/login', auth);
    }
};

(async () => {
    await isAlreadyAuthenticated();

    createApp(App)
        .use(router)
        .use(store)
        .provide('authService', authService)
        .provide('collectionService', collectionService)
        .provide('sessionService', sessionService)
        .mount('#app');
})();
