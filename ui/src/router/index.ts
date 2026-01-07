import { computed } from 'vue';
import { createRouter as vueCreateRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw, RouteRecordMultipleViews } from 'vue-router';
import type { Routes } from "@jataware/beaker-vue/router";
import { reformatRoutes }  from "@jataware/beaker-vue/router";
import { useUserStore } from '@/stores/user';

const requiresAuth = async (to, from) => {
  const userStore = useUserStore();

  // Wait for store initialization and refresh status.
  // Refreshes for every page view in case auth status has changed between.
  await userStore.waitForInit();
  await userStore.refresh();

  if (to?.meta?.requiresAuth && !(userStore.isLoggedIn && await userStore.isSessionValid())) {
    return {
      name: "login",
      query: {
        next: to.fullPath,
      }
    };
  }
};

const prepareLogin = async (to, from) => {
  const userStore = useUserStore();

  // Wait for store initialization
  await userStore.waitForInit();

  const loginInfo = await userStore.prepareLogin();
  const localNext = to.query?.next;
  if (loginInfo?.status === "logged_in") {
    return localNext || loginInfo?.next || "/dashboard";
  }
};

const routes: RouteRecordRaw[] = [
    {
      name: "home",
      path: "/",
      component: async () => import('@/pages/Home.vue'),
      meta: {
        title: "Home",
        requiresAuth: false,
      },
    },
    {
      name: "dashboard",
      path: "/dashboard",
      component: () => import('@/pages/Dashboard.vue'),
      meta: {
        title: "Dashboard",
        requiresAuth: true
      },
    },
    {
      name: "splash",
      path: "/about",
      component: () => import('@/pages/SplashPage.vue'),
      meta: {
        title: "Your AI-Powered Co-Scientist",
        requiresAuth: false
      },
    },
    {
      name: "launch",
      path: "/launch/:context/:session?",
      component: () => import('@/pages/Launch.vue'),
      meta: {
        title: (params) => `Launching session ${ params.session }`,
        requiresAuth: true, requiresRole: ["server"]
      },
    },
    {
      name: "session",
      path: "/connect/:session",
      component: () => import('@/pages/Session.vue'),
      props: true,
      meta: {
        title: (params) => `Session ${ params.session }`,
        requiresAuth: true, requiresRole: ["server"]
      },
    },
    {
      path: "/admin",
      component: () => import('@/pages/admin/AdminLayout.vue'),
      meta: {
        title: "Admin",
        requiresAuth: true, requiresRole: ["admin"]
      },
      redirect: { name: "admin-dashboard" },
      children: [
        {
          name: "admin-dashboard",
          path: "dashboard",
          component: () => import('@/pages/admin/AdminDashboard.vue'),
          meta: {
            title: "Admin - Dashboard",
            requiresAuth: true, requiresRole: ["admin"]
          },
        },
        {
          name: "admin-contexts",
          path: "contexts",
          component: () => import('@/pages/admin/AdminContexts.vue'),
          meta: {
            title: "Admin - Contexts",
            requiresAuth: true, requiresRole: ["admin"]
          },
        },
        {
          name: "admin-context-edit",
          path: "contexts/:sourceKey",
          component: () => import('@/pages/admin/AdminContextPanelHost.vue'),
          meta: {
            title: "Admin - Edit Context",
            requiresAuth: true, requiresRole: ["admin"],
            panelHost: true,
          },
        },
        {
          name: "admin-context-workflow",
          path: "contexts/:sourceKey/workflows/:workflowId",
          component: () => import('@/pages/admin/AdminContextPanelHost.vue'),
          meta: {
            title: "Admin - Edit Workflow",
            requiresAuth: true, requiresRole: ["admin"],
            panelHost: true,
          },
        },
        {
          name: "admin-context-workflow-stage",
          path: "contexts/:sourceKey/workflows/:workflowId/stages/:stageId",
          component: () => import('@/pages/admin/AdminContextPanelHost.vue'),
          meta: {
            title: "Admin - Edit Stage",
            requiresAuth: true, requiresRole: ["admin"],
            panelHost: true,
          },
        },
        {
          name: "admin-context-integration",
          path: "contexts/:sourceKey/integrations/:integrationId",
          component: () => import('@/pages/admin/AdminContextPanelHost.vue'),
          meta: {
            title: "Admin - Edit Integration",
            requiresAuth: true, requiresRole: ["admin"],
            panelHost: true,
          },
        },
        {
          name: "admin-images",
          path: "images",
          component: () => import('@/pages/admin/AdminImages.vue'),
          meta: {
            title: "Admin - Images",
            requiresAuth: true, requiresRole: ["admin"]
          },
        },
        {
          name: "admin-vault",
          path: "vault",
          component: () => import('@/pages/admin/AdminVault.vue'),
          meta: {
            title: "Admin - Secret Vault",
            requiresAuth: true, requiresRole: ["admin"]
          },
        },
        {
          name: "admin-users",
          path: "users",
          component: () => import('@/pages/admin/AdminUsers.vue'),
          meta: {
            title: "Admin - Users",
            requiresAuth: true, requiresRole: ["admin"]
          },
        },
        {
          name: "admin-sessions",
          path: "sessions",
          component: () => import('@/pages/admin/AdminSessions.vue'),
          meta: {
            title: "Admin - Sessions",
            requiresAuth: true, requiresRole: ["admin"]
          },
        },
      ],
    },
    {
      name: "signup",
      path: "/signup",
      component: () => import('@/pages/auth/SignUp.vue'),
      meta: {
        title: "Sign Up",
        requiresAuth: false
      },
    },
    {
      name: "login",
      path: "/login",
      component: () => import('@/pages/auth/Login.vue'),
      beforeEnter: [prepareLogin],
      meta: {
        title: "Login",
        requiresAuth: false,
      },
    },
    {
      name: "logout",
      path: "/logout",
      component: () => import('@/pages/auth/Logout.vue'),
      meta: {
        title: "Logout",
        requiresAuth: false,
      },
    },
    {
      name: "reset-password",
      path: "/reset",
      component: () => import('@/pages/auth/ResetPassword.vue'),
      meta: {
        title: "Password Reset",
        requiresAuth: false
      },
    },
    {
      name: "email-validation",
      path: "/verify",
      component: () => import('@/pages/auth/EmailValidation.vue'),
      meta: {
        title: "Verify your email",
        requiresAuth: false
      },
    },
    {
      name: "invite-signup",
      path: "/invite",
      component: () => import('@/pages/auth/InviteSignup.vue'),
      meta: {
        title: "Verify your invitation",
        requiresAuth: false
      },
    },
    {
      name: "not-found",
      path: "/:pathMatch(.*)*",
      component: () => import('@/pages/NotFound.vue'),
      meta: {
        title: "Page Not Found",
        requiresAuth: false
      },
    },
]

export const createRouter = (config) => {
  if (config.pathPrefix) {
    const prefix = (<string>config.pathPrefix).split('/').filter((obj) => Boolean(obj));
    routes.forEach((route) => {
      const path = [...prefix, ...route.path.split('/')].filter((part) => part);
      route.path = "/" + path.join("/");
    })
  }
  const router = vueCreateRouter({
    history: createWebHistory(import.meta.env?.BASE_URL),
    routes: routes,
  });
  router.beforeEach(requiresAuth);
  return router;
}

export default createRouter;
