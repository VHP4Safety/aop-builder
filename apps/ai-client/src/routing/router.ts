import { createRouter, createWebHistory } from 'vue-router'
import Login from "../views/Login.vue";
import Register from "../views/Register.vue";
import AppLayout from "../layout/AppLayout.vue";
import Home from "../views/Home.vue";
import store from "../store";
import Library from "../views/Library.vue";
import CreateLibrary from "../views/CreateLibrary.vue";
import ExplainabilityModule from "../views/ExplainabilityModule.vue";
import StartProces from "../views/process/StartProcess.vue";
import ViewProcess from "../views/process/ViewProcess.vue";
import ViewProcessResult from "../views/process/ViewProcessResult.vue";
import ViewProcessChunkSelection from "../views/process/ViewProcessChunkSelection.vue";
import ProcessStartupInformation from "../views/process/result/ProcessStartupInformation.vue";
import ProcessVisualInformation from "../views/process/result/ProcessVisualInformation.vue";
import ProcessEnrichedGraphInformation from "../views/process/result/ProcessEnrichedGraphInformation.vue";
import ProcessSelectedChunkInformation from "../views/process/result/ProcessSelectedChunkInformation.vue";

const routes = [
    {
        path: '/login',
        name: 'Login',
        component: Login,
        meta: {
            title: 'Aanmelden',
            requiresVisitor: true
        }
    },
    {
        path: '/register',
        name: 'Register',
        component: Register,
        meta: {
            title: 'Registreren',
            requiresVisitor: true
        }
    },
    {
        path: '/',
        component: AppLayout,
        meta: {
            requiresAuth: true
        },
        children: [
            {
                path: '',
                name: 'Home',
                component: Home,
                meta: {
                    title: 'Mijn overzicht'
                }
            },
            {
                path: '/library',
                name: 'Library',
                component: Library,
                meta: {
                    title: 'Mijn bibliotheek'
                }
            },
            {
                path: '/library/create',
                name: 'CreateLibrary',
                component: CreateLibrary,
                meta: {
                    title: 'Collectie toevoegen'
                }
            },
            {
                path: '/explainability',
                name: 'ExplainabilityModule',
                component: ExplainabilityModule,
                meta: {
                    title: 'Explainability Module'
                }
            },
            {
                path: '/sessions/start',
                name: 'StartProcess',
                component: StartProces,
                meta: {
                    title: 'Start process'
                }
            },
            {
                path: '/sessions/:id',
                name: 'ViewProcess',
                component: ViewProcess,
                meta: {
                    title: 'View process'
                }
            },
            {
                path: '/sessions/:id/chunking',
                name: 'ViewProcessChunkingSelection',
                component: ViewProcessChunkSelection,
                meta: {
                    title: 'Review relevant chunks'
                }
            },
            {
                path: '/sessions/:id/result',
                name: 'ViewProcessResult',
                component: ViewProcessResult,
                children: [
                    {
                        path: 'startup',
                        name: 'ProcessStartupInformation',
                        component: ProcessStartupInformation,
                        meta: {
                            title: 'Startup information'
                        }
                    },
                    {
                        path: 'chunks',
                        name: 'ProcessSelectedChunkInformation',
                        component: ProcessSelectedChunkInformation,
                        meta: {
                            title: 'Startup information'
                        }
                    },
                    {
                        path: 'visual',
                        name: 'ProcessVisualInformation',
                        component: ProcessVisualInformation,
                        meta: {
                            title: 'Extracted Causal Relations'
                        }
                    },
                    {
                        path: 'enriched',
                        name: 'ProcessEnrichedGraphInformation',
                        component: ProcessEnrichedGraphInformation,
                        meta: {
                            title: 'Enriched AOP Graph'
                        }
                    }
                ]
            }
        ]
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes,
});

router.beforeEach((to) => {
    const loggedIn = store.getters['auth/isAuthenticated'];

    if (to.meta && to.meta.title) {
        document.title = to.meta?.title as string;
    }

    if (to.matched.some(record => record.meta.requiresAuth) && !loggedIn) {
        return '/login';
    }

    if (to.matched.some(record => record.meta.requiresVisitor) && loggedIn) {
        return '/';
    }

    return true;
});

router.afterEach(() => {
    window.scrollTo({
        top: 0,
        left: 0,
        behavior: "smooth",
    });
})

export default router
