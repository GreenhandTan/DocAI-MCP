<script setup lang="ts">
import { computed, ref } from "vue";

const props = defineProps<{
  selectedContentCount: number;
  selectedTemplateName?: string;
  selectedResultFileId?: string;
  messages: { role: "user" | "assistant"; content: string }[];
}>();

const emit = defineEmits<{
  (e: "send", text: string): void;
  (e: "modify", text: string): void;
}>();

const input = ref("");
const isModifyMode = ref(false);

const canSend = computed(() => input.value.trim().length > 0);

const toggleModifyMode = () => {
  isModifyMode.value = !isModifyMode.value;
};

const send = () => {
  const text = input.value.trim();
  if (!text) return;
  if (isModifyMode.value) {
    emit("modify", text);
  } else {
    emit("send", text);
  }
  input.value = "";
  isModifyMode.value = false;
};
</script>

<template>
  <div
    class="bg-white rounded-xl border border-gray-200 shadow-sm flex flex-col h-full"
  >
    <div class="px-5 py-4 border-b border-gray-100 shrink-0">
      <div class="flex items-center justify-between">
        <div>
          <div class="text-lg font-semibold text-gray-900">需求对话</div>
          <div class="text-sm text-gray-500 mt-1">
            <span>已选内容文档：{{ props.selectedContentCount }} 个</span>
            <span class="mx-2 text-gray-300">|</span>
            <span>模板：{{ props.selectedTemplateName || "未选择" }}</span>
          </div>
        </div>
        <button
          v-if="props.selectedResultFileId"
          @click="toggleModifyMode"
          class="text-sm px-3 py-1.5 rounded-lg transition-colors"
          :class="
            isModifyMode
              ? 'bg-amber-100 text-amber-700'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          "
        >
          {{ isModifyMode ? "取消修改" : "修改结果" }}
        </button>
      </div>
    </div>

    <div class="px-5 py-4 flex-1 flex flex-col min-h-0">
      <div
        class="flex-1 overflow-auto rounded-lg border border-gray-100 bg-gray-50/50 p-3 space-y-3 mb-4"
      >
        <div v-if="props.messages.length === 0" class="text-sm text-gray-500">
          在这里描述你希望 AI
          帮你完成的事情，例如：提取要点、生成摘要、按照某模板改写、格式统一、生成会议纪要等。
        </div>
        <div
          v-for="(m, idx) in props.messages"
          :key="idx"
          class="flex"
          :class="m.role === 'user' ? 'justify-end' : 'justify-start'"
        >
          <div
            class="max-w-[85%] rounded-xl px-3 py-2 text-sm whitespace-pre-wrap"
            :class="
              m.role === 'user'
                ? 'bg-indigo-600 text-white'
                : 'bg-white border border-gray-200 text-gray-800'
            "
          >
            {{ m.content }}
          </div>
        </div>
      </div>

      <div class="flex gap-3 shrink-0">
        <input
          v-model="input"
          class="flex-1 rounded-lg border border-gray-200 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          :placeholder="
            isModifyMode
              ? '请输入修改要求，例如：调整字体大小、修改段落内容...'
              : '请输入需求，例如：请提取该文档的关键结论，并生成一份摘要'
          "
          @keyup.enter="send"
        />
        <button
          class="rounded-lg px-4 py-2 text-white font-medium disabled:opacity-50 transition-colors"
          :class="
            isModifyMode
              ? 'bg-amber-600 hover:bg-amber-700'
              : 'bg-indigo-600 hover:bg-indigo-700'
          "
          :disabled="!canSend"
          @click="send"
        >
          {{ isModifyMode ? "修改" : "发送" }}
        </button>
      </div>
    </div>
  </div>
</template>
