<template>
    <div>
        <div class="file-summary">服务器当前文件数：{{ availableFiles.length }}</div>
        <div class="file-download-buttons">
            <el-button type="default" @click="download('all.zip')" style="width: 100%;">一键下载全部文件</el-button>
        </div>
        <div v-if="availableFiles.length" class="file-list">
            <h4>已生成文件：</h4>
            <ul>
                <li v-for="f in availableFiles" :key="f">
                    <el-button type="text" @click="download(f)">{{ f }}</el-button>
                </li>
            </ul>
        </div>


    </div>
</template>

<script setup lang="ts">
import { ElButton } from 'element-plus';
import { ref, onMounted } from 'vue';
import { listFiles, downloadFile } from '../api';

const props = defineProps<{
    uuid: string;
}>();

const availableFiles = ref<string[]>([]);

const loadFiles = async () => {
    try {
        availableFiles.value = await listFiles(props.uuid);
    } catch (err) {
        availableFiles.value = [];
        console.error('获取文件列表失败', err);
    }
};

const download = async (file: string) => {
    try {
        // `file` should be the raw name returned by listFiles, e.g. "all.zip"
        console.debug('请求下载', file, 'uuid=', props.uuid);
        const blob = await downloadFile(file, props.uuid);
        console.debug('收到 blob 大小', blob.size);
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = file;
        a.click();
        URL.revokeObjectURL(url);
    } catch (err) {
        console.error('下载失败', err);
        // 这里可以添加通知
    }
};

onMounted(loadFiles);

defineExpose({ loadFiles });
</script>

<style scoped>
.file-summary {
    margin-bottom: 12px;
    color: var(--text-primary);
    font-size: 14px;
}

.file-download-buttons {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.file-list {
    margin-top: 12px;
}

.file-list ul {
    list-style: none;
    padding: 0;
}

.file-list li {
    margin: 4px 0;
}
</style>
