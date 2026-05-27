import { createStore } from 'vuex';
import createSubscriber from './plugins/subscriber.ts'
import auth from "./modules/auth";

export default createStore({
    state: {},
    mutations: {},
    actions: {},
    modules: { auth },
    plugins: [createSubscriber()],
});