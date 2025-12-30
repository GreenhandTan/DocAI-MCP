<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'

const emit = defineEmits(['complete'])
const isUploading = ref(false)
const contentFiles = ref<File[]>([])
const templateFile = ref<File | null>(null)

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files) {
    contentFiles.value = Array.from(target.files)
  }
}

const handleTemplateSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files && target.files[0]) {
    templateFile.value = target.files[0]
  }
}

const upload = async () => {
  if (contentFiles.value.length === 0 && !templateFile.value) return
  
  isUploading.value = true
  const formData = new FormData()
  for (const f of contentFiles.value) {
    formData.append('content_files', f)
  }
  if (templateFile.value) {
    formData.append('template_file', templateFile.value)
  }
  
  try {
    await axios.post('/api/v1/files/upload-batch', formData)
    emit('complete')
    contentFiles.value = []
    templateFile.value = null
    alert('上传成功')
  } catch (e) {
    console.error(e)
    alert('上传失败')
  } finally {
    isUploading.value = false
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="border border-gray-200 rounded-lg p-4 bg-gray-50/40 space-y-2">
      <div class="text-sm font-medium text-gray-900">内容文档（可多选）</div>
      <input type="file" multiple @change="handleFileSelect" class="block w-full text-sm text-gray-500
        file:mr-4 file:py-2 file:px-4
        file:rounded-full file:border-0
        file:text-sm file:font-semibold
        file:bg-indigo-50 file:text-indigo-700
        hover:file:bg-indigo-100" />
      <div v-if="contentFiles.length" class="text-xs text-gray-600">
        已选 {{ contentFiles.length }} 个文件
      </div>
    </div>
    <div class="border border-gray-200 rounded-lg p-4 bg-gray-50/40 space-y-2">
      <div class="text-sm font-medium text-gray-900">模板文档（可选，单选）</div>
      <input type="file" @change="handleTemplateSelect" class="block w-full text-sm text-gray-500
        file:mr-4 file:py-2 file:px-4
        file:rounded-full file:border-0
        file:text-sm file:font-semibold
        file:bg-indigo-50 file:text-indigo-700
        hover:file:bg-indigo-100" />
      <div v-if="templateFile" class="text-xs text-gray-600">
        已选模板：{{ templateFile.name }}
      </div>
    </div>
    <button 
      @click="upload" 
      :disabled="(contentFiles.length === 0 && !templateFile) || isUploading"
      class="w-full bg-indigo-600 text-white py-2 px-4 rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed">
      {{ isUploading ? '上传中...' : '上传文档' }}
    </button>
  </div>
</template>
