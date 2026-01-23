<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import axios from "axios";
import {
  Play,
  Plus,
  Trash2,
  Settings,
  FileText,
  Cpu,
  Shield,
  Mic,
  ArrowRight,
  Loader2,
  CheckCircle,
  XCircle,
  Save,
} from "lucide-vue-next";

interface WorkflowNode {
  id: string;
  type: string;
  label: string;
  config: Record<string, any>;
  position: { x: number; y: number };
}

interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
}

interface Workflow {
  workflow_id: string;
  name: string;
  description: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

const emit = defineEmits<{
  (e: "execute", workflowId: string, fileIds: string[]): void;
}>();

const props = defineProps<{
  selectedFileIds?: string[];
}>();

const workflows = ref<Workflow[]>([]);
const selectedWorkflow = ref<Workflow | null>(null);
const isLoading = ref(false);
const isSaving = ref(false);
const isExecuting = ref(false);
const executionStatus = ref<string>("");

// 新建工作流
const newWorkflowName = ref("");
const newWorkflowDescription = ref("");
const editingNodes = ref<WorkflowNode[]>([]);
const editingEdges = ref<WorkflowEdge[]>([]);
const showEditor = ref(false);

// 可用节点类型
const nodeTypes = [
  { type: "content_extractor", label: "内容提取", icon: FileText, color: "bg-blue-100 text-blue-700" },
  { type: "document_analyzer", label: "文档分析", icon: Cpu, color: "bg-purple-100 text-purple-700" },
  { type: "document_reviewer", label: "文档审查", icon: Shield, color: "bg-orange-100 text-orange-700" },
  { type: "audio_transcriber", label: "音频转录", icon: Mic, color: "bg-green-100 text-green-700" },
  { type: "ai_processor", label: "AI处理", icon: Cpu, color: "bg-indigo-100 text-indigo-700" },
  { type: "document_generator", label: "生成文档", icon: FileText, color: "bg-pink-100 text-pink-700" },
];

const getNodeType = (type: string) => nodeTypes.find(n => n.type === type) || nodeTypes[0];

const generateId = () => Math.random().toString(36).substring(2, 10);

const loadWorkflows = async () => {
  isLoading.value = true;
  try {
    const response = await axios.get("/api/v1/workflows");
    workflows.value = response.data;
  } catch (error) {
    console.error("Failed to load workflows:", error);
  } finally {
    isLoading.value = false;
  }
};

const addNode = (type: string) => {
  const nodeType = getNodeType(type);
  const newNode: WorkflowNode = {
    id: generateId(),
    type,
    label: nodeType.label,
    config: {},
    position: { x: 100 + editingNodes.value.length * 50, y: 100 + editingNodes.value.length * 30 },
  };
  editingNodes.value.push(newNode);
  
  // 自动连接到上一个节点
  if (editingNodes.value.length > 1) {
    const prevNode = editingNodes.value[editingNodes.value.length - 2];
    editingEdges.value.push({
      id: generateId(),
      source: prevNode.id,
      target: newNode.id,
    });
  }
};

const removeNode = (nodeId: string) => {
  editingNodes.value = editingNodes.value.filter(n => n.id !== nodeId);
  editingEdges.value = editingEdges.value.filter(e => e.source !== nodeId && e.target !== nodeId);
};

const saveWorkflow = async () => {
  if (!newWorkflowName.value.trim()) {
    alert("请输入工作流名称");
    return;
  }
  if (editingNodes.value.length === 0) {
    alert("请添加至少一个节点");
    return;
  }
  
  isSaving.value = true;
  try {
    const response = await axios.post("/api/v1/workflows/create", {
      name: newWorkflowName.value,
      description: newWorkflowDescription.value,
      nodes: editingNodes.value,
      edges: editingEdges.value,
    });
    
    await loadWorkflows();
    showEditor.value = false;
    newWorkflowName.value = "";
    newWorkflowDescription.value = "";
    editingNodes.value = [];
    editingEdges.value = [];
  } catch (error) {
    console.error("Failed to save workflow:", error);
    alert("保存失败");
  } finally {
    isSaving.value = false;
  }
};

const executeWorkflow = async (workflow: Workflow) => {
  if (!props.selectedFileIds || props.selectedFileIds.length === 0) {
    alert("请先选择输入文件");
    return;
  }
  
  isExecuting.value = true;
  executionStatus.value = "执行中...";
  
  try {
    const response = await axios.post("/api/v1/workflows/execute", {
      workflow_id: workflow.workflow_id,
      input_file_ids: props.selectedFileIds,
    });
    
    const executionId = response.data.execution_id;
    
    // 轮询执行状态
    const checkStatus = async () => {
      const statusResponse = await axios.get(`/api/v1/workflows/executions/${executionId}`);
      const status = statusResponse.data.status;
      executionStatus.value = `状态: ${status}${statusResponse.data.current_node ? ` (${statusResponse.data.current_node})` : ''}`;
      
      if (status === "completed" || status === "failed") {
        isExecuting.value = false;
        if (status === "completed") {
          emit("execute", workflow.workflow_id, props.selectedFileIds || []);
        }
        return;
      }
      
      setTimeout(checkStatus, 2000);
    };
    
    checkStatus();
  } catch (error) {
    console.error("Failed to execute workflow:", error);
    isExecuting.value = false;
    executionStatus.value = "执行失败";
  }
};

const startNewWorkflow = () => {
  showEditor.value = true;
  editingNodes.value = [];
  editingEdges.value = [];
  newWorkflowName.value = "";
  newWorkflowDescription.value = "";
};

onMounted(() => {
  loadWorkflows();
});
</script>

<template>
  <div class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
    <!-- 标题栏 -->
    <div class="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
      <div>
        <div class="text-lg font-semibold text-gray-900">工作流编排</div>
        <div class="text-sm text-gray-500">创建和执行自动化处理流程</div>
      </div>
      <button
        @click="startNewWorkflow"
        class="flex items-center gap-2 px-3 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm"
      >
        <Plus class="h-4 w-4" />
        新建工作流
      </button>
    </div>

    <!-- 工作流编辑器 -->
    <div v-if="showEditor" class="p-5 border-b border-gray-100 bg-gray-50">
      <div class="mb-4">
        <input
          v-model="newWorkflowName"
          type="text"
          placeholder="工作流名称"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
        />
      </div>
      <div class="mb-4">
        <textarea
          v-model="newWorkflowDescription"
          placeholder="描述（可选）"
          rows="2"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
        ></textarea>
      </div>

      <!-- 节点类型选择 -->
      <div class="mb-4">
        <div class="text-sm font-medium text-gray-700 mb-2">添加节点</div>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="nodeType in nodeTypes"
            :key="nodeType.type"
            @click="addNode(nodeType.type)"
            :class="nodeType.color"
            class="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium hover:opacity-80 transition-opacity"
          >
            <component :is="nodeType.icon" class="h-4 w-4" />
            {{ nodeType.label }}
          </button>
        </div>
      </div>

      <!-- 当前节点列表 -->
      <div v-if="editingNodes.length > 0" class="mb-4">
        <div class="text-sm font-medium text-gray-700 mb-2">工作流节点</div>
        <div class="flex items-center flex-wrap gap-2">
          <template v-for="(node, index) in editingNodes" :key="node.id">
            <div
              :class="getNodeType(node.type).color"
              class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm"
            >
              <component :is="getNodeType(node.type).icon" class="h-4 w-4" />
              <span>{{ node.label }}</span>
              <button
                @click="removeNode(node.id)"
                class="ml-1 hover:opacity-70"
              >
                <Trash2 class="h-3 w-3" />
              </button>
            </div>
            <ArrowRight
              v-if="index < editingNodes.length - 1"
              class="h-4 w-4 text-gray-400"
            />
          </template>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="flex gap-2">
        <button
          @click="saveWorkflow"
          :disabled="isSaving"
          class="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 text-sm"
        >
          <Save v-if="!isSaving" class="h-4 w-4" />
          <Loader2 v-else class="h-4 w-4 animate-spin" />
          保存工作流
        </button>
        <button
          @click="showEditor = false"
          class="px-4 py-2 text-gray-600 hover:text-gray-800 text-sm"
        >
          取消
        </button>
      </div>
    </div>

    <!-- 工作流列表 -->
    <div class="p-4 max-h-[400px] overflow-auto">
      <div v-if="isLoading" class="flex justify-center py-8">
        <Loader2 class="h-8 w-8 animate-spin text-indigo-600" />
      </div>
      
      <div v-else-if="workflows.length === 0" class="text-center py-8 text-gray-500">
        <Settings class="h-12 w-12 mx-auto mb-3 text-gray-300" />
        <p>暂无工作流</p>
        <p class="text-sm">点击"新建工作流"创建第一个</p>
      </div>
      
      <div v-else class="space-y-3">
        <div
          v-for="workflow in workflows"
          :key="workflow.workflow_id"
          class="border border-gray-200 rounded-lg p-4 hover:border-indigo-300 transition-colors"
        >
          <div class="flex items-start justify-between mb-3">
            <div>
              <div class="font-medium text-gray-900">{{ workflow.name }}</div>
              <div v-if="workflow.description" class="text-sm text-gray-500 mt-1">
                {{ workflow.description }}
              </div>
            </div>
            <button
              @click="executeWorkflow(workflow)"
              :disabled="isExecuting || !selectedFileIds?.length"
              class="flex items-center gap-2 px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm"
            >
              <Play v-if="!isExecuting" class="h-4 w-4" />
              <Loader2 v-else class="h-4 w-4 animate-spin" />
              执行
            </button>
          </div>
          
          <!-- 节点预览 -->
          <div class="flex items-center flex-wrap gap-2 text-xs">
            <template v-for="(node, index) in workflow.nodes" :key="node.id">
              <div
                :class="getNodeType(node.type).color"
                class="flex items-center gap-1 px-2 py-1 rounded"
              >
                <component :is="getNodeType(node.type).icon" class="h-3 w-3" />
                {{ node.label }}
              </div>
              <ArrowRight
                v-if="index < workflow.nodes.length - 1"
                class="h-3 w-3 text-gray-400"
              />
            </template>
          </div>
        </div>
      </div>
    </div>

    <!-- 执行状态 -->
    <div
      v-if="executionStatus"
      class="px-4 py-3 bg-gray-50 border-t border-gray-100 text-sm text-gray-600"
    >
      {{ executionStatus }}
    </div>
  </div>
</template>
