<script setup lang="ts">
import { onMounted, onBeforeUnmount, watch, ref } from "vue";
import axios from "axios";

const props = defineProps<{
  fileId: string;
  show?: boolean;
}>();

const emit = defineEmits(["close"]);

const editorContainerId = `onlyoffice-editor-${props.fileId}`;
let docEditor: any = null;
const isLoading = ref(true);
const loadError = ref<string | null>(null);

const loadEditor = async () => {
  isLoading.value = true;
  loadError.value = null;

  try {
    const { data: config } = await axios.get(
      `/api/v1/files/${props.fileId}/onlyoffice-config`
    );
    // @ts-ignore
    docEditor = new DocsAPI.DocEditor(editorContainerId, config);
    isLoading.value = false;
  } catch (e) {
    console.error("Failed to load editor config", e);
    loadError.value = "加载在线编辑器失败，请检查文档是否存在";
    isLoading.value = false;
  }
};

const destroyEditor = () => {
  if (docEditor) {
    docEditor.destroyEditor();
    docEditor = null;
  }
};

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === "Escape") {
    emit("close");
  }
};

// 兼容旧的show属性模式
const shouldShow = ref(props.show !== false);

watch(
  () => props.show,
  (newShow) => {
    shouldShow.value = newShow !== false;
    if (shouldShow.value) {
      setTimeout(loadEditor, 100);
    } else {
      destroyEditor();
    }
  }
);

onMounted(() => {
  if (shouldShow.value) {
    loadEditor();
  }
  document.addEventListener("keydown", handleKeydown);
});

onBeforeUnmount(() => {
  destroyEditor();
  document.removeEventListener("keydown", handleKeydown);
});
</script>

<template>
  <div class="h-full flex flex-col bg-white">
    <!-- 加载状态 -->
    <div v-if="isLoading" class="flex-1 flex items-center justify-center">
      <div class="text-center">
        <div
          class="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"
        ></div>
        <p class="text-slate-500 font-medium">正在加载编辑器...</p>
      </div>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="loadError" class="flex-1 flex items-center justify-center">
      <div class="text-center">
        <div class="text-rose-500 text-5xl mb-4">⚠️</div>
        <p class="text-slate-700 font-medium">{{ loadError }}</p>
        <button
          @click="loadEditor"
          class="mt-4 px-5 py-2.5 bg-indigo-600 text-white rounded-xl hover:bg-indigo-500 transition-colors shadow-lg shadow-indigo-500/20"
        >
          重试
        </button>
      </div>
    </div>

    <!-- 编辑器容器 -->
    <div v-show="!isLoading && !loadError" class="flex-1 relative">
      <div :id="editorContainerId" class="absolute inset-0"></div>
    </div>
  </div>
</template>
