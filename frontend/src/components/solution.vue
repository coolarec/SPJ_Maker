<script setup lang="ts">
import MonacoEditor from 'monaco-editor-vue3';
import { ElCard } from 'element-plus';
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
    <el-card class="editor-container uniform-card" shadow="never">
        <template #header>
            <div class="test-case-header">
                <div class="header-left">
                    <h3>STD</h3>
                </div>
                <div class="header-actions"></div>
            </div>
        </template>
        <div class="editor-inner">
            <div class="editor-surface">
                <MonacoEditor
                    v-if="editorReady"
                    :key="editorTheme"
                    v-model:value="code"
                    language="cpp"
                    :theme="editorTheme"
                    :options="{
                        automaticLayout: true,
                        fontSize: 16,
                        minimap: { enabled: false },
                        scrollBeyondLastLine: false,
                        wordWrap: 'on',
                    }"
                />
            </div>
        </div>
    </el-card>
</template>

<style scoped>
.editor-container {
    box-sizing: border-box;
    overflow: hidden;
}

.editor-inner {
    padding: 15px;
}

.editor-surface {
    height: 450px;
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
    background: var(--muted-bg);
}
</style>