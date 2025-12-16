/**
 * SSE (Server-Sent Events) 处理模块
 * 完全透明的流式通信，零黑盒
 */

class SSEClient {
    constructor() {
        this.eventSource = null;
        this.onThinking = null;
        this.onProgress = null;
        this.onFinal = null;
        this.onError = null;
        this.onDone = null;
        this.onContextStats = null;
        this.onCompressionStart = null;
        this.onCompressionDone = null;
        this.onFilesGenerated = null;
        this.onPlanUpdate = null;
        this.onThinkingStart = null;
        // iter grouped new handlers
        this.onIterStart = null;
        this.onIterDone = null;
        this.onNote = null;
        this.onExec = null;
    }

    /**
     * 发送消息并建立SSE连接
     * @param {string} message - 用户消息
     * @param {string} model - 模型名称
     * @param {string} conversationId - 对话ID
     */
    send(message, model = 'gpt-5.2', conversationId, clientMsgId) {
        // 关闭之前的连接
        this.close();

        // 构造URL
        const baseUrl = `/chat?message=${encodeURIComponent(message)}`;
        const modelParam = `&model=${encodeURIComponent(model)}`;
        const convParam = `&conversation_id=${encodeURIComponent(conversationId)}`;
        let url = baseUrl + modelParam + convParam;
        if (clientMsgId) {
            url += `&client_msg_id=${encodeURIComponent(clientMsgId)}`;
        }

        // 创建EventSource
        this.eventSource = new EventSource(url);

        // 监听消息
        this.eventSource.onmessage = (e) => {
            try {
                // 检查结束标记
                if (e.data === '[DONE]') {
                    console.log('[SSE] 流式传输完成');
                    this.close();
                    if (this.onDone) {
                        this.onDone();
                    }
                    return;
                }

                // 解析JSON
                const update = JSON.parse(e.data);
                console.log('[SSE] 收到更新:', update.type);

                // 根据类型分发
                this.dispatch(update);

            } catch (err) {
                console.error('[SSE] 解析消息失败:', err, e.data);
            }
        };

        // 监听错误
        this.eventSource.onerror = (e) => {
            console.error('[SSE] 连接错误:', e);

            // 通知错误处理器
            if (this.onError) {
                this.onError({
                    message: 'SSE连接中断',
                    event: e
                });
            }

            this.close();
        };

        console.log('[SSE] 连接已建立:', url);
    }

    /**
     * 分发更新到对应的处理器
     * @param {Object} update - 更新对象
     */
    dispatch(update) {
        console.log('[SSE] 分发消息:', update.type, update);

        switch (update.type) {
            case 'iter_start':
                if (this.onIterStart) {
                    this.onIterStart(update.iter);
                }
                break;
            case 'iter_done':
                if (this.onIterDone) {
                    this.onIterDone(update.iter, update.status);
                }
                break;
            case 'thinking_start':
                console.log('[SSE] 处理thinking_start:', update.iter);
                if (this.onIterStart) {
                    this.onIterStart(update.iter);
                }
                break;
            case 'thinking':
                console.log('[SSE] 处理thinking消息:', update.content);
                if (this.onThinking) {
                    this.onThinking(update.content || '', update.iter);
                }
                break;

            case 'tool_call_text':
                console.log('[SSE] 处理tool_call_text消息:', update.content);
                if (this.onNote) {
                    this.onNote(update.content || update.delta || '', update.iter);
                }
                break;

            case 'note':
                if (this.onNote) {
                    this.onNote(update.delta || '', update.iter);
                }
                break;

            case 'exec':
                console.log('[SSE] exec case: this.onExec存在?', !!this.onExec);
                if (this.onExec) {
                    console.log('[SSE] 即将调用onExec');
                    this.onExec(update);
                    console.log('[SSE] onExec调用完成');
                } else {
                    console.error('[SSE] this.onExec不存在！');
                }
                break;

            case 'progress':
                console.log('[SSE] 处理progress消息:', update.message);
                // 兼容旧progress：同时走 exec/info 和 per-iter progress UI
                if (this.onExec) {
                    const execUpdate = {
                        iter: update.iter,
                        phase: 'info',
                        message: update.message,
                        status: update.status,
                        ts: update.ts
                    };
                    this.onExec(execUpdate);
                }
                if (this.onProgress) {
                    this.onProgress(update.message, update.status, update.iter);
                }
                break;

            case 'final':
                console.log('[SSE] 处理final消息');
                if (this.onFinal) {
                    this.onFinal(update.result);
                }
                break;

            case 'context_stats':
                console.log('[SSE] 处理context_stats消息:', update.stats);
                if (this.onContextStats) {
                    this.onContextStats(update.stats);
                }
                break;

            case 'compression_start':
                console.log('[SSE] 处理compression_start消息');
                if (this.onCompressionStart) {
                    this.onCompressionStart(update.message, update.stats);
                }
                break;

            case 'compression_done':
                console.log('[SSE] 处理compression_done消息');
                if (this.onCompressionDone) {
                    const oldStats = update.old_stats;
                    const newStats = update.new_stats;
                    this.onCompressionDone(update.message, oldStats, newStats);
                }
                break;

            case 'files_generated':
                console.log('[SSE] 处理files_generated消息:', update.files);
                if (this.onFilesGenerated) {
                    this.onFilesGenerated(update.files, update.iter);
                }
                // 注意：不再调用onExec，避免重复显示（onFilesGenerated中已调用appendFilesGenerated）
                break;

            case 'plan_update':
                console.log('[SSE] 处理plan_update消息');
                if (this.onPlanUpdate) {
                    this.onPlanUpdate(update.plan, update.summary);
                }
                break;

            default:
                console.warn('[SSE] 未知的更新类型:', update.type);
        }
    }

    /**
     * 关闭SSE连接
     */
    close() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
            console.log('[SSE] 连接已关闭');
        }
    }

    /**
     * 检查连接状态
     */
    isConnected() {
        return this.eventSource !== null && this.eventSource.readyState === EventSource.OPEN;
    }
}
