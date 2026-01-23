import { createRouter, createWebHistory } from "vue-router";
import HomePage from "../views/HomePage.vue";
import EditorPage from "../views/EditorPage.vue";
import FeaturesPage from "../views/FeaturesPage.vue";

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
    {
      path: "/features",
      name: "features",
      component: FeaturesPage,
    },
  ],
});

export default router;
