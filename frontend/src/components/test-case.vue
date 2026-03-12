<script setup lang="ts">
import { ref, toRaw, watch } from 'vue';
import { ArrowRight, Plus, Delete, Upload } from '@element-plus/icons-vue';
import type { UploadFile, UploadFiles } from 'element-plus';
import { ElUpload, ElButton, ElInput, ElEmpty, ElCard, ElScrollbar } from 'element-plus';

const emit = defineEmits<{
    change: [cases: Array<{ id: string; name: string; input: string; output: string; status?: string | null; tooLarge?: boolean }>];
}>();

type CaseItem = {
    id: string;
    name: string;
    expanded: boolean;
    input: string;
    output: string;
    status?: string | null;
    tooLarge?: boolean;
};

const MAX_EXPANDABLE_CONTENT_SIZE = 50_000;

const createCase = (
    index: number,
    input = '',
    output = '',
    name = `data${index}`,
    tooLarge = false,
): CaseItem => ({
    id: `case-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    name,
    expanded: false,
    input,
    output,
    status: null,
    tooLarge,
});

const manualCases = ref<CaseItem[]>([]);

const toggleExpanded = (item: CaseItem) => {
    if (item.tooLarge) return;
    item.expanded = !item.expanded;
};

const addCase = () => {
    manualCases.value.push(createCase(manualCases.value.length + 1));
};

const removeCase = (id: string) => {
    manualCases.value = manualCases.value.filter((item) => item.id !== id);
};

const pendingPairs = new Map<string, { input?: string; output?: string }>();

const appendMatchedCase = (input: string, output: string) => {
    const index = manualCases.value.length + 1;
    const tooLarge = input.length + output.length > MAX_EXPANDABLE_CONTENT_SIZE;
    manualCases.value.push(createCase(index, input, output, `data${index}`, tooLarge));
};

const importFromFile = async (file: File) => {
    const match = file.name.match(/^(.*)\.(in|out)$/i);
    if (!match) return;

    const baseName = match[1];
    const ext = match[2]?.toLowerCase();
    if (!baseName || !ext) return;
    const content = await file.text();
    const current = pendingPairs.get(baseName) ?? {};

    if (ext === 'in') current.input = content;
    else current.output = content;

    if (current.input != null && current.output != null) {
        appendMatchedCase(current.input, current.output);
        pendingPairs.delete(baseName);
        return;
    }

    pendingPairs.set(baseName, current);
};

const handleUploadChange = async (
    file: UploadFile,
    _uploadFiles: UploadFiles,
) => {
    if (!file.raw) return;
    await importFromFile(file.raw);
};

function getAllCases() {
    return toRaw(manualCases.value);
}

function setCaseStatuses(results: { id: string; status: string }[]) {
    results.forEach((r) => {
        const item = manualCases.value.find((c) => c.id === r.id);
        if (item) item.status = r.status;
    });
}

function clearCaseStatuses() {
    manualCases.value.forEach((item) => {
        item.status = null;
    });
}

const getStatusClass = (status?: string | null) => {
    const normalized = status?.toUpperCase();
    if (!normalized) return '';
    if (normalized === 'AC' || normalized === 'SUCCESS') return 'status-ac';
    if (normalized === 'WA') return 'status-wa';
    if (normalized === 'RE') return 'status-re';
    if (normalized === 'TLE') return 'status-tle';
    return 'status-other';
};

watch(
    manualCases,
    (value) => {
        emit('change', toRaw(value).map((item) => ({ ...item })));
    },
    { deep: true, immediate: true },
);

defineExpose({ getAllCases, setCaseStatuses, clearCaseStatuses });
</script>

<template>
    <el-card class="test-case_card uniform-card" shadow="never">
        <template #header>
            <div class="test-case-header">
                <div class="header-left">
                    <h3>测试样例</h3>
                </div>
                <div class="header-actions">
                    <el-upload class="upload-wrapper" accept=".in,.out" multiple
                        :auto-upload="false" :show-file-list="false" :on-change="handleUploadChange">
                        <el-button type="default" :icon="Upload">从文件导入</el-button>
                    </el-upload>
                    <el-button type="default" :icon="Plus" @click="addCase">新增样例</el-button>
                </div>
            </div>
        </template>

        <el-scrollbar class="cases-scroll">
            <template v-if="manualCases.length === 0">
                <el-empty description="当前没有任何测试样例，请通过手动添加或文件导入创建。" style="width: 100%;" />
            </template>
            <div v-for="item in manualCases" :key="item.id" class="case-item">
                    <div class="case-row" @click="toggleExpanded(item)">
                        <div class="case-title">
                            <ArrowRight class="arrow-icon" :class="{ expanded: item.expanded }" />
                            <span>{{ item.name }}</span>
                        </div>

                        <div class="row-right" @click.stop>
                            <span v-if="item.tooLarge" class="too-large-tip">文件过大不能展开</span>
                            <el-button class="delete-btn" type="danger" size="small" plain :icon="Delete"
                                @click="removeCase(item.id)">删除</el-button>
                            <span v-if="item.status" class="status-badge" :class="getStatusClass(item.status)">
                                {{ item.status }}
                            </span>
                        </div>
                    </div>

                    <div v-if="item.expanded && !item.tooLarge" class="case-detail">
                        <div class="column">
                            <h4>输入（Input）</h4>
                            <el-input type="textarea" v-model="item.input" class="manual-input"
                                placeholder="请输入测试输入内容" />
                        </div>

                        <div class="column">
                            <h4>输出（Output）</h4>
                            <el-input type="textarea" v-model="item.output" class="manual-input"
                                placeholder="请输入期望输出内容" />
                        </div>
                    </div>
                </div>
        </el-scrollbar>

    </el-card>
</template>

<style scoped>
.test-case_card {
    display: flex;
    flex-direction: column;
}

.case-item {
    padding: 0 15px;
    margin-bottom: 8px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background-color: var(--card-bg);
    overflow: hidden;
}

.arrow-icon {
    width: 22px;
    height: 22px;
    color: var(--text-primary);
    transition: transform 0.2s ease;
}

.arrow-icon.expanded {
    transform: rotate(90deg);
}

.status-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 40px;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    line-height: 20px;
    color: #fff;
}

.status-ac {
    background: var(--el-color-success, #67c23a);
}

.status-wa {
    background: var(--el-color-warning, #e6a23c);
}

.status-re,
.status-tle {
    background: var(--el-color-danger, #f56c6c);
}

.status-other {
    background: var(--el-color-info, #909399);
}

.case-detail {
    padding: 0 15px 12px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
}

.case-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    cursor: pointer;
    min-height: 36px;
}

.case-title {
    display: inline-flex;
    align-items: center;
    gap: 20px;
    color: var(--text-primary);
}

.row-right {
    display: flex;
    align-items: center;
    gap: 8px;
}

.too-large-tip {
    color: var(--el-color-warning, #e6a23c);
    font-size: 12px;
    white-space: nowrap;
}

.cases-scroll {
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}
</style>
