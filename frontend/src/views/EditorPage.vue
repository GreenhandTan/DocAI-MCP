<script setup lang="ts">
import { useRoute, useRouter } from "vue-router";
import DocumentEditor from "../components/DocumentEditor.vue";
import { ArrowLeft } from "lucide-vue-next";

const route = useRoute();
const router = useRouter();
const fileId = route.params.fileId as string;

const goBack = () => {
  router.push("/");
};
</script>

<template>
  <div class="h-screen flex flex-col bg-slate-50">
    <header
      class="bg-white/80 backdrop-blur-md border-b border-slate-200 px-6 py-4 flex items-center gap-4 shrink-0 sticky top-0 z-10"
    >
      <button
        @click="goBack"
        class="flex items-center gap-2 text-slate-500 hover:text-indigo-600 transition-colors group"
      >
        <ArrowLeft
          class="w-5 h-5 group-hover:-translate-x-1 transition-transform"
        />
        <span class="font-medium">返回</span>
      </button>
      <div class="h-6 w-px bg-slate-200"></div>
      <h1 class="text-lg font-semibold text-slate-800 tracking-tight">
        在线编辑
      </h1>
    </header>
    <div class="flex-1 overflow-hidden">
      <DocumentEditor :fileId="fileId" :show="true" />
    </div>
  </div>
</template>
