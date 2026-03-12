<script setup lang="ts">
import { ref, onBeforeUnmount, onMounted, watch } from 'vue';
import Editor from './components/editor.vue';
import TestCase from './components/test-case.vue';
import FileDowload from './components/file-dowload.vue';
import Solution from './components/solution.vue';
import { ElContainer, ElHeader, ElMain, ElAside, ElButton } from 'element-plus';
import { ElMessage } from 'element-plus';
import { ElMessageBox } from 'element-plus';

import { submitDataAndStd } from './api';
import type { DataStdInput } from './api';

import { Moon, Sunny, Opportunity } from '@element-plus/icons-vue';
const createPageUuid = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const pageUuid = ref(createPageUuid());

const onHeaderMouseMove = (event: MouseEvent) => {
  const card = event.currentTarget as HTMLElement | null;
  if (!card) return;

  const rect = card.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;

  card.style.setProperty('--mx', `${x}px`);
  card.style.setProperty('--my', `${y}px`);
};

const isCodeSubmitted = ref(true);
const isDark = ref(false);
const submittingData = ref(false);
const hasStoredThemePreference = ref(false);
const themeReady = ref(false);
let prefersDarkMedia: MediaQueryList | null = null;

const handlePrefersDarkChange = (event: MediaQueryListEvent) => {
  try {
    const stored = localStorage.getItem('spj_theme');
    if (stored === 'dark' || stored === 'light') return;
  } catch (e) {
    /* ignore */
  }

  isDark.value = event.matches;
};

const spjCode = ref('');
const stdCode = ref('');
const currentCases = ref<Array<{ id?: string; name?: string; input?: string; output?: string }>>([]);
const editorRef = ref<any>(null);
const testCaseRef = ref<any>(null);
const solutionRef = ref<any>(null);
const fileDownloadRef = ref<any>(null);

const handleCasesChange = (cases: Array<{ id?: string; name?: string; input?: string; output?: string }>) => {
  currentCases.value = cases;
};

const hasValidCases = (cases: Array<{ input?: string; output?: string }>) =>
  cases.some((item) => (item.input ?? '').trim() !== '' || (item.output ?? '').trim() !== '');

const validateBeforeSubmit = (
  spjCode: string,
  stdCode: string,
  cases: Array<{ input?: string; output?: string }>
) => {
  const hasCases = hasValidCases(cases);
  const spjEmpty = spjCode === '';
  const stdEmpty = stdCode === '';

  if (hasCases && spjEmpty && stdEmpty) {
    ElMessage.warning('存在测试样例时，必须同时填写 SPJ 和 STD 代码后才能提交');
    return false;
  }
  if (hasCases && spjEmpty) {
    ElMessage.warning('存在测试样例时，必须填写 SPJ 代码后才能提交');
    return false;
  }
  if (hasCases && stdEmpty) {
    ElMessage.warning('存在测试样例时，必须填写 STD 代码后才能提交');
    return false;
  }
  if (spjEmpty) {
    ElMessage.warning('必须填写 SPJ 代码后才能提交');
    return false;
  }
  return true;
};

const buildSubmitResultMessage = (res: { success?: boolean; message?: string; cases?: Array<{ status: string }> }) => {
  const lines: string[] = [];

  lines.push(res.success ? '生成完成。' : '生成失败。');
  if (res.message) {
    lines.push(`说明：${res.message}`);
  }

  if (res.cases?.length) {
    const summary = res.cases.reduce<Record<string, number>>((acc, item) => {
      const key = (item.status || 'UNKNOWN').toUpperCase();
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});

    lines.push('');
    lines.push('测试点结果：');
    Object.entries(summary).forEach(([status, count]) => {
      lines.push(`${status}: ${count}`);
    });
  }

  return lines.join('\n');
};

const syncDocumentTheme = (dark: boolean) => {
  if (typeof document === 'undefined') return;

  const classNames = ['dark', 'el-theme-dark'];
  [document.documentElement, document.body].forEach((element) => {
    classNames.forEach((className) => {
      element.classList.toggle(className, dark);
    });
  });

  document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
};

const handleSubmitData = async () => {
  const currentSpjCode = (spjCode.value || (editorRef.value?.getCode?.() as string | undefined) || '').trim();
  const currentStdCode = (stdCode.value || (solutionRef.value?.getCode?.() as string | undefined) || '').trim();
  spjCode.value = currentSpjCode;
  stdCode.value = currentStdCode;

  const cases = testCaseRef.value?.getAllCases?.() || currentCases.value;
  currentCases.value = cases;

  if (!validateBeforeSubmit(currentSpjCode, currentStdCode, cases)) {
    return;
  }

  const payload: DataStdInput = {
    uuid: pageUuid.value,
    spjCode: currentSpjCode,
    stdCode: currentStdCode,
    cases,
  };

  submittingData.value = true;
  try {
    const res = await submitDataAndStd(payload);
    console.log('submitDataAndStd result', res);
    if (res.cases && testCaseRef.value?.setCaseStatuses) {
      testCaseRef.value.setCaseStatuses(res.cases);
    }
    await fileDownloadRef.value?.loadFiles?.();

    await ElMessageBox.alert(buildSubmitResultMessage(res), '提交结果', {
      confirmButtonText: '知道了',
      type: res.success ? 'success' : 'warning',
    });
  } catch (e) {
    console.error('submitDataAndStd failed', e);
    ElMessage.error('提交失败，请稍后重试');
  } finally {
    submittingData.value = false;
  }
};

const toggleTheme = () => {
  hasStoredThemePreference.value = true;
  isDark.value = !isDark.value;
};

onMounted(() => {
  try {
    const stored = localStorage.getItem('spj_theme');
    if (stored === 'dark' || stored === 'light') {
      hasStoredThemePreference.value = true;
      isDark.value = stored === 'dark';
    } else if (typeof window !== 'undefined' && 'matchMedia' in window) {
      prefersDarkMedia = window.matchMedia('(prefers-color-scheme: dark)');
      isDark.value = prefersDarkMedia.matches;
    }
  } catch (e) {
    if (typeof window !== 'undefined' && 'matchMedia' in window) {
      prefersDarkMedia = window.matchMedia('(prefers-color-scheme: dark)');
      isDark.value = prefersDarkMedia.matches;
    }
  }

  if (!prefersDarkMedia && typeof window !== 'undefined' && 'matchMedia' in window) {
    prefersDarkMedia = window.matchMedia('(prefers-color-scheme: dark)');
  }

  prefersDarkMedia?.addEventListener?.('change', handlePrefersDarkChange);
  themeReady.value = true;
});

onBeforeUnmount(() => {
  prefersDarkMedia?.removeEventListener?.('change', handlePrefersDarkChange);
});

watch(isDark, (val) => {
  syncDocumentTheme(val);
  if (!themeReady.value || !hasStoredThemePreference.value) return;

  try {
    localStorage.setItem('spj_theme', val ? 'dark' : 'light');
  } catch (e) {
    /* ignore */
  }
}, { immediate: true });

watch(stdCode, () => {
  testCaseRef.value?.clearCaseStatuses?.();
});

</script>

<template>
  <div class="layout" :class="{ dark: isDark, 'el-theme-dark': isDark }">
    <el-container direction="horizontal">
      <el-aside class="app-aside"></el-aside>
      <el-container class="app-content">
        <el-header class="app-header">
          <div class="header-card" @mousemove="onHeaderMouseMove">
            <h1 class="header-title">SPJ Maker</h1>
            <p class="header-subtitle">Test Your Special Judge Code with Ease</p>
            <p class="header-uuid">UUID: {{ pageUuid }}</p>
          </div>
        </el-header>

        <el-main>
          <div>
            <Editor ref="editorRef" v-model="spjCode" :uuid="pageUuid" :is-dark="isDark"></Editor>
            <div style="margin-top: 20px;" v-show="isCodeSubmitted" class="cases-two-col">
              <TestCase ref="testCaseRef" :uuid="pageUuid" @change="handleCasesChange"></TestCase>
              <Solution ref="solutionRef" v-model="stdCode" :uuid="pageUuid" :is-dark="isDark"></Solution>
            </div>
            <el-button
              type="default"
              style="margin-top: 20px;width: 100%;"
              :icon="Opportunity"
              :loading="submittingData"
              :disabled="submittingData"
              @click="handleSubmitData"
            >
              提交数据及STD以生成文件
            </el-button>
            <FileDowload ref="fileDownloadRef" :uuid="pageUuid" style="margin-top: 20px;" v-show="isCodeSubmitted"></FileDowload>
          </div>
        </el-main>
      </el-container>
      <el-aside class="app-aside"></el-aside>
      </el-container>
    <div class="theme-toggle">
      <el-button circle class="theme-btn" type="primary" size="large" @click="toggleTheme" title="切换主题">
        <Moon v-if="!isDark" />
        <Sunny v-else />
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.layout {
  background: var(--bg);
  min-height: 100vh;
  overflow-x: hidden;
}

.app-aside {
  flex: 0 0 200px;
  width: 200px;
  justify-content: center;
  transition: width 280ms ease, flex-basis 280ms ease;
}



.app-content {
  margin: 20px;
  min-width: 0;
  transition: margin 280ms ease;
}

.app-header {
  padding: 0;
  height: auto;
  margin-bottom: 16px;
  transition: margin-bottom 280ms ease;
}

.header-card {
  --mx: 50%;
  --my: 50%;
  position: relative;
  width: 100%;
  box-sizing: border-box;
  min-width: 0;
  border-radius: 18px;
  padding: 30px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
  overflow: hidden;
  -webkit-user-select: none;
  user-select: none;
  transition:
    box-shadow 180ms ease,
    border-radius 280ms ease,
    padding 280ms ease,
    transform 280ms ease;
}

.header-card::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle 140px at var(--mx) var(--my),
      var(--spot1),
      var(--spot2) 38%,
      var(--spot3) 75%);
  pointer-events: none;
  opacity: 0;
  transition: opacity 180ms ease;
}

.header-card:hover {
  box-shadow:
    0 18px 36px rgba(0, 0, 0, 0.22),
    0 6px 14px rgba(0, 0, 0, 0.1);
}

.header-card:hover::before {
  opacity: 1;
}

.header-title,
.header-subtitle,
.header-uuid {
  position: relative;
  z-index: 1;
  margin: 0;
  color: var(--text-primary);
  text-align: center;
  -webkit-user-select: none;
  user-select: none;
}

.header-title {
  font-size: 32px;
  font-weight: 700;
  letter-spacing: 0.4px;
  transition: font-size 280ms ease;
}

.header-subtitle {
  margin-top: 8px;
  font-size: 16px;
  color: var(--text-muted);
  transition: font-size 280ms ease, margin-top 280ms ease;
}

.header-uuid {
  margin-top: 12px;
  font-size: 13px;
  color: var(--text-muted2);
  transition: font-size 280ms ease, margin-top 280ms ease;
}

/* theme variables moved to src/styles/theme.css */

@media (max-width: 1000px) {
  .app-content {
    margin: 20px;
  }

  .header-card {
    border-radius: 14px;
    padding: 18px;
  }

  .header-title {
    font-size: 26px;
  }

  .header-subtitle {
    margin-top: 6px;
    font-size: 14px;
  }

  .header-uuid {
    margin-top: 10px;
    font-size: 12px;
  }

  .app-aside {
    width: 0 !important;
    flex: 0 0 0 !important;
    overflow: hidden;
  }
}

.cases-two-col {
  display: flex;
  gap: 20px;
}
.cases-two-col > * {
  flex: 1;
  min-width: 0;
}

@media (max-width: 950px) {
  .cases-two-col {
    flex-direction: column;
  }
}

.theme-toggle {
  color: var(--text-primary);
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 9999;
}

.theme-toggle .theme-btn {
  background: var(--card-bg);
  border-color: var(--border);
  color: var(--text-primary);
  box-shadow: var(--shadow);
  width: 56px;
  height: 56px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: transform 180ms ease, box-shadow 180ms ease, background-color 180ms ease;
}

.theme-toggle .theme-btn:hover {
  transform: translateY(-2px);
}

.theme-toggle .theme-btn svg {
  width: 22px;
  height: 22px;
}

@media (prefers-reduced-motion: reduce) {

  .app-aside,
  .app-content,
  .app-header,
  .header-card,
  .header-card::before,
  .header-title,
  .header-subtitle,
  .header-uuid {
    transition: none !important;
  }
}
</style>
