from flask import Flask, request, Response, send_from_directory
import anthropic
import json
import time
import threading

app = Flask(__name__, static_folder='public')
MODEL = 'claude-haiku-4-5-20251001'

# ── Session usage tracking ────────────────────────────
SESSION = {'calls': 0, 'input_tokens': 0, 'output_tokens': 0}
S_LOCK  = threading.Lock()

def track(inp: int, out: int):
    with S_LOCK:
        SESSION['calls']         += 1
        SESSION['input_tokens']  += inp
        SESSION['output_tokens'] += out

def sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/api/usage')
def usage():
    with S_LOCK:
        return dict(SESSION)

@app.route('/api/usage/reset', methods=['POST'])
def usage_reset():
    with S_LOCK:
        SESSION['calls'] = SESSION['input_tokens'] = SESSION['output_tokens'] = 0
    return {'ok': True}

# ── Tool Use ──────────────────────────────────────────
TOOLS = [
    {
        'name': 'read_file',
        'description': '讀取一個檔案的內容（模擬環境）',
        'input_schema': {
            'type': 'object',
            'properties': {
                'reason': {'type': 'string', 'description': '用一句繁體中文說明為什麼要讀這個檔案'},
                'path': {'type': 'string', 'description': '檔案路徑'}
            },
            'required': ['reason', 'path']
        }
    },
    {
        'name': 'bash',
        'description': '執行一個 bash 指令（模擬環境）',
        'input_schema': {
            'type': 'object',
            'properties': {
                'reason': {'type': 'string', 'description': '用一句繁體中文說明這個指令在做什麼'},
                'command': {'type': 'string', 'description': '要執行的指令'}
            },
            'required': ['reason', 'command']
        }
    },
    {
        'name': 'search_code',
        'description': '在程式碼中搜尋關鍵字（模擬環境）',
        'input_schema': {
            'type': 'object',
            'properties': {
                'reason': {'type': 'string', 'description': '用一句繁體中文說明為什麼要搜尋這個'},
                'pattern': {'type': 'string', 'description': '要搜尋的關鍵字'},
                'path': {'type': 'string', 'description': '搜尋目錄'}
            },
            'required': ['reason', 'pattern']
        }
    },
    {
        'name': 'web_fetch',
        'description': '從網路抓取網頁內容（模擬環境）',
        'input_schema': {
            'type': 'object',
            'properties': {
                'reason': {'type': 'string', 'description': '用一句繁體中文說明要抓取什麼資訊'},
                'url': {'type': 'string', 'description': '網頁 URL'}
            },
            'required': ['reason', 'url']
        }
    }
]

MOCK = {
    'read_file': lambda i: f"# {i.get('path','file')}\ndef calculate_total(items):\n    total = 0\n    for item in itmss:  # bug: 'itmss' should be 'items'\n        total += item.price\n    return total",
    'bash': lambda i: f"$ {i.get('command','')}\nmain.py:4: NameError: name 'itmss' is not defined\n（提示：'itmss' 是 'items' 的拼錯）",
    'search_code': lambda i: f"搜尋 \"{i.get('pattern','')}\" 結果：\nmain.py:4 → for item in itmss:\n  ↑ 'itmss' 應改為 'items'",
    'web_fetch': lambda i: f"[{i.get('url','')}]\n標題：相關技術文章\n內容節錄：這是關於所查詢主題的模擬文章，包含重要的技術細節..."
}

TOOL_ICONS = {'read_file': '📖', 'bash': '💻', 'search_code': '🔍', 'web_fetch': '🌐'}

@app.route('/api/toolflow', methods=['POST'])
def toolflow():
    api_key = request.headers.get('x-api-key', '')
    task    = request.json.get('task', '')

    def generate():
        if not api_key:
            yield sse({'type': 'error', 'message': '請先設定 API Key'})
            return

        client = anthropic.Anthropic(api_key=api_key)

        yield sse({'type': 'node', 'icon': '💬', 'title': '接收輸入', 'desc': task, 'tool': None})
        time.sleep(0.2)
        yield sse({'type': 'node_done'})

        messages  = [{'role': 'user', 'content': task}]
        total_in  = 0
        total_out = 0

        try:
            for turn in range(8):
                resp = client.messages.create(
                    model=MODEL,
                    max_tokens=4096,
                    tools=TOOLS,
                    system='你是一個 AI 助手，在模擬環境中使用工具完成任務。每次只呼叫一個工具。工具結果是模擬資料，請依此做出合理回應。完成後請用繁體中文給出總結。',
                    messages=messages
                )
                total_in  += getattr(getattr(resp, 'usage', None), 'input_tokens',  0) or 0
                total_out += getattr(getattr(resp, 'usage', None), 'output_tokens', 0) or 0

                if turn == 0:
                    yield sse({'type': 'node', 'icon': '🧠', 'title': '理解意圖', 'desc': '分析任務，規劃執行步驟...', 'tool': None})
                    time.sleep(0.5)
                    yield sse({'type': 'node_done'})

                content_dicts = []
                for b in resp.content:
                    if b.type == 'text':
                        content_dicts.append({'type': 'text', 'text': b.text})
                    elif b.type == 'tool_use':
                        content_dicts.append({'type': 'tool_use', 'id': b.id, 'name': b.name, 'input': dict(b.input)})
                messages.append({'role': 'assistant', 'content': content_dicts})

                if resp.stop_reason == 'end_turn':
                    text_blocks = [b for b in resp.content if b.type == 'text']
                    txt     = text_blocks[0].text if text_blocks else '完成'
                    summary = txt[:80] + '...' if len(txt) > 80 else txt
                    yield sse({'type': 'node', 'icon': '✅', 'title': '生成最終回答', 'desc': summary, 'tool': None})
                    time.sleep(0.3)
                    yield sse({'type': 'node_done'})
                    break

                elif resp.stop_reason == 'tool_use':
                    tool_results = []
                    for tu in [b for b in resp.content if b.type == 'tool_use']:
                        reason   = tu.input.get('reason', '')
                        tech     = {k: v for k, v in tu.input.items() if k != 'reason'}
                        tech_str = ', '.join(f'{v}' for v in tech.values())[:50]
                        yield sse({
                            'type': 'node',
                            'icon': TOOL_ICONS.get(tu.name, '🔧'),
                            'title': reason or f'呼叫 {tu.name}',
                            'desc': tech_str,
                            'tool': tu.name
                        })
                        time.sleep(0.9)
                        result = MOCK[tu.name](tu.input) if tu.name in MOCK else '執行完成'
                        yield sse({'type': 'node_done'})
                        yield sse({'type': 'tool_result', 'name': tu.name, 'result': result})
                        tool_results.append({'type': 'tool_result', 'tool_use_id': tu.id, 'content': result})
                    messages.append({'role': 'user', 'content': tool_results})

                else:
                    text_blocks = [b for b in resp.content if b.type == 'text']
                    txt     = text_blocks[0].text if text_blocks else '（已截斷）'
                    summary = txt[:80] + '...' if len(txt) > 80 else txt
                    yield sse({'type': 'node', 'icon': '✅', 'title': '生成最終回答', 'desc': summary, 'tool': None})
                    time.sleep(0.3)
                    yield sse({'type': 'node_done'})
                    break

            yield sse({'type': 'done'})
            track(total_in, total_out)

        except Exception as e:
            yield sse({'type': 'error', 'message': str(e)})

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

# ── Explain ───────────────────────────────────────────
@app.route('/api/explain', methods=['POST'])
def explain():
    api_key = request.headers.get('x-api-key', '')
    label   = request.json.get('label', '')
    detail  = request.json.get('detail', '')
    if not api_key:
        return {'explanation': '需要設定 API Key 才能查詢說明'}
    client = anthropic.Anthropic(api_key=api_key)
    try:
        tool_name = request.json.get('toolName', '')
        tool_hint = f'（使用工具：{tool_name}）' if tool_name else ''
        resp = client.messages.create(
            model=MODEL,
            max_tokens=200,
            messages=[{'role': 'user', 'content':
                f'把以下指令拆解說明，每行格式：代碼部分：繁體中文解釋（8字內）\n\n'
                f'工具：{tool_hint or label}\n'
                f'指令：{detail}\n\n'
                f'規則：\n'
                f'- 每行只寫「代碼片段：口語解釋」，不要其他文字\n'
                f'- 代碼片段照原文抄，解釋用最簡單的口語\n'
                f'- 最多6行，跳過不重要的符號\n'
                f'- 不要標題、序號、•符號、markdown'}]
        )
        inp = getattr(getattr(resp, 'usage', None), 'input_tokens',  0) or 0
        out = getattr(getattr(resp, 'usage', None), 'output_tokens', 0) or 0
        track(inp, out)
        return {'explanation': resp.content[0].text}
    except Exception as e:
        return {'explanation': f'查詢失敗：{str(e)}'}

if __name__ == '__main__':
    print('\n  ✅  伺服器已啟動（Haiku 模型）')
    print('  🌐  http://localhost:3456\n')
    app.run(port=3456, debug=False, threaded=True)
