<script setup lang="ts">
import { ref, computed } from "vue";
import {
  AlertTriangle,
  CheckCircle,
  XCircle,
  Info,
  ChevronDown,
  ChevronRight,
  FileText,
  Shield,
} from "lucide-vue-next";

interface Annotation {
  position: string;
  original_text?: string;
  issue_type?: string;
  risk_category?: string;
  severity: string;
  comment?: string;
  mitigation?: string;
  impact?: string;
}

interface ReviewResult {
  review_id: string;
  status: string;
  review_type: string;
  annotations: Annotation[] | null;
  summary: string | null;
  risk_level: string | null;
  error: string | null;
}

const props = defineProps<{
  review: ReviewResult | null;
  loading?: boolean;
}>();

const expandedAnnotations = ref<Set<number>>(new Set());

const toggleAnnotation = (index: number) => {
  if (expandedAnnotations.value.has(index)) {
    expandedAnnotations.value.delete(index);
  } else {
    expandedAnnotations.value.add(index);
  }
};

const riskLevelConfig = computed(() => {
  const level = props.review?.risk_level || "unknown";
  const configs: Record<string, { color: string; bgColor: string; icon: any; label: string }> = {
    critical: { color: "text-red-700", bgColor: "bg-red-100", icon: XCircle, label: "严重风险" },
    high: { color: "text-orange-700", bgColor: "bg-orange-100", icon: AlertTriangle, label: "高风险" },
    medium: { color: "text-yellow-700", bgColor: "bg-yellow-100", icon: Info, label: "中风险" },
    low: { color: "text-green-700", bgColor: "bg-green-100", icon: CheckCircle, label: "低风险" },
    unknown: { color: "text-gray-700", bgColor: "bg-gray-100", icon: Info, label: "未知" },
  };
  return configs[level] || configs.unknown;
});

const severityConfig = (severity: string) => {
  const configs: Record<string, { color: string; bgColor: string }> = {
    high: { color: "text-red-700", bgColor: "bg-red-50 border-red-200" },
    medium: { color: "text-yellow-700", bgColor: "bg-yellow-50 border-yellow-200" },
    low: { color: "text-green-700", bgColor: "bg-green-50 border-green-200" },
  };
  return configs[severity] || configs.medium;
};

const reviewTypeLabel = computed(() => {
  const labels: Record<string, string> = {
    legal: "法律审查",
    compliance: "合规审查",
    risk: "风险评估",
    general: "通用审查",
  };
  return labels[props.review?.review_type || ""] || "文档审查";
});
</script>

<template>
  <div class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
    <!-- 标题栏 -->
    <div class="px-5 py-4 border-b border-gray-100 flex items-center justify-between bg-gradient-to-r from-indigo-50 to-purple-50">
      <div class="flex items-center gap-3">
        <div class="p-2 bg-indigo-100 rounded-lg">
          <Shield class="h-5 w-5 text-indigo-600" />
        </div>
        <div>
          <div class="text-lg font-semibold text-gray-900">{{ reviewTypeLabel }}</div>
          <div class="text-sm text-gray-500">AI 智能审查报告</div>
        </div>
      </div>
      
      <!-- 风险等级标签 -->
      <div
        v-if="review && review.risk_level"
        :class="[riskLevelConfig.bgColor, riskLevelConfig.color]"
        class="flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium"
      >
        <component :is="riskLevelConfig.icon" class="h-4 w-4" />
        {{ riskLevelConfig.label }}
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="p-8 flex flex-col items-center justify-center">
      <div class="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600 mb-4"></div>
      <p class="text-gray-500">正在审查文档...</p>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="review?.error" class="p-6">
      <div class="bg-red-50 border border-red-200 rounded-lg p-4">
        <div class="flex items-center gap-2 text-red-700">
          <XCircle class="h-5 w-5" />
          <span class="font-medium">审查失败</span>
        </div>
        <p class="text-red-600 mt-2 text-sm">{{ review.error }}</p>
      </div>
    </div>

    <!-- 审查结果 -->
    <div v-else-if="review" class="divide-y divide-gray-100">
      <!-- 总结 -->
      <div v-if="review.summary" class="p-5">
        <h3 class="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
          <FileText class="h-4 w-4" />
          审查总结
        </h3>
        <p class="text-gray-600 text-sm leading-relaxed">{{ review.summary }}</p>
      </div>

      <!-- 批注列表 -->
      <div v-if="review.annotations && review.annotations.length > 0" class="p-5">
        <h3 class="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
          <AlertTriangle class="h-4 w-4" />
          发现 {{ review.annotations.length }} 个问题
        </h3>
        
        <div class="space-y-3">
          <div
            v-for="(annotation, index) in review.annotations"
            :key="index"
            :class="severityConfig(annotation.severity).bgColor"
            class="border rounded-lg overflow-hidden"
          >
            <!-- 批注标题 -->
            <button
              @click="toggleAnnotation(index)"
              class="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-white/50 transition-colors"
            >
              <div class="flex items-center gap-3">
                <span
                  :class="severityConfig(annotation.severity).color"
                  class="text-xs font-medium px-2 py-0.5 bg-white rounded"
                >
                  {{ annotation.severity === 'high' ? '高' : annotation.severity === 'medium' ? '中' : '低' }}
                </span>
                <span class="text-sm font-medium text-gray-800">
                  {{ annotation.position }}
                </span>
                <span class="text-sm text-gray-500">
                  {{ annotation.issue_type || annotation.risk_category || '' }}
                </span>
              </div>
              <component
                :is="expandedAnnotations.has(index) ? ChevronDown : ChevronRight"
                class="h-4 w-4 text-gray-400"
              />
            </button>
            
            <!-- 批注详情 -->
            <div
              v-if="expandedAnnotations.has(index)"
              class="px-4 pb-4 pt-0 bg-white/50"
            >
              <div v-if="annotation.original_text" class="mb-3">
                <div class="text-xs text-gray-500 mb-1">原文</div>
                <div class="text-sm text-gray-700 bg-gray-100 rounded p-2 italic">
                  "{{ annotation.original_text }}"
                </div>
              </div>
              
              <div v-if="annotation.comment" class="mb-3">
                <div class="text-xs text-gray-500 mb-1">问题描述</div>
                <div class="text-sm text-gray-700">{{ annotation.comment }}</div>
              </div>
              
              <div v-if="annotation.impact" class="mb-3">
                <div class="text-xs text-gray-500 mb-1">影响</div>
                <div class="text-sm text-gray-700">{{ annotation.impact }}</div>
              </div>
              
              <div v-if="annotation.mitigation">
                <div class="text-xs text-gray-500 mb-1">建议</div>
                <div class="text-sm text-indigo-700 bg-indigo-50 rounded p-2">
                  {{ annotation.mitigation }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 无问题 -->
      <div
        v-else-if="review.annotations && review.annotations.length === 0"
        class="p-8 text-center"
      >
        <CheckCircle class="h-12 w-12 text-green-500 mx-auto mb-3" />
        <p class="text-gray-600">未发现明显问题</p>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="p-8 text-center text-gray-500">
      <Shield class="h-12 w-12 text-gray-300 mx-auto mb-3" />
      <p>选择文档并开始审查</p>
    </div>
  </div>
</template>
