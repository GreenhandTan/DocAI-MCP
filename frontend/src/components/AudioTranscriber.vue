<script setup lang="ts">
import { ref, computed } from "vue";
import axios from "axios";
import {
  Mic,
  Upload,
  Play,
  Pause,
  Loader2,
  FileText,
  CheckCircle,
  XCircle,
  Users,
  ListChecks,
  Download,
} from "lucide-vue-next";

interface ActionItem {
  item: string;
  owner?: string;
  deadline?: string;
}

interface TranscriptionResult {
  transcription_id: string;
  audio_file_id: string;
  status: string;
  transcript: string | null;
  speakers: any[] | null;
  summary: string | null;
  action_items: ActionItem[] | null;
  result_file_id: string | null;
  error: string | null;
}

const emit = defineEmits<{
  (e: "uploaded", fileId: string): void;
  (e: "transcribed", result: TranscriptionResult): void;
}>();

const isUploading = ref(false);
const isTranscribing = ref(false);
const uploadedAudioId = ref<string | null>(null);
const uploadedFileName = ref<string>("");
const transcriptionResult = ref<TranscriptionResult | null>(null);
const generateMinutes = ref(true);
const pollingTimer = ref<number | null>(null);

const handleFileSelect = async (event: Event) => {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) return;
  
  // 检查文件类型
  const allowedTypes = ['audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/m4a', 'audio/ogg', 'audio/webm'];
  if (!allowedTypes.includes(file.type) && !file.name.match(/\.(mp3|wav|m4a|ogg|webm)$/i)) {
    alert("请上传音频文件 (MP3, WAV, M4A, OGG, WEBM)");
    return;
  }
  
  isUploading.value = true;
  
  try {
    const formData = new FormData();
    formData.append("file", file);
    
    const response = await axios.post("/api/v1/files/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    
    uploadedAudioId.value = response.data.fileId;
    uploadedFileName.value = file.name;
    emit("uploaded", response.data.fileId);
  } catch (error) {
    console.error("Upload failed:", error);
    alert("上传失败");
  } finally {
    isUploading.value = false;
  }
};

const startTranscription = async () => {
  if (!uploadedAudioId.value) return;
  
  isTranscribing.value = true;
  transcriptionResult.value = null;
  
  try {
    const response = await axios.post("/api/v1/transcriptions/create", {
      audio_file_id: uploadedAudioId.value,
      generate_minutes: generateMinutes.value,
    });
    
    const transcriptionId = response.data.transcription_id;
    
    // 轮询状态
    const checkStatus = async () => {
      try {
        const statusResponse = await axios.get(`/api/v1/transcriptions/${transcriptionId}`);
        const result = statusResponse.data as TranscriptionResult;
        
        if (result.status === "completed" || result.status === "failed") {
          isTranscribing.value = false;
          transcriptionResult.value = result;
          emit("transcribed", result);
          if (pollingTimer.value) {
            clearTimeout(pollingTimer.value);
            pollingTimer.value = null;
          }
          return;
        }
        
        pollingTimer.value = window.setTimeout(checkStatus, 3000);
      } catch (error) {
        console.error("Status check failed:", error);
        isTranscribing.value = false;
      }
    };
    
    checkStatus();
  } catch (error) {
    console.error("Transcription failed:", error);
    isTranscribing.value = false;
    alert("转录失败");
  }
};

const downloadResult = async () => {
  if (!transcriptionResult.value?.result_file_id) return;
  
  try {
    const response = await axios.get(
      `/api/v1/files/${transcriptionResult.value.result_file_id}/download`,
      { responseType: "blob" }
    );
    
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "会议纪要.docx");
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error("Download failed:", error);
  }
};

const reset = () => {
  uploadedAudioId.value = null;
  uploadedFileName.value = "";
  transcriptionResult.value = null;
  if (pollingTimer.value) {
    clearTimeout(pollingTimer.value);
    pollingTimer.value = null;
  }
};
</script>

<template>
  <div class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
    <!-- 标题栏 -->
    <div class="px-5 py-4 border-b border-gray-100 bg-gradient-to-r from-green-50 to-teal-50">
      <div class="flex items-center gap-3">
        <div class="p-2 bg-green-100 rounded-lg">
          <Mic class="h-5 w-5 text-green-600" />
        </div>
        <div>
          <div class="text-lg font-semibold text-gray-900">语音转会议纪要</div>
          <div class="text-sm text-gray-500">上传音频自动生成结构化会议纪要</div>
        </div>
      </div>
    </div>

    <div class="p-5">
      <!-- 上传区域 -->
      <div
        v-if="!uploadedAudioId && !isUploading"
        class="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-green-400 transition-colors"
      >
        <input
          type="file"
          accept="audio/*,.mp3,.wav,.m4a,.ogg,.webm"
          @change="handleFileSelect"
          class="hidden"
          id="audio-upload"
        />
        <label for="audio-upload" class="cursor-pointer">
          <Upload class="h-12 w-12 text-gray-400 mx-auto mb-3" />
          <p class="text-gray-600 mb-1">点击上传音频文件</p>
          <p class="text-sm text-gray-400">支持 MP3, WAV, M4A, OGG, WEBM</p>
        </label>
      </div>

      <!-- 上传中 -->
      <div v-if="isUploading" class="text-center py-8">
        <Loader2 class="h-10 w-10 animate-spin text-green-600 mx-auto mb-3" />
        <p class="text-gray-600">正在上传...</p>
      </div>

      <!-- 已上传，准备转录 -->
      <div v-if="uploadedAudioId && !isTranscribing && !transcriptionResult" class="space-y-4">
        <div class="flex items-center gap-3 p-4 bg-green-50 rounded-lg">
          <CheckCircle class="h-5 w-5 text-green-600" />
          <div class="flex-1">
            <p class="text-sm font-medium text-gray-800">{{ uploadedFileName }}</p>
            <p class="text-xs text-gray-500">文件已上传</p>
          </div>
          <button @click="reset" class="text-gray-400 hover:text-gray-600">
            <XCircle class="h-5 w-5" />
          </button>
        </div>

        <label class="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            v-model="generateMinutes"
            class="rounded border-gray-300 text-green-600 focus:ring-green-500"
          />
          生成会议纪要文档
        </label>

        <button
          @click="startTranscription"
          class="w-full flex items-center justify-center gap-2 px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
        >
          <Play class="h-5 w-5" />
          开始转录
        </button>
      </div>

      <!-- 转录中 -->
      <div v-if="isTranscribing" class="text-center py-8">
        <Loader2 class="h-10 w-10 animate-spin text-green-600 mx-auto mb-3" />
        <p class="text-gray-600 mb-2">正在转录音频...</p>
        <p class="text-sm text-gray-400">这可能需要几分钟，请耐心等待</p>
      </div>

      <!-- 转录结果 -->
      <div v-if="transcriptionResult" class="space-y-4">
        <!-- 错误 -->
        <div v-if="transcriptionResult.error" class="bg-red-50 border border-red-200 rounded-lg p-4">
          <div class="flex items-center gap-2 text-red-700">
            <XCircle class="h-5 w-5" />
            <span class="font-medium">转录失败</span>
          </div>
          <p class="text-red-600 mt-2 text-sm">{{ transcriptionResult.error }}</p>
        </div>

        <!-- 成功 -->
        <template v-else>
          <!-- 摘要 -->
          <div v-if="transcriptionResult.summary" class="bg-gray-50 rounded-lg p-4">
            <h4 class="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
              <FileText class="h-4 w-4" />
              会议摘要
            </h4>
            <p class="text-gray-600 text-sm">{{ transcriptionResult.summary }}</p>
          </div>

          <!-- 待办事项 -->
          <div v-if="transcriptionResult.action_items?.length" class="bg-blue-50 rounded-lg p-4">
            <h4 class="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
              <ListChecks class="h-4 w-4" />
              待办事项 ({{ transcriptionResult.action_items.length }})
            </h4>
            <ul class="space-y-2">
              <li
                v-for="(item, index) in transcriptionResult.action_items"
                :key="index"
                class="flex items-start gap-2 text-sm"
              >
                <span class="text-blue-600 font-medium">{{ index + 1 }}.</span>
                <div>
                  <span class="text-gray-700">{{ item.item }}</span>
                  <span v-if="item.owner" class="text-gray-500 ml-2">
                    ({{ item.owner }}<span v-if="item.deadline">, {{ item.deadline }}</span>)
                  </span>
                </div>
              </li>
            </ul>
          </div>

          <!-- 原始转录 -->
          <div v-if="transcriptionResult.transcript">
            <h4 class="text-sm font-semibold text-gray-700 mb-2">原始转录文本</h4>
            <div class="bg-gray-50 rounded-lg p-4 max-h-48 overflow-auto">
              <p class="text-sm text-gray-600 whitespace-pre-wrap">
                {{ transcriptionResult.transcript }}
              </p>
            </div>
          </div>

          <!-- 下载按钮 -->
          <div class="flex gap-2">
            <button
              v-if="transcriptionResult.result_file_id"
              @click="downloadResult"
              class="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
            >
              <Download class="h-4 w-4" />
              下载会议纪要
            </button>
            <button
              @click="reset"
              class="px-4 py-2 text-gray-600 hover:text-gray-800 border border-gray-300 rounded-lg"
            >
              重新上传
            </button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>
