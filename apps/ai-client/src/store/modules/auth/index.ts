import { Module } from 'vuex';
import {Auth} from "../../../models/Auth.ts";
import {User} from "../../../models/User.ts";
import {Token} from "../../../models/Token.ts";

export const AuthModule: Module<Auth, unknown> = {
    namespaced: true,
    state: {
        user: null as User | null,
        token: null as Token | null
    } as Auth,
    getters: {
        isAuthenticated: (state: Auth) => {
            const userExists = state.user !== null && state.user.id !== null;
            const tokenExists = state.token !== null && state.token.accessToken !== '';
            return userExists && tokenExists;
        },
    },
    mutations: {
        setUser: (state: Auth, user: User) => {
            state.user = user
        },
        setToken: (state: Auth, token: Token) => {
            state.token = token
        }
    },
    actions: {
        login: async ({commit}: { commit: any, state: Auth }, auth: Auth) => {
            commit('setUser', auth.user)
            commit('setToken', auth.token)
        },
        refresh: async ({commit}: { commit: any, state: Auth }, token: Token) => {
            commit('setToken', token)
        },
        signOut: ({ commit }: any) => {
            commit('setUser', null)
            commit('setToken', null)
        }
    }
};

export default AuthModule;