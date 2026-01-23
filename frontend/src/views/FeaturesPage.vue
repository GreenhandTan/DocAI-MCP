<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import axios from "axios";
import {
  ArrowLeft,
  Shield,
  GitBranch,
  Mic,
  FileText,
  Loader2,
  CheckCircle,
  Upload,
} from "lucide-vue-next";
import ReviewPanel from "../components/ReviewPanel.vue";
import WorkflowPanel from "../components/WorkflowPanel.vue";
import AudioTranscriber from "../components/AudioTranscriber.vue";

const router = useRouter();

// 当前活动的功能选项卡
const activeTab = ref<"review" | "workflow" | "audio">("review");

// 文件相关
interface UploadedFile {
  file_id: string;
  filename: string;
  status: string;
  is_template: boolean;
}

const uploadedFiles = ref<UploadedFile[]>([]);
const selectedFileId = ref<string | null>(null);
const isUploading = ref(false);

// 审查相关
interface ReviewResult {
  review_id: string;
  status: string;
  review_type: string;
  annotations: any[] | null;
  summary: string | null;
  risk_level: string | null;
  error: string | null;
}

const reviewResult = ref<ReviewResult | null>(null);
const isReviewing = ref(false);
const selectedReviewType = ref("general");

const reviewTypes = [
  { id: "general", name: "通用审查", description: "内容完整性和逻辑检查" },
  { id: "legal", name: "法律审查", description: "合同条款和法律风险" },
  { id: "compliance", name: "合规审查", description: "法规合规性检查" },
  { id: "risk", name: "风险评估", description: "综合风险分析" },
];

// 加载文件列表
const fetchFiles = async () => {
  try {
    const response = await axios.get("/api/v1/files");
    uploadedFiles.value = response.data;
  } catch (error) {
    console.error("Failed to fetch files:", error);
  }
};

// 上传文件
const handleFileUpload = async (event: Event) => {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) return;

  isUploading.value = true;

  try {
    const formData = new FormData();
    formData.append("file", file);

    const response = await axios.post("/api/v1/files/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });

    await fetchFiles();
    selectedFileId.value = response.data.fileId;
  } catch (error) {
    console.error("Upload failed:", error);
    alert("上传失败");
  } finally {
    isUploading.value = false;
  }
};

// 开始审查
const startReview = async () => {
  if (!selectedFileId.value) {
    alert("请先选择要审查的文档");
    return;
  }

  isReviewing.value = true;
  reviewResult.value = null;

  try {
    // 创建审查任务
    const createResponse = await axios.post("/api/v1/reviews/create", {
      file_id: selectedFileId.value,
      review_type: selectedReviewType.value,
    });

    const reviewId = createResponse.data.review_id;

    // 轮询状态
    const checkStatus = async () => {
      try {
        const statusResponse = await axios.get(`/api/v1/reviews/${reviewId}`);
        const result = statusResponse.data as ReviewResult;

        if (result.status === "completed" || result.status === "failed") {
          isReviewing.value = false;
          reviewResult.value = result;
          return;
        }

        setTimeout(checkStatus, 2000);
      } catch (error) {
        console.error("Status check failed:", error);
        isReviewing.value = false;
      }
    };

    checkStatus();
  } catch (error) {
    console.error("Review failed:", error);
    isReviewing.value = false;
    alert("审查启动失败");
  }
};

const goBack = () => {
  router.push("/");
};

onMounted(() => {
  fetchFiles();
});
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <!-- 顶部导航 -->
    <header class="bg-white border-b border-gray-200 sticky top-0 z-10">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex items-center justify-between h-16">
          <div class="flex items-center gap-4">
            <button
              @click="goBack"
              class="flex items-center gap-2 text-gray-600 hover:text-gray-900"
            >
              <ArrowLeft class="h-5 w-5" />
              <span>返回</span>
            </button>
            <div class="h-6 w-px bg-gray-300"></div>
            <h1 class="text-xl font-bold text-gray-900">高级功能</h1>
          </div>
        </div>
      </div>
    </header>

    <!-- 功能选项卡 -->
    <div class="bg-white border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <nav class="flex space-x-8" aria-label="Tabs">
          <button
            @click="activeTab = 'review'"
            :class="[
              activeTab === 'review'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
              'flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm',
            ]"
          >
            <Shield class="h-5 w-5" />
            AI 审查员
          </button>
          <button
            @click="activeTab = 'workflow'"
            :class="[
              activeTab === 'workflow'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
              'flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm',
            ]"
          >
            <GitBranch class="h-5 w-5" />
            工作流编排
          </button>
          <button
            @click="activeTab = 'audio'"
            :class="[
              activeTab === 'audio'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
              'flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm',
            ]"
          >
            <Mic class="h-5 w-5" />
            语音转纪要
          </button>
        </nav>
      </div>
    </div>

    <!-- 主内容区 -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- AI 审查员 -->
      <div v-if="activeTab === 'review'" class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- 左侧：文件选择和设置 -->
        <div class="space-y-6">
          <!-- 上传文件 -->
          <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <h3 class="text-lg font-semibold text-gray-900 mb-4">选择文档</h3>
            
            <!-- 上传按钮 -->
            <div class="mb-4">
              <input
                type="file"
                accept=".pdf,.docx,.doc,.txt"
                @change="handleFileUpload"
                class="hidden"
                id="file-upload"
              />
              <label
                for="file-upload"
                class="flex items-center justify-center gap-2 w-full px-4 py-3 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-indigo-400 transition-colors"
              >
                <Upload v-if="!isUploading" class="h-5 w-5 text-gray-400" />
                <Loader2 v-else class="h-5 w-5 text-indigo-600 animate-spin" />
                <span class="text-gray-600">上传新文档</span>
              </label>
            </div>

            <!-- 已上传文件列表 -->
            <div class="space-y-2 max-h-60 overflow-auto">
              <button
                v-for="file in uploadedFiles.filter(f => !f.is_template)"
                :key="file.file_id"
                @click="selectedFileId = file.file_id"
                :class="[
                  'w-full flex items-center gap-3 p-3 rounded-lg border transition-colors text-left',
                  selectedFileId === file.file_id
                    ? 'border-indigo-500 bg-indigo-50'
                    : 'border-gray-200 hover:border-gray-300',
                ]"
              >
                <FileText class="h-5 w-5 text-gray-400" />
                <span class="flex-1 truncate text-sm">{{ file.filename }}</span>
                <CheckCircle
                  v-if="selectedFileId === file.file_id"
                  class="h-5 w-5 text-indigo-600"
                />
              </button>
            </div>
          </div>

          <!-- 审查类型选择 -->
          <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <h3 class="text-lg font-semibold text-gray-900 mb-4">审查类型</h3>
            <div class="space-y-2">
              <button
                v-for="type in reviewTypes"
                :key="type.id"
                @click="selectedReviewType = type.id"
                :class="[
                  'w-full flex flex-col p-3 rounded-lg border transition-colors text-left',
                  selectedReviewType === type.id
                    ? 'border-indigo-500 bg-indigo-50'
                    : 'border-gray-200 hover:border-gray-300',
                ]"
              >
                <span class="font-medium text-gray-900">{{ type.name }}</span>
                <span class="text-sm text-gray-500">{{ type.description }}</span>
              </button>
            </div>
          </div>

          <!-- 开始审查按钮 -->
          <button
            @click="startReview"
            :disabled="!selectedFileId || isReviewing"
            class="w-full flex items-center justify-center gap-2 px-4 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Shield v-if="!isReviewing" class="h-5 w-5" />
            <Loader2 v-else class="h-5 w-5 animate-spin" />
            {{ isReviewing ? "审查中..." : "开始审查" }}
          </button>
        </div>

        <!-- 右侧：审查结果 -->
        <div class="lg:col-span-2">
          <ReviewPanel :review="reviewResult" :loading="isReviewing" />
        </div>
      </div>

      <!-- 工作流编排 -->
      <div v-if="activeTab === 'workflow'" class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <WorkflowPanel
          :selected-file-ids="selectedFileId ? [selectedFileId] : []"
          @execute="(wfId, fileIds) => console.log('Executed:', wfId, fileIds)"
        />
        
        <!-- 文件选择 -->
        <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
          <h3 class="text-lg font-semibold text-gray-900 mb-4">输入文件</h3>
          <p class="text-sm text-gray-500 mb-4">选择要处理的文件作为工作流输入</p>
          
          <div class="mb-4">
            <input
              type="file"
              accept=".pdf,.docx,.doc,.txt"
              @change="handleFileUpload"
              class="hidden"
              id="workflow-file-upload"
            />
            <label
              for="workflow-file-upload"
              class="flex items-center justify-center gap-2 w-full px-4 py-3 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-indigo-400 transition-colors"
            >
              <Upload v-if="!isUploading" class="h-5 w-5 text-gray-400" />
              <Loader2 v-else class="h-5 w-5 text-indigo-600 animate-spin" />
              <span class="text-gray-600">上传文件</span>
            </label>
          </div>

          <div class="space-y-2 max-h-80 overflow-auto">
            <button
              v-for="file in uploadedFiles.filter(f => !f.is_template)"
              :key="file.file_id"
              @click="selectedFileId = file.file_id"
              :class="[
                'w-full flex items-center gap-3 p-3 rounded-lg border transition-colors text-left',
                selectedFileId === file.file_id
                  ? 'border-indigo-500 bg-indigo-50'
                  : 'border-gray-200 hover:border-gray-300',
              ]"
            >
              <FileText class="h-5 w-5 text-gray-400" />
              <span class="flex-1 truncate text-sm">{{ file.filename }}</span>
              <CheckCircle
                v-if="selectedFileId === file.file_id"
                class="h-5 w-5 text-indigo-600"
              />
            </button>
          </div>
        </div>
      </div>

      <!-- 语音转纪要 -->
      <div v-if="activeTab === 'audio'" class="max-w-2xl mx-auto">
        <AudioTranscriber
          @uploaded="(fileId) => console.log('Audio uploaded:', fileId)"
          @transcribed="(result) => console.log('Transcribed:', result)"
        />
      </div>
    </main>
  </div>
</template>
