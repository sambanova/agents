<template>
  <TransitionRoot appear :show="open" as="template">
    <Dialog as="div" @close="$emit('close')" class="relative z-50">
      <TransitionChild
        enter="ease-out duration-300"
        enter-from="opacity-0"
        enter-to="opacity-100"
        leave="ease-in duration-200"
        leave-from="opacity-100"
        leave-to="opacity-0"
      >
        <div class="fixed inset-0 bg-black bg-opacity-25" />
      </TransitionChild>

      <div class="fixed inset-0 overflow-y-auto">
        <div class="flex min-h-full items-center justify-center p-4">
          <TransitionChild
            enter="ease-out duration-300"
            enter-from="opacity-0 scale-95"
            enter-to="opacity-100 scale-100"
            leave="ease-in duration-200"
            leave-from="opacity-100 scale-100"
            leave-to="opacity-0 scale-95"
          >
            <DialogPanel
              class="w-full max-w-4xl transform overflow-hidden rounded-2xl bg-white p-6 text-left align-middle shadow-xl transition-all"
            >
              <DialogTitle as="h3" class="text-2xl font-bold text-gray-900 mb-6">
              </DialogTitle>

              <div class="mt-4 space-y-8 max-h-[70vh] overflow-y-auto px-2">
                <div
                  v-for="(section, index) in reportData"
                  :key="index"
                  class="mb-8"
                >
                  <!-- Section Title -->
                  <h2 class="text-xl font-bold text-gray-900 mb-4 flex items-center">
                    <BookOpenIcon class="w-5 h-5 text-primary-600 mr-2" />
                    {{ section.title }}
                  </h2>

                  <!-- Content with enhanced markdown styling -->
                  <div 
                    class="prose prose-lg max-w-none"
                    v-html="formatMarkdown(section.generated_content)"
                  ></div>

                  <!-- Elegant divider -->
                  <div
                    v-if="index < reportData.length - 1"
                    class="my-8 flex items-center justify-center"
                  >
                    <div class="border-t border-gray-200 w-full" />
                    <div class="mx-4">
                      <DocumentTextIcon class="w-5 h-5 text-gray-400" />
                    </div>
                    <div class="border-t border-gray-200 w-full" />
                  </div>
                </div>
              </div>

              <!-- Close button -->
              <div class="mt-6 flex justify-end">
                <button
                  @click="$emit('close')"
                  class="inline-flex items-center px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  <XMarkIcon class="w-5 h-5 mr-2" />
                  Close
                </button>
              </div>
            </DialogPanel>
          </TransitionChild>
        </div>
      </div>
    </Dialog>
  </TransitionRoot>
</template>

<script setup>
import {
  Dialog,
  DialogPanel,
  DialogTitle,
  TransitionRoot,
  TransitionChild
} from '@headlessui/vue'
import { XMarkIcon, BookOpenIcon, DocumentTextIcon } from '@heroicons/vue/24/outline'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { ref } from 'vue'

defineProps({
  open: Boolean,
  reportData: {
    type: Array,
    required: true
  }
})

defineEmits(['close'])

const loading = ref(false)

const formatMarkdown = (content) => {
  if (!content) return ''
  const rawHtml = marked(content)
  return DOMPurify.sanitize(rawHtml)
}

const generatePDF = async () => {
  try {
    loading.value = true
    // ... existing code ...
    loading.value = false
  } catch (error) {
    console.error('Error generating PDF:', error)
    loading.value = false
  }
}
</script>

<style scoped>
:deep(.prose) {
  @apply text-gray-600;
}

:deep(.prose h1), :deep(.prose h2), :deep(.prose h3) {
  @apply text-gray-900 font-semibold mt-6 mb-4;
}

:deep(.prose h1) {
  @apply text-2xl;
}

:deep(.prose h2) {
  @apply text-xl;
}

:deep(.prose h3) {
  @apply text-lg;
}

:deep(.prose p) {
  @apply mb-4 leading-relaxed;
}

:deep(.prose ul) {
  @apply list-disc list-inside mb-4 space-y-2;
}

:deep(.prose ol) {
  @apply list-decimal list-inside mb-4 space-y-2;
}

:deep(.prose li) {
  @apply text-gray-700;
}

:deep(.prose a) {
  @apply text-blue-600 hover:underline;
}

:deep(.prose code) {
  @apply bg-gray-100 px-1.5 py-0.5 rounded text-sm font-mono;
}

:deep(.prose pre) {
  @apply bg-gray-100 p-4 rounded-lg overflow-x-auto my-4;
}

:deep(.prose blockquote) {
  @apply border-l-4 border-gray-200 pl-4 italic my-4;
}

:deep(.prose strong) {
  @apply font-semibold text-gray-900;
}

:deep(.prose img) {
  @apply rounded-lg my-4;
}

:deep(.prose table) {
  @apply w-full my-4;
}

:deep(.prose td), :deep(.prose th) {
  @apply border p-2;
}
</style>