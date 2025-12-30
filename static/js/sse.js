/**
 * SSE (Server-Sent Events) 处理模块
 * 完全透明的流式通信，零黑盒
 */

class SSEClient {
    constructor() {
        this.abortController = null;
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
     * 发送消息并建立SSE连接（使用fetch stream）
     * @param {string} message - 用户消息
     * @param {string} model - 模型名称
     * @param {string} conversationId - 对话ID
     * @param {string} clientMsgId - 客户端消息ID
     * @param {string} interruptedResponse - 被中断的assistant回复（可选）
     */
    async send(message, model = 'gpt-5', conversationId, clientMsgId, interruptedResponse = null) {
        // 关闭之前的连接
        this.close();

        // 创建AbortController用于中断
        this.abortController = new AbortController();

        // 构造请求body
        const body = {
            message: message,
            model: model,
            conversation_id: conversationId
        };
        if (clientMsgId) {
            body.client_msg_id = clientMsgId;
        }
        if (interruptedResponse) {
            body.interrupted_response = interruptedResponse;
        }

        try {
            console.log('[SSE] 发送请求:', body);

            // 使用fetch发送POST请求
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(body),
                signal: this.abortController.signal
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            // 读取stream
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const {done, value} = await reader.read();

                if (done) {
                    console.log('[SSE] 流式传输完成');
                    if (this.onDone) {
                        this.onDone();
                    }
                    break;
                }

                // 解码并追加到buffer
                buffer += decoder.decode(value, {stream: true});

                // 处理buffer中的完整消息
                const lines = buffer.split('\n');
                buffer = lines.pop(); // 保留不完整的行

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6); // 移除"data: "前缀

                        // 检查结束标记
                        if (data === '[DONE]') {
                            console.log('[SSE] 收到结束标记');
                            continue;
                        }

                        // 解析JSON
                        try {
                            const update = JSON.parse(data);
                            console.log('[SSE] 收到更新:', update.type);
                            this.dispatch(update);
                        } catch (err) {
                            console.error('[SSE] 解析消息失败:', err, data);
                        }
                    }
                }
            }

        } catch (err) {
            if (err.name === 'AbortError') {
                console.log('[SSE] 连接已中断');
            } else {
                console.error('[SSE] 连接错误:', err);
                if (this.onError) {
                    this.onError({
                        message: err.message || 'SSE连接失败',
                        error: err
                    });
                }
            }
        } finally {
            this.abortController = null;
        }
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
        if (this.abortController) {
            this.abortController.abort();
            this.abortController = null;
            console.log('[SSE] 连接已关闭');
        }
    }

    /**
     * 检查连接状态
     */
    isConnected() {
        return this.abortController !== null;
    }
}
