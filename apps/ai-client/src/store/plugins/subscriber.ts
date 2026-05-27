import {Store} from 'vuex';
import axios from "axios";
import {Token} from "../../models/Token.ts";

const mutationTypes = {
    SET_TOKEN: 'auth/setToken',
    SET_USER: 'auth/setUser'
};

const storageKeys = {
    TOKEN: 'token',
    USER: 'user'
};

function manageLocalStorage(key: string, payload: any)
{
    if (payload)
    {
        if (key === storageKeys.TOKEN) {
            const existing = localStorage.getItem(key);
            if (existing) {
                const existingParsed: Token = JSON.parse(existing);

                // Als de bestaande token een recentere createdAt heeft, sla de nieuwe dan niet op
                if (new Date(existingParsed.createdAt) > new Date(payload.createdAt)) {
                    return;
                }
            }
        }

        localStorage.setItem(key, JSON.stringify(payload));
    }
    else
    {
        localStorage.removeItem(key);
    }

    if (storageKeys.TOKEN === key) {
        if (payload) {
            axios.defaults.headers.common['Authorization'] = `Bearer ${payload.accessToken}`;
        } else {
            delete axios.defaults.headers.common['Authorization'];
        }
    }
}

export default function createSubscriber()
{
    return (store: Store<any>) =>
    {
        store.subscribe((mutation: any) => {
            if (mutationTypes.SET_TOKEN === mutation.type) {
                manageLocalStorage(storageKeys.TOKEN, mutation.payload);
            }

            if (mutationTypes.SET_USER === mutation.type) {
                manageLocalStorage(storageKeys.USER, mutation.payload);
            }
        });
    };
}
