<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import axios from "axios";

interface Task {
  task_id: string;
  task_type: string;
  status: string;
  requirements: string | null;
  content_file_ids: string[];
  template_file_id: string | null;
  result_file_id: string | null;
  error: string | null;
  created_at: string | null;
}

const emit = defineEmits(["edit-file", "modify-file"]);

const tasks = ref<Task[]>([]);
let timer: number | null = null;

const statusText = (status: string) => {
  if (status === "pending") return "等待中";
  if (status === "processing") return "处理中";
  if (status === "completed") return "已完成";
  if (status === "failed") return "失败";
  return status;
};

const fetchTasks = async () => {
  const { data } = await axios.get("/api/v1/tasks");
  tasks.value = data;
};

const handleEdit = (fileId: string) => {
  emit("edit-file", fileId);
};

const handleModify = (fileId: string) => {
  emit("modify-file", fileId);
};

const handleDownload = (fileId: string) => {
  // 直接通过后端API下载文件
  const downloadUrl = `/api/v1/files/${fileId}/download`;
  const link = document.createElement("a");
  link.href = downloadUrl;
  link.download = `document-${fileId.slice(0, 8)}.docx`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

onMounted(async () => {
  await fetchTasks();
  timer = window.setInterval(fetchTasks, 2000);
});

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer);
  timer = null;
});
</script>

<template>
  <div class="space-y-3">
    <div
      v-for="task in tasks"
      :key="task.task_id"
      class="border border-gray-200 p-3 rounded-lg flex justify-between items-start bg-white shadow-sm"
    >
      <div class="flex-1 min-w-0">
        <div class="font-medium text-gray-900 text-sm">
          任务 {{ task.task_id.slice(0, 8) }}
        </div>
        <div class="text-xs text-gray-500 mt-1">
          状态：{{ statusText(task.status) }}
        </div>
        <div
          v-if="task.requirements"
          class="text-xs text-gray-500 mt-1 line-clamp-1"
        >
          需求：{{ task.requirements }}
        </div>
        <div v-if="task.error" class="text-xs text-red-600 mt-1">
          错误：{{ task.error }}
        </div>
      </div>
      <div
        v-if="task.status === 'completed'"
        class="flex space-x-2 items-center shrink-0 ml-2"
      >
        <button
          v-if="task.result_file_id"
          @click="handleDownload(task.result_file_id)"
          class="text-xs px-2 py-1 rounded-md bg-green-600 text-white hover:bg-green-700"
        >
          下载
        </button>
        <button
          v-if="task.result_file_id"
          @click="handleEdit(task.result_file_id)"
          class="text-xs px-2 py-1 rounded-md bg-indigo-600 text-white hover:bg-indigo-700"
        >
          预览
        </button>
        <button
          v-if="task.result_file_id"
          @click="handleModify(task.result_file_id)"
          class="text-xs px-2 py-1 rounded-md bg-amber-600 text-white hover:bg-amber-700"
        >
          修改
        </button>
      </div>
      <div v-else class="text-xs text-indigo-600 animate-pulse shrink-0 ml-2">
        处理中...
      </div>
    </div>
    <div
      v-if="tasks.length === 0"
      class="text-center text-gray-500 py-6 text-sm"
    >
      暂无任务
    </div>
  </div>
</template>
