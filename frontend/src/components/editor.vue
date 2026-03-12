<script setup lang="ts">
import MonacoEditor from 'monaco-editor-vue3';
import { computed, ref, onMounted, watch } from 'vue';
const props = defineProps<{
    uuid: string;
    isDark?: boolean;
    modelValue?: string;
}>();

const emit = defineEmits<{
    change: [code: string];
    'update:modelValue': [code: string];
}>();

const code = ref(props.modelValue ?? '');
const editorTheme = computed(() => (props.isDark ? 'vs-dark' : 'vs-light'));

// only render MonacoEditor after component mounted to ensure container exists
const editorReady = ref(false);
onMounted(() => {
    editorReady.value = true;
});

watch(code, (value) => {
    emit('update:modelValue', value);
    emit('change', value);
});

watch(
    () => props.modelValue,
    (value) => {
        const nextValue = value ?? '';
        if (nextValue !== code.value) {
            code.value = nextValue;
        }
    }
);

function getCode() {
    return code.value;
}

defineExpose({ getCode });
</script>

<template>
    <div class="editor-container">
        <div class="test-case-header editor-header">
            <h3>SPJ 编辑器</h3>
        </div>
        <div class="editor-surface">
            <MonacoEditor v-if="editorReady" :key="editorTheme" v-model:value="code" language="cpp" :theme="editorTheme"
                :options="{
                    automaticLayout: true,
                    fontSize: 16,
                    minimap: { enabled: false },
                    scrollBeyondLastLine: false,
                    wordWrap: 'on',
                }" />
        </div>
    </div>
</template>

<style scoped>
.editor-container {
    border: 1px solid var(--border);
    border-radius: 8px;
    background-color: var(--card-bg);
    box-sizing: border-box;
    overflow: hidden;
    padding: 15px;
}

.editor-surface {
    height: 500px;
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
    background: var(--muted-bg);
}

.editor-actions {
    width: 100%;
    display: flex;
    flex-direction: row-reverse;
    padding: 16px 8px 12px;
    gap: 8px;
}

.action-btn {
    margin: 0 15px 0 0;
    width: 120px;
}
</style>