import axios from 'axios';

// 代码提交相关类型（编辑器用）
export interface CodeInput {
    code: string;
    uuid: string;
}
export interface CodeOutput {
    result: string;
    error: string;
}

// 测试用例处理返回结果类型
export interface CaseProcessResult {
    id: string;
    status: string;
}

// --- API wrappers -----------------------------------------------------------



/**
 * 发送文件模式的测试用例到后端处理，返回每个用例的状态
 */
export async function processCases(cases: any[]): Promise<CaseProcessResult[]> {
    const resp = await axios.post<CaseProcessResult[]>('/spjmaker/api/process', { cases });
    return resp.data;
}

/**
 * 从服务器获取可下载文件列表
 */
export async function listFiles(uuid?: string): Promise<string[]> {
    const resp = await axios.get<string[]>('/spjmaker/api/files', {
        params: uuid ? { uuid } : undefined,
    });

    if (!Array.isArray(resp.data)) {
        console.error('文件列表接口返回了非数组数据：', resp.data);
        return [];
    }

    return resp.data;
}

/**
 * 下载指定名称的文件；返回 Blob 供调用方处理
 */
export async function downloadFile(name: string, uuid?: string): Promise<Blob> {
    // perform request and sanity-check result so callers can detect when the
    // server returned an error disguised as an empty blob.
    const resp = await axios.get(`/spjmaker/api/download/${encodeURIComponent(name)}`, {
        params: uuid ? { uuid } : undefined,
        responseType: 'blob',
        validateStatus: status => true, // we'll handle non-200 ourselves
    });

    if (resp.status !== 200) {
        throw new Error(`下载请求返回状态 ${resp.status}`);
    }
    const blob = resp.data as Blob;
    if (blob.size === 0) {
        throw new Error(`接收到的文件大小为 0`);
    }
    return blob;
}

// payload used when submitting all data and STD to generate files
export interface DataStdInput {
    uuid: string;
    spjCode?: string;
    stdCode?: string;
    cases?: any[];
}

/**
 * 发送当前所有信息到后端，让服务器生成需要运行结果
 */
export interface DataStdResult {
    success: boolean;
    message?: string;
    cases?: CaseProcessResult[];
}

export async function submitDataAndStd(payload: DataStdInput): Promise<DataStdResult> {
    const resp = await axios.post<DataStdResult>('/spjmaker/api/submit-data', payload);
    return resp.data;
}