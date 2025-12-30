<script setup lang="ts">
interface Template {
  id: string;
  name: string;
  description: string;
  category: string;
  icon: string;
}

const templates: Template[] = [
  {
    id: "template-resume",
    name: "个人简历",
    description: "专业简历模板，包含个人信息、工作经历、教育背景等模块",
    category: "个人文档",
    icon: "📄",
  },
  {
    id: "template-report",
    name: "项目报告",
    description: "标准项目报告格式，包含摘要、正文、结论等部分",
    category: "商务文档",
    icon: "📊",
  },
  {
    id: "template-contract",
    name: "合同模板",
    description: "通用合同模板，包含条款、签署信息等",
    category: "法律文档",
    icon: "⚖️",
  },
  {
    id: "template-meeting",
    name: "会议纪要",
    description: "会议记录模板，包含参会人员、议题、决议等",
    category: "办公文档",
    icon: "📝",
  },
  {
    id: "template-proposal",
    name: "项目提案",
    description: "项目提案模板，包含背景、目标、计划等",
    category: "商务文档",
    icon: "💡",
  },
  {
    id: "template-invoice",
    name: "发票模板",
    description: "标准发票格式，包含明细、金额、付款信息等",
    category: "财务文档",
    icon: "💰",
  },
];

const props = defineProps<{
  selectedTemplateId: string | null;
}>();

const emit = defineEmits<{
  (e: "select", template: Template): void;
  (e: "clear"): void;
}>();

const selectTemplate = (template: Template) => {
  emit("select", template);
};

const clearTemplate = () => {
  emit("clear");
};
</script>

<template>
  <div class="bg-white rounded-xl border border-gray-200 shadow-sm">
    <div
      class="px-5 py-4 border-b border-gray-100 flex items-center justify-between"
    >
      <div>
        <div class="text-lg font-semibold text-gray-900">模板库</div>
        <div class="text-sm text-gray-500 mt-1">选择预置模板快速开始</div>
      </div>
      <button
        v-if="props.selectedTemplateId"
        @click="clearTemplate"
        class="text-sm text-amber-700 hover:text-amber-800"
      >
        清除选择
      </button>
    </div>

    <div class="p-4 max-h-[400px] overflow-auto space-y-2">
      <button
        v-for="template in templates"
        :key="template.id"
        @click="selectTemplate(template)"
        class="w-full text-left p-4 rounded-lg border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50/30 transition-all"
        :class="
          props.selectedTemplateId === template.id
            ? 'border-indigo-500 bg-indigo-50'
            : ''
        "
      >
        <div class="flex items-start gap-3">
          <div class="text-2xl">{{ template.icon }}</div>
          <div class="flex-1 min-w-0">
            <div class="font-medium text-gray-900">{{ template.name }}</div>
            <div class="text-xs text-gray-500 mt-1">
              {{ template.category }}
            </div>
            <div class="text-sm text-gray-600 mt-2">
              {{ template.description }}
            </div>
          </div>
          <div
            v-if="props.selectedTemplateId === template.id"
            class="text-indigo-600"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              class="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
        </div>
      </button>
    </div>
  </div>
</template>
