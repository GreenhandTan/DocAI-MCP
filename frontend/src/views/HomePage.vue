<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from "vue";
import { useRouter } from "vue-router";
import axios from "axios";
import {
  Plus,
  MessageSquare,
  FileText,
  Send,
  X,
  Download,
  Loader2,
  CheckCircle,
  AlertCircle,
  Clock,
  ChevronRight,
  Paperclip,
  Sparkles,
  RotateCcw,
  ThumbsUp,
  ThumbsDown,
  Copy,
} from "lucide-vue-next";

const router = useRouter();

// ============ 数据类型 ============
interface UploadedFile {
  file_id: string;
  filename: string;
  status: string;
  is_template: boolean;
  created_at: string | null;
  size?: number;
}

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

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  thinking?: string;
  isThinkingExpanded?: boolean;
  attachments?: UploadedFile[];
  isStreaming?: boolean;
  timestamp: Date;
}

interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: Date;
}

// ============ 状态 ============
const conversations = ref<Conversation[]>([]);
const currentConversationId = ref<string | null>(null);
const uploadedFiles = ref<UploadedFile[]>([]);
const selectedFileIds = ref<string[]>([]);
const tasks = ref<Task[]>([]);
const isUploading = ref(false);
const uploadingFiles = ref<string[]>([]);
const inputMessage = ref("");
const isSending = ref(false);
const isThinking = ref(false);
const thinkingText = ref("");
const messagesContainer = ref<HTMLElement | null>(null);

// 模型选择
const modelOptions = [
  { id: "glm4.7", name: "glm4.7" },
  { id: "minimax-m2.1", name: "minimax-m2.1" },
];
const selectedModel = ref<string>("glm4.7");

// 模板相关
const presetTemplates = [
  { id: "resume", name: "个人简历", icon: "📄" },
  { id: "report", name: "项目报告", icon: "📊" },
  { id: "meeting", name: "会议纪要", icon: "📝" },
  { id: "contract", name: "合同协议", icon: "📋" },
  { id: "proposal", name: "项目提案", icon: "💡" },
];
const selectedTemplate = ref<string | null>(null);
const customTemplateFile = ref<UploadedFile | null>(null);
const showTemplateMenu = ref(false);

let taskTimer: number | null = null;

// ============ 计算属性 ============
const currentConversation = computed(() =>
  conversations.value.find((c) => c.id === currentConversationId.value)
);

const currentMessages = computed(
  () => currentConversation.value?.messages || []
);

const selectedFiles = computed(() =>
  uploadedFiles.value.filter((f) => selectedFileIds.value.includes(f.file_id))
);

const canSend = computed(
  () =>
    inputMessage.value.trim().length > 0 &&
    (selectedFileIds.value.length > 0 ||
      selectedTemplate.value ||
      customTemplateFile.value) &&
    !isSending.value
);

// ============ 工具函数 ============
const generateId = () => Math.random().toString(36).substring(2, 15);

const scrollToBottom = async () => {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
};

// ============ 会话管理 ============
const createNewConversation = () => {
  const newConv: Conversation = {
    id: generateId(),
    title: "新对话",
    messages: [],
    createdAt: new Date(),
  };
  conversations.value.unshift(newConv);
  currentConversationId.value = newConv.id;
  selectedFileIds.value = [];
  selectedTemplate.value = null;
};

const switchConversation = (convId: string) => {
  currentConversationId.value = convId;
};

// ============ 文件操作 ============
const handleFileSelect = async (event: Event) => {
  const target = event.target as HTMLInputElement;
  if (!target.files || target.files.length === 0) return;

  const files = Array.from(target.files);
  isUploading.value = true;

  for (const file of files) {
    uploadingFiles.value.push(file.name);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const { data } = await axios.post("/api/v1/files/upload", formData);
      await fetchFiles();
      if (data.fileId) {
        selectedFileIds.value.push(data.fileId);
      }
    } catch (e) {
      console.error("Upload failed:", e);
    } finally {
      uploadingFiles.value = uploadingFiles.value.filter(
        (f) => f !== file.name
      );
    }
  }

  isUploading.value = false;
  target.value = "";
};

const fetchFiles = async () => {
  try {
    const { data } = await axios.get("/api/v1/files");
    uploadedFiles.value = data;
  } catch (e) {
    console.error("Fetch files failed:", e);
  }
};

const fetchTasks = async () => {
  try {
    const { data } = await axios.get("/api/v1/tasks");
    tasks.value = data;
  } catch (e) {
    console.error("Fetch tasks failed:", e);
  }
};

const removeSelectedFile = (fileId: string) => {
  selectedFileIds.value = selectedFileIds.value.filter((id) => id !== fileId);
};

const toggleTemplate = (templateId: string) => {
  selectedTemplate.value =
    selectedTemplate.value === templateId ? null : templateId;
  if (selectedTemplate.value) {
    customTemplateFile.value = null; // 互斥
  }
  showTemplateMenu.value = false;
};

const handleCustomTemplateUpload = async (event: Event) => {
  const target = event.target as HTMLInputElement;
  if (!target.files || target.files.length === 0) return;

  const file = target.files[0];
  const formData = new FormData();
  formData.append("file", file);
  formData.append("is_template", "true");

  try {
    const { data } = await axios.post("/api/v1/files/upload", formData);
    customTemplateFile.value = {
      file_id: data.fileId,
      filename: data.filename,
      status: data.status,
      is_template: true,
      created_at: new Date().toISOString(),
    };
    selectedTemplate.value = null; // 互斥
    showTemplateMenu.value = false;
  } catch (e) {
    console.error("Template upload failed:", e);
  } finally {
    target.value = "";
  }
};

// ============ 消息发送（流式） ============
const sendMessage = async () => {
  if (!canSend.value) return;

  // 确保有当前会话
  if (!currentConversationId.value) {
    createNewConversation();
  }

  const text = inputMessage.value.trim();
  inputMessage.value = "";
  isSending.value = true;
  isThinking.value = false;
  thinkingText.value = "";

  // 添加用户消息
  const userMessage: ChatMessage = {
    id: generateId(),
    role: "user",
    content: text,
    attachments: selectedFiles.value.map((f) => ({ ...f })),
    timestamp: new Date(),
  };

  currentConversation.value?.messages.push(userMessage);

  // 更新会话标题
  if (
    currentConversation.value &&
    currentConversation.value.messages.length === 1
  ) {
    currentConversation.value.title =
      text.slice(0, 20) + (text.length > 20 ? "..." : "");
  }

  // 添加AI消息占位
  const aiMessage: ChatMessage = {
    id: generateId(),
    role: "assistant",
    content: "",
    thinking: "",
    isThinkingExpanded: true,
    isStreaming: true,
    timestamp: new Date(),
  };
  currentConversation.value?.messages.push(aiMessage);

  await scrollToBottom();

  try {
    // 使用流式API
    const response = await fetch("/api/v1/ai/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        file_ids: selectedFileIds.value,
        preset_template: selectedTemplate.value,
        template_file_id: customTemplateFile.value?.file_id,
        model: selectedModel.value,
      }),
    });

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (reader) {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === "thinking") {
                isThinking.value = true;
                thinkingText.value += data.content;
                aiMessage.thinking = thinkingText.value;
              } else if (data.type === "content") {
                isThinking.value = false;
                aiMessage.content += data.content;
              } else if (data.type === "done") {
                aiMessage.isStreaming = false;
              } else if (data.type === "error") {
                aiMessage.content = "抱歉，处理请求时出现错误：" + data.content;
                aiMessage.isStreaming = false;
              }

              await scrollToBottom();
            } catch {
              // 忽略解析错误
            }
          }
        }
      }
    }
  } catch (e) {
    console.error(e);
    aiMessage.content = "AI 响应失败，请稍后重试。";
    aiMessage.isStreaming = false;
  }

  // 创建后台任务
  try {
    await axios.post("/api/v1/tasks/create", {
      task_type:
        selectedTemplate.value || customTemplateFile.value
          ? "fill_template"
          : "format_document",
      content_file_ids: selectedFileIds.value,
      preset_template: selectedTemplate.value,
      template_file_id: customTemplateFile.value?.file_id,
      requirements: text,
      ai_model: selectedModel.value,
    });

    // 添加任务创建成功的提示
    const taskMessage: ChatMessage = {
      id: generateId(),
      role: "assistant",
      content: "✅ 已创建文档处理任务，正在后台处理中...",
      timestamp: new Date(),
    };
    currentConversation.value?.messages.push(taskMessage);

    await fetchTasks();
  } catch (e) {
    console.error(e);
  }

  isSending.value = false;
  thinkingText.value = "";
  await scrollToBottom();
};

// ============ 其他操作 ============
const goToEditor = (fileId: string) => {
  router.push(`/editor/${fileId}`);
};

const downloadFile = (fileId: string) => {
  window.open(`/api/v1/files/${fileId}/download`, "_blank");
};

const toggleThinking = (message: ChatMessage) => {
  message.isThinkingExpanded = !message.isThinkingExpanded;
};

const copyContent = async (content: string) => {
  try {
    await navigator.clipboard.writeText(content);
  } catch (e) {
    console.error("Copy failed:", e);
  }
};

const getTaskStatusIcon = (status: string) => {
  switch (status) {
    case "completed":
      return CheckCircle;
    case "failed":
      return AlertCircle;
    case "processing":
      return Loader2;
    default:
      return Clock;
  }
};

const getTaskStatusClass = (status: string) => {
  switch (status) {
    case "completed":
      return "text-green-500";
    case "failed":
      return "text-red-500";
    case "processing":
      return "text-blue-500 animate-spin";
    default:
      return "text-gray-400";
  }
};

// ============ 生命周期 ============
onMounted(async () => {
  await Promise.all([fetchFiles(), fetchTasks()]);
  taskTimer = window.setInterval(fetchTasks, 3000);

  // 创建默认会话
  if (conversations.value.length === 0) {
    createNewConversation();
  }
});

onBeforeUnmount(() => {
  if (taskTimer) {
    window.clearInterval(taskTimer);
  }
});
</script>

<template>
  <div class="h-screen flex bg-white font-sans text-slate-900">
    <!-- 左侧边栏 -->
    <aside class="w-72 bg-slate-900 flex flex-col border-r border-slate-800">
      <!-- Logo -->
      <div class="p-5 flex items-center gap-3">
        <div
          class="w-9 h-9 bg-gradient-to-br from-indigo-500 to-violet-600 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-500/20"
        >
          <span class="text-white font-bold text-xl">D</span>
        </div>
        <span class="font-bold text-xl text-white tracking-tight">DocAI</span>
      </div>

      <!-- 新建会话按钮 -->
      <div class="px-4 mb-4">
        <button
          @click="createNewConversation"
          class="w-full flex items-center gap-3 px-4 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 transition-all duration-200 text-white shadow-lg shadow-indigo-900/20 group"
        >
          <Plus
            class="w-5 h-5 group-hover:rotate-90 transition-transform duration-300"
          />
          <span class="font-medium">新建会话</span>
          <span
            class="ml-auto text-xs text-indigo-200 bg-indigo-700/50 px-2 py-0.5 rounded"
            >⌘ K</span
          >
        </button>
      </div>

      <!-- 历史会话 -->
      <div
        class="flex-1 overflow-y-auto px-3 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-slate-700 [&::-webkit-scrollbar-thumb]:rounded-full hover:[&::-webkit-scrollbar-thumb]:bg-slate-600"
      >
        <div
          class="text-xs font-medium text-slate-500 px-3 py-2 uppercase tracking-wider"
        >
          历史会话
        </div>
        <div class="space-y-1">
          <button
            v-for="conv in conversations"
            :key="conv.id"
            @click="switchConversation(conv.id)"
            class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left text-sm transition-all duration-200 group"
            :class="
              currentConversationId === conv.id
                ? 'bg-slate-800 text-white shadow-sm'
                : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
            "
          >
            <MessageSquare
              class="w-4 h-4 shrink-0 transition-colors"
              :class="
                currentConversationId === conv.id
                  ? 'text-indigo-400'
                  : 'text-slate-600 group-hover:text-slate-500'
              "
            />
            <span class="truncate font-medium">{{ conv.title }}</span>
          </button>
        </div>
      </div>

      <!-- 底部任务状态 -->
      <div class="p-4 border-t border-slate-800 bg-slate-900/50">
        <div class="flex items-center justify-between mb-3">
          <div
            class="text-xs font-medium text-slate-500 uppercase tracking-wider"
          >
            处理任务
          </div>
          <span
            class="text-xs text-slate-600 bg-slate-800 px-1.5 py-0.5 rounded"
            >{{ tasks.length }}</span
          >
        </div>
        <div
          class="space-y-2 max-h-40 overflow-y-auto pr-1 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-slate-700 [&::-webkit-scrollbar-thumb]:rounded-full hover:[&::-webkit-scrollbar-thumb]:bg-slate-600"
        >
          <div
            v-for="task in tasks.slice(0, 5)"
            :key="task.task_id"
            class="group flex items-center gap-3 p-2.5 rounded-lg bg-slate-800/50 border border-slate-800 hover:border-slate-700 transition-all"
          >
            <div class="shrink-0">
              <component
                :is="getTaskStatusIcon(task.status)"
                :class="['w-4 h-4', getTaskStatusClass(task.status)]"
              />
            </div>
            <div class="flex-1 min-w-0">
              <div class="text-xs text-slate-300 truncate">
                {{ task.requirements?.slice(0, 20) || "处理中..." }}
              </div>
              <div
                class="text-[10px] text-slate-500 mt-0.5 flex items-center gap-1"
              >
                {{
                  task.task_type === "fill_template" ? "模板填充" : "文档格式化"
                }}
              </div>
            </div>
            <div
              class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
            >
              <button
                v-if="task.status === 'completed' && task.result_file_id"
                @click="goToEditor(task.result_file_id)"
                class="p-1 text-slate-400 hover:text-emerald-400 hover:bg-slate-700 rounded transition-colors"
                title="编辑"
              >
                <CheckCircle class="w-3.5 h-3.5" />
              </button>
              <button
                v-if="task.status === 'completed' && task.result_file_id"
                @click="downloadFile(task.result_file_id)"
                class="p-1 text-slate-400 hover:text-indigo-400 hover:bg-slate-700 rounded transition-colors"
                title="下载"
              >
                <Download class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="flex-1 flex flex-col relative overflow-hidden">
      <!-- 顶部标题栏 -->
      <header
        class="h-16 border-b border-slate-100 bg-white/80 backdrop-blur-md flex items-center justify-between px-6 sticky top-0 z-10"
      >
        <div class="flex items-center gap-3">
          <h1 class="font-semibold text-slate-800 text-lg tracking-tight">
            {{ currentConversation?.title || "DocAI 智能助手" }}
          </h1>
          <div
            v-if="isThinking"
            class="flex items-center gap-1.5 px-2 py-1 rounded-full bg-indigo-50 text-indigo-600 text-xs font-medium"
          >
            <Loader2 class="w-3 h-3 animate-spin" />
            <span>思考中</span>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <div
            class="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-100 border border-slate-200"
          >
            <div
              class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"
            ></div>
            <span class="text-xs font-medium text-slate-600">K2 模型在线</span>
          </div>
        </div>
      </header>

      <!-- 消息区域 -->
      <div ref="messagesContainer" class="flex-1 overflow-y-auto scroll-smooth">
        <!-- 空状态 -->
        <div
          v-if="currentMessages.length === 0"
          class="h-full flex flex-col items-center justify-center p-8"
        >
          <div class="text-center max-w-2xl w-full animate-fade-in-up">
            <div
              class="w-20 h-20 bg-gradient-to-br from-indigo-500 to-violet-600 rounded-3xl flex items-center justify-center mx-auto mb-8 shadow-xl shadow-indigo-500/20"
            >
              <Sparkles class="w-10 h-10 text-white" />
            </div>
            <h2 class="text-3xl font-bold text-slate-900 mb-4 tracking-tight">
              有什么可以帮助你？
            </h2>
            <p class="text-slate-500 mb-10 text-lg">
              上传文档，描述你的需求，我将帮你智能处理各类文档任务
            </p>

            <div class="grid grid-cols-2 md:grid-cols-3 gap-4 text-left">
              <div
                v-for="tpl in presetTemplates"
                :key="tpl.id"
                @click="toggleTemplate(tpl.id)"
                class="group relative overflow-hidden p-4 rounded-2xl border border-slate-200 bg-white hover:border-indigo-300 hover:shadow-lg hover:shadow-indigo-500/5 cursor-pointer transition-all duration-300"
              >
                <div
                  class="absolute top-0 right-0 p-3 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <ChevronRight class="w-4 h-4 text-indigo-400" />
                </div>
                <div
                  class="text-3xl mb-3 group-hover:scale-110 transition-transform duration-300 origin-left"
                >
                  {{ tpl.icon }}
                </div>
                <h3 class="font-semibold text-slate-800 mb-1">
                  {{ tpl.name }}
                </h3>
                <p class="text-xs text-slate-500">点击使用此模板</p>
              </div>
            </div>
          </div>
        </div>

        <!-- 消息列表 -->
        <div v-else class="max-w-4xl mx-auto py-8 px-4 space-y-8">
          <div
            v-for="msg in currentMessages"
            :key="msg.id"
            class="animate-fade-in"
          >
            <!-- 用户消息 -->
            <div v-if="msg.role === 'user'" class="flex justify-end">
              <div class="max-w-[85%] flex flex-col items-end">
                <!-- 附件文件 -->
                <div
                  v-if="msg.attachments && msg.attachments.length > 0"
                  class="flex flex-wrap gap-2 mb-3 justify-end"
                >
                  <div
                    v-for="file in msg.attachments"
                    :key="file.file_id"
                    class="flex items-center gap-3 px-4 py-2.5 bg-white rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow"
                  >
                    <div
                      class="w-8 h-8 bg-rose-100 rounded-lg flex items-center justify-center shrink-0"
                    >
                      <FileText class="w-4 h-4 text-rose-500" />
                    </div>
                    <div class="min-w-0">
                      <div
                        class="text-sm font-medium text-slate-700 truncate max-w-[180px]"
                      >
                        {{ file.filename }}
                      </div>
                      <div class="text-xs text-slate-400">
                        {{
                          file.size
                            ? (file.size / 1024).toFixed(1) + " KB"
                            : "未知大小"
                        }}
                      </div>
                    </div>
                  </div>
                </div>
                <!-- 消息内容 -->
                <div
                  class="bg-indigo-600 rounded-2xl rounded-tr-sm px-5 py-3.5 text-white shadow-md shadow-indigo-500/10 text-base leading-relaxed"
                >
                  {{ msg.content }}
                </div>
              </div>
            </div>

            <!-- AI消息 -->
            <div v-else class="flex gap-4 group">
              <div
                class="w-10 h-10 bg-white border border-slate-100 rounded-xl flex items-center justify-center shrink-0 shadow-sm"
              >
                <Sparkles class="w-5 h-5 text-indigo-600" />
              </div>
              <div class="flex-1 min-w-0">
                <!-- 思考过程 -->
                <div v-if="msg.thinking" class="mb-4">
                  <div
                    class="inline-block rounded-xl overflow-hidden border border-amber-200 bg-amber-50/50"
                  >
                    <button
                      @click="toggleThinking(msg)"
                      class="w-full flex items-center gap-2 px-3 py-2 text-sm text-amber-700 hover:bg-amber-100/50 transition-colors"
                    >
                      <Loader2
                        v-if="msg.isStreaming && isThinking"
                        class="w-3.5 h-3.5 animate-spin"
                      />
                      <span class="font-medium">{{
                        msg.isStreaming && isThinking
                          ? "正在深度思考..."
                          : "思考过程"
                      }}</span>
                      <span class="text-xs text-amber-600/70 ml-auto"
                        >{{ msg.thinking.length }} 字符</span
                      >
                      <ChevronRight
                        class="w-4 h-4 transition-transform duration-200"
                        :class="msg.isThinkingExpanded ? 'rotate-90' : ''"
                      />
                    </button>
                    <div
                      v-show="msg.isThinkingExpanded"
                      class="px-3 py-2 border-t border-amber-200/50 text-sm text-amber-800/80 whitespace-pre-wrap font-mono bg-amber-50/30"
                    >
                      {{ msg.thinking }}
                    </div>
                  </div>
                </div>

                <!-- 正文内容 -->
                <div
                  class="prose prose-slate max-w-none text-slate-800 leading-relaxed"
                >
                  <template v-if="msg.content">{{ msg.content }}</template>
                  <span
                    v-else-if="msg.isStreaming && !isThinking"
                    class="inline-flex items-center gap-2 text-slate-400"
                  >
                    <span
                      class="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
                    ></span>
                    <span
                      class="w-2 h-2 bg-slate-400 rounded-full animate-bounce delay-75"
                    ></span>
                    <span
                      class="w-2 h-2 bg-slate-400 rounded-full animate-bounce delay-150"
                    ></span>
                  </span>
                </div>

                <!-- 消息操作栏 -->
                <div
                  v-if="!msg.isStreaming && msg.content"
                  class="flex items-center gap-2 mt-4 opacity-0 group-hover:opacity-100 transition-opacity duration-200"
                >
                  <button
                    @click="copyContent(msg.content)"
                    class="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                    title="复制"
                  >
                    <Copy class="w-4 h-4" />
                  </button>
                  <button
                    class="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                    title="重试"
                  >
                    <RotateCcw class="w-4 h-4" />
                  </button>
                  <div class="w-px h-3 bg-slate-200 mx-1"></div>
                  <button
                    class="p-1.5 text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors"
                  >
                    <ThumbsUp class="w-4 h-4" />
                  </button>
                  <button
                    class="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                  >
                    <ThumbsDown class="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部输入区域 -->
      <div
        class="shrink-0 bg-gradient-to-t from-white via-white to-transparent pt-10 pb-6 px-6"
      >
        <div class="max-w-3xl mx-auto relative">
          <!-- 正在思考提示 -->
          <div
            v-if="isThinking && isSending"
            class="absolute -top-10 left-0 right-0 flex justify-center"
          >
            <div
              class="flex items-center gap-2 px-4 py-1.5 bg-white/90 backdrop-blur border border-indigo-100 rounded-full shadow-sm text-sm text-indigo-600"
            >
              <Loader2 class="w-3.5 h-3.5 animate-spin" />
              <span class="font-medium">正在思考中...</span>
            </div>
          </div>

          <div
            class="bg-white rounded-2xl border border-slate-200 shadow-xl shadow-slate-200/50 focus-within:border-indigo-300 focus-within:ring-4 focus-within:ring-indigo-100 transition-all duration-300"
          >
            <!-- 已选附件 -->
            <div
              v-if="
                selectedFiles.length > 0 ||
                selectedTemplate ||
                customTemplateFile
              "
              class="px-4 pt-3 flex flex-wrap gap-2"
            >
              <div
                v-for="file in selectedFiles"
                :key="file.file_id"
                class="flex items-center gap-2 pl-2 pr-1 py-1 bg-slate-50 rounded-lg border border-slate-200 group"
              >
                <div
                  class="w-5 h-5 bg-rose-100 rounded flex items-center justify-center"
                >
                  <FileText class="w-3 h-3 text-rose-500" />
                </div>
                <span
                  class="text-xs font-medium text-slate-700 max-w-[120px] truncate"
                  >{{ file.filename }}</span
                >
                <button
                  @click="removeSelectedFile(file.file_id)"
                  class="p-0.5 hover:bg-slate-200 rounded text-slate-400 hover:text-slate-600 transition-colors"
                >
                  <X class="w-3 h-3" />
                </button>
              </div>
              <div
                v-if="selectedTemplate"
                class="flex items-center gap-2 pl-2 pr-1 py-1 bg-amber-50 rounded-lg border border-amber-200"
              >
                <span class="text-sm">{{
                  presetTemplates.find((t) => t.id === selectedTemplate)?.icon
                }}</span>
                <span class="text-xs font-medium text-amber-700">{{
                  presetTemplates.find((t) => t.id === selectedTemplate)?.name
                }}</span>
                <button
                  @click="selectedTemplate = null"
                  class="p-0.5 hover:bg-amber-100 rounded text-amber-600/70 hover:text-amber-800 transition-colors"
                >
                  <X class="w-3 h-3" />
                </button>
              </div>
              <div
                v-if="customTemplateFile"
                class="flex items-center gap-2 pl-2 pr-1 py-1 bg-amber-50 rounded-lg border border-amber-200"
              >
                <span class="text-sm">📤</span>
                <span
                  class="text-xs font-medium text-amber-700 max-w-[120px] truncate"
                  >{{ customTemplateFile.filename }}</span
                >
                <button
                  @click="customTemplateFile = null"
                  class="p-0.5 hover:bg-amber-100 rounded text-amber-600/70 hover:text-amber-800 transition-colors"
                >
                  <X class="w-3 h-3" />
                </button>
              </div>
            </div>

            <!-- 上传中提示 -->
            <div
              v-if="uploadingFiles.length > 0"
              class="px-4 pt-3 flex items-center gap-2 text-sm text-indigo-600"
            >
              <Loader2 class="w-4 h-4 animate-spin" />
              <span>正在上传: {{ uploadingFiles.join(", ") }}</span>
            </div>

            <!-- 输入框 -->
            <div class="p-2">
              <textarea
                v-model="inputMessage"
                @keydown.enter.exact.prevent="sendMessage"
                placeholder="输入你的需求，或上传文档..."
                class="w-full resize-none border-none outline-none focus:outline-none focus:ring-0 bg-transparent text-slate-800 placeholder-slate-400 text-base leading-relaxed px-2 shadow-none appearance-none"
                rows="1"
                :style="{
                  height: 'auto',
                  minHeight: '44px',
                  maxHeight: '200px',
                }"
                @input="(e: Event) => { const t = e.target as HTMLTextAreaElement; t.style.height = 'auto'; t.style.height = t.scrollHeight + 'px'; }"
              ></textarea>
            </div>

            <!-- 工具栏 -->
            <div class="px-2 pb-2 flex items-center justify-between">
              <div class="flex items-center gap-1">
                <!-- 上传按钮 -->
                <label
                  class="p-2 rounded-xl hover:bg-slate-100 cursor-pointer transition-colors text-slate-500 hover:text-indigo-600"
                  title="上传文件"
                >
                  <Paperclip class="w-5 h-5" />
                  <input
                    type="file"
                    multiple
                    accept=".doc,.docx,.pdf,.txt"
                    class="hidden"
                    @change="handleFileSelect"
                  />
                </label>

                <!-- 模板选择 -->
                <div class="relative">
                  <button
                    @click="showTemplateMenu = !showTemplateMenu"
                    class="flex items-center gap-1.5 px-3 py-2 rounded-xl hover:bg-slate-100 transition-colors"
                    :class="
                      selectedTemplate || customTemplateFile
                        ? 'bg-amber-50 text-amber-700 hover:bg-amber-100'
                        : 'text-slate-500 hover:text-indigo-600'
                    "
                  >
                    <Sparkles class="w-4 h-4" />
                    <span class="text-sm font-medium">{{
                      selectedTemplate
                        ? presetTemplates.find((t) => t.id === selectedTemplate)
                            ?.name
                        : customTemplateFile
                        ? "自定义模板"
                        : "模板"
                    }}</span>
                  </button>
                  <div
                    v-show="showTemplateMenu"
                    class="absolute bottom-full left-0 mb-3 bg-white rounded-2xl shadow-xl border border-slate-100 p-2 min-w-[200px] z-20 animate-fade-in-up"
                  >
                    <div
                      class="text-xs font-medium text-slate-400 px-3 py-2 uppercase tracking-wider"
                    >
                      选择模板
                    </div>
                    <button
                      v-for="tpl in presetTemplates"
                      :key="tpl.id"
                      @click="toggleTemplate(tpl.id)"
                      class="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-slate-50 text-left transition-colors"
                      :class="
                        selectedTemplate === tpl.id
                          ? 'bg-indigo-50 text-indigo-700'
                          : 'text-slate-700'
                      "
                    >
                      <span class="text-lg">{{ tpl.icon }}</span>
                      <span class="text-sm font-medium">{{ tpl.name }}</span>
                      <CheckCircle
                        v-if="selectedTemplate === tpl.id"
                        class="w-4 h-4 ml-auto text-indigo-600"
                      />
                    </button>

                    <div class="h-px bg-slate-100 my-1 mx-2"></div>

                    <label
                      class="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-slate-50 text-left transition-colors cursor-pointer text-slate-700"
                    >
                      <span class="text-lg">📤</span>
                      <span class="text-sm font-medium">上传自定义模板</span>
                      <input
                        type="file"
                        accept=".doc,.docx"
                        class="hidden"
                        @change="handleCustomTemplateUpload"
                      />
                    </label>
                  </div>
                </div>
              </div>

              <div class="flex items-center gap-2">
                <select
                  v-model="selectedModel"
                  class="h-10 px-3 rounded-xl border border-slate-200 bg-white text-slate-700 text-sm font-medium hover:bg-slate-50 transition-colors"
                  title="选择模型"
                >
                  <option v-for="m in modelOptions" :key="m.id" :value="m.id">
                    {{ m.name }}
                  </option>
                </select>

                <!-- 发送按钮 -->
                <button
                  @click="sendMessage"
                  :disabled="!canSend"
                  class="w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-200 shadow-sm"
                  :class="
                    canSend
                      ? 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-500/30 hover:shadow-indigo-500/50 hover:-translate-y-0.5'
                      : 'bg-slate-100 text-slate-300 cursor-not-allowed'
                  "
                >
                  <Send v-if="!isSending" class="w-5 h-5 ml-0.5" />
                  <Loader2 v-else class="w-5 h-5 animate-spin" />
                </button>
              </div>
            </div>
          </div>

          <div class="text-center text-xs text-slate-400 mt-3">
            DocAI 可能生成不准确的信息，请核对重要内容
          </div>
        </div>
      </div>
    </main>
  </div>
</template>
