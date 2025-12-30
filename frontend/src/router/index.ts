import { createRouter, createWebHistory } from "vue-router";
import HomePage from "../views/HomePage.vue";
import EditorPage from "../views/EditorPage.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "home",
      component: HomePage,
    },
    {
      path: "/editor/:fileId",
      name: "editor",
      component: EditorPage,
      props: true,
    },
  ],
});

export default router;
