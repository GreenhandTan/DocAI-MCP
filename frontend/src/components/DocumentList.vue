<script setup lang="ts">
import { onMounted, ref } from 'vue'
import axios from 'axios'

interface DocItem {
  file_id: string
  filename: string
  status: string
  is_template: boolean
  created_at: string | null
}

const props = defineProps<{
  selectedContentIds: string[]
  selectedTemplateId: string | null
}>()

const emit = defineEmits<{
  (e: 'active', doc: DocItem): void
  (e: 'edit', fileId: string): void
  (e: 'toggle-content', doc: DocItem): void
  (e: 'set-template', doc: DocItem | null): void
}>()

const docs = ref<DocItem[]>([])
const selectedId = ref<string | null>(null)

const statusText = (status: string) => {
  if (status === 'uploading') return '上传中'
  if (status === 'uploaded') return '已上传'
  if (status === 'processing') return '处理中'
  if (status === 'completed') return '已完成'
  if (status === 'failed') return '失败'
  return status
}

const refresh = async () => {
  const { data } = await axios.get('/api/v1/files')
  docs.value = data
  if (!selectedId.value && docs.value.length > 0) {
    selectedId.value = docs.value[0].file_id
    emit('active', docs.value[0])
  }
}

const choose = (doc: DocItem) => {
  selectedId.value = doc.file_id
  emit('active', doc)
}

const download = (fileId: string) => {
  window.open(`/api/v1/files/${fileId}/download`, '_blank')
}

onMounted(refresh)
</script>

<template>
  <div class="bg-white rounded-xl border border-gray-200 shadow-sm">
    <div class="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
      <div>
        <div class="text-lg font-semibold text-gray-900">文档列表</div>
        <div class="text-sm text-gray-500 mt-1">上传后可选择文档并发起任务或在线编辑</div>
      </div>
      <div class="flex items-center gap-3">
        <button
          v-if="props.selectedTemplateId"
          class="text-sm text-amber-700 hover:text-amber-800"
          @click="$emit('set-template', null)"
        >
          清除模板
        </button>
        <button class="text-sm text-indigo-600 hover:text-indigo-800" @click="refresh">刷新</button>
      </div>
    </div>

    <div class="p-2 max-h-[360px] overflow-auto">
      <button
        v-for="d in docs"
        :key="d.file_id"
        class="w-full text-left p-3 rounded-lg border border-transparent hover:bg-gray-50 flex items-center justify-between"
        :class="selectedId === d.file_id ? 'bg-indigo-50/50 border-indigo-100' : ''"
        @click="choose(d)"
      >
        <div class="min-w-0 flex items-start gap-3">
          <div class="flex flex-col gap-2 pt-0.5">
            <label class="flex items-center gap-2 text-xs text-gray-600">
              <input
                type="checkbox"
                class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                :checked="props.selectedContentIds.includes(d.file_id)"
                @click.stop
                @change="$emit('toggle-content', d)"
              />
              内容
            </label>
            <label class="flex items-center gap-2 text-xs text-gray-600">
              <input
                type="radio"
                name="template-doc"
                class="border-gray-300 text-amber-600 focus:ring-amber-500"
                :checked="props.selectedTemplateId === d.file_id"
                @click.stop
                @change="$emit('set-template', d)"
              />
              模板
            </label>
          </div>
          <div class="min-w-0">
            <div class="font-medium text-gray-900 truncate flex items-center gap-2">
              <span>{{ d.filename }}</span>
              <span v-if="d.is_template" class="text-[10px] px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-100">
                模板
              </span>
            </div>
            <div class="text-xs text-gray-500 mt-1">状态：{{ statusText(d.status) }}</div>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <button
            class="text-xs px-2 py-1 rounded-md bg-indigo-600 text-white"
            @click.stop="$emit('edit', d.file_id)"
          >
            在线编辑
          </button>
          <button
            class="text-xs px-2 py-1 rounded-md bg-gray-100 text-gray-700 hover:bg-gray-200"
            @click.stop="download(d.file_id)"
          >
            下载
          </button>
        </div>
      </button>

      <div v-if="docs.length === 0" class="p-6 text-center text-gray-500">
        暂无文档，请先上传
      </div>
    </div>
  </div>
</template>
