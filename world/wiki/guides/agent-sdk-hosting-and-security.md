# Agent SDK Hosting and Secure Deployment

別名：生產環境託管與安全部署、容器化部署、沙箱隔離、憑證代理、多租戶隔離、Hosting、Secure Deployment、Docker、gVisor、Firecracker
框架：agent-sdk

## 摘要
Claude Agent SDK 在執行時會產生並監督一個擁有專屬 Shell、工作目錄與本機 JSONL 對話紀錄檔的 `claude` CLI 子行程（透過 stdio 通訊），因此託管 Agent SDK 與託管無狀態 API 封裝層截然不同。本指南涵蓋自託管（Self-hosting）的系統資源需求、四種工作階段容器生命週期模式（Ephemeral、Long-Running、Hybrid、Multi-agent Container）、多租戶隔離設定，以及防禦提示詞注入（Prompt Injection）的縱深防禦架構（包含 `sandbox-runtime`、Docker 安全參數、gVisor、Firecracker microVM 與外部 Proxy 憑證注入模式）。

## 重點

### 子行程模型與本機狀態（`hosting.md`）
- **一對一子行程模型**：每次呼叫 `query()` 會啟動一個獨立的 `claude` CLI 子行程並透過 stdio 通訊；執行 N 個並行工作階段即代表 N 個子行程（各自擁有獨立行程樹與 Transcript 檔案）。預設皆繼承應用程式的工作目錄；若需隔離檔案系統，應在每個 `query()` 的 `options` 傳入不同的 `cwd`（例如 `cwd: "/work/session-a"`）。（若不想自管代理人迴圈，可改用 Anthropic 託管的 Managed Agents。）
- **容器本機磁碟上的三類預設狀態（容器重啟、縮容或遷移節點時皆會遺失）**：
  1. **Session transcripts（工作階段對話紀錄）**：預設位於 `~/.claude/projects/`（若設定 `CLAUDE_CONFIG_DIR` 則位於其下的 `projects/`）。跨主機持久化需設定 `SessionStore` adapter（注意：`SessionStore` 僅鏡像 Transcript，不鏡像 `CLAUDE.md` 或工作目錄產物；且當批次寫入 Store 失敗時會發出 `{ type: "system", subtype: "mirror_error" }` 並繼續執行）。
  2. **`CLAUDE.md` 記憶檔**：使用者層級位於 `~/.claude/CLAUDE.md`，專案層級位於工作階段的工作目錄。需透過掛載共用磁碟區（Volume）或物件儲存同步來持久化。
  3. **工作目錄產物（Working-directory artifacts）**：位於工作階段的 `cwd`。

### 系統需求、資源配置與水平擴展
- **執行階段依賴（Runtime dependencies）**：
  - Python SDK 需 **Python 3.10+**；TypeScript SDK 需 **Node.js 18.14+**。
  - 兩個 SDK 在大多數安裝環境下皆已內建（Bundle）對應平台的原生 Claude Code 二進位檔，被啟動的 CLI 子行程不需要額外安裝 Node.js。內建二進位檔版本綁定於 SDK 套件版本（遵循 semver）。
- **硬體資源基準與容量計算**：
  - 單一剛啟動的代理人實例建議起點為：**1 GiB RAM、5 GiB 磁碟空間、1 CPU**（容器基礎設施成本約每小時 \$0.05，遠低於單次長工作階段可能消耗數美元的 Token 成本）。
  - 記憶體消耗會隨工作階段長度與工具活動增長（1 GiB 為下限而非上限），主機並行容量公式：
    `agents per host = (host RAM - overhead) / (per-session RAM ceiling)`（需在預期工具負載下執行代表性工作階段長度的壓測以量測 Peak RSS）。
  - 水平擴展路由：對於長時執行（Long-running）模式，應在負載平衡器後方運行容器池，並對 `sessionId` 使用一致性雜湊（Consistent hashing）將同一工作階段固定路由（Pin）至同一台容器與同一個運行中的子行程。
- **網路需求**：
  - 對外（Outbound）：需 HTTPS 連線至 `api.anthropic.com`（或 Amazon Bedrock / Google Cloud Agent Platform 的區域端點），以及所使用的 MCP 伺服器與外部工具端點。
  - 對內（Inbound）：在容器上暴露 HTTP 或 WebSocket 連接埠由應用程式處理請求並在內部呼叫 SDK；`claude` 子行程本身不會監聽網路。

### 四種工作階段容器模式（Session Patterns）
1. **Ephemeral sessions（短暫型容器）**：
   - 每個使用者任務建立一個新容器，任務完成即銷毀（適合 Bug 調查修復、發票/收據擷取、文件翻譯、媒體轉換等單次任務；極需秒級以下的冷啟動速度與按秒計費）。
   - 容器執行單次入口腳本（如從 `TASK_PROMPT` 環境變數讀取任務並設 `maxTurns: 20` / `max_turns=20`）。
2. **Long-running sessions（長時執行型容器）**：
   - 維持持久化容器實例（通常單一容器內承載多個 SDK 行程），服務持續性工作（如郵件分類回覆代理人、透過容器連接埠託管可編輯網站的 Site builder、Slack 高流量聊天機器人）。
   - **保持連線與預熱（Pre-warming）API 差異**：
     - TypeScript：使用 `streamInput()` 向活動中工作階段追加回合；在流量進入前呼叫 `startup()` 預熱子行程，若直到第一個請求抵達前還不知道工作階段的 `cwd`，則改呼叫 `prewarm()`。
     - Python：使用 `ClaudeSDKClient` 跨回合保持工作階段開啟。
3. **Hybrid sessions（混合型容器）**：
   - 短暫型容器在啟動時從外部 `SessionStore` 載入（Hydrate）歷史狀態並將更新寫回，閒置時關閉容器，使用者回來時重新啟動（適合間歇性互動的個人專案管理、長達數小時暫停與恢復的深度研究、載入歷史工單的客服代理人）。此模式**必須**配置 `SessionStore`（`resume: sessionId, sessionStore` / `resume=session_id, session_store=session_store`）。
4. **Multi-agent container（多代理人共用容器）**：
   - 在單一容器內執行多個密切協作的 SDK 子行程（如多代理人模擬）。必須為每個代理人配置獨立 `cwd` 與設定隔離。

### 多租戶隔離（Multi-tenant Isolation）與已知部署限制
- **在共用容器內隔離多租戶的五項必要設定**：
  1. 傳入 `settingSources: []`（TypeScript）或 `setting_sources=[]`（Python）以跳過讀取使用者、專案與本地設定檔。
  2. 在 `env` 設定 `"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"`：因為位於 `~/.claude/projects/<project>/memory/` 的自動記憶（Auto memory）**不受 `settingSources` 控制**，預設會無條件載入系統提示詞！
  3. 在 `env` 將 `CLAUDE_CONFIG_DIR` 指向租戶專屬目錄，避免共用全域 `~/.claude.json`（若每個設定目錄僅服務單一工作目錄且未使用 `SessionStore`，還可在 `env` 設定 `CLAUDE_CODE_PROJECT_DIR_NAME` 縮短 Transcript 路徑，需 TypeScript SDK `v0.3.234+` 或 Python SDK `v0.2.140+`）。
  4. 每次 `query()` 明確傳入租戶專屬的 `cwd`。
  5. 在外部 Proxy 實施每租戶專屬的對外規則（獨立對外 IP、憑證或網域白名單）。
- **已知部署限制與應對方式**：
  - **無頂層工作階段逾時（No top-level session timeout）**：工作階段不會自動逾時，必須設定 `maxTurns` / `max_turns` 限制回合數。
  - **長時間工作階段記憶體增長**：限制工作階段長度或定期回收子行程。
  - **大量平行子代理人扇出（Fanout）可能觸發速率限制（Rate limits）**：應拆分為較小批次分派。
  - **無單一子代理人掛鐘截止時間（No per-subagent wall-clock deadline）**：在 `AgentDefinition` 中以 `maxTurns` 限制子代理人；環境變數 `CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS` 僅設定子代理人停止產出輸出時的卡死看門狗（Stall watchdog），並非總執行時間上限。

### 安全部署與縱深防禦（`secure-deployment.md`）
- **內建安全機制**：
  - **Permissions system**：權限規則與受管設定（Managed settings）。
  - **關鍵路徑刪除保護（Critical-path removals）**：當 `permissionMode` 為 `default` 時，被辨識為刪除工作目錄或其他關鍵路徑的 `rm` / `rmdir` 指令必定要求核准，**即使有匹配的 allow 規則也不會跳過核准**（此為權限閘門而非沙箱）。
  - **網頁搜尋摘要（Web search summarization）**：搜尋結果會先經過摘要而非直接將原始網頁內容放入 Context，降低惡意網頁 Prompt Injection 風險。
  - **Sandbox mode**：限制 Bash 指令的檔案系統與網路存取。

### 四種隔離技術對比（Isolation Technologies）
1. **Sandbox runtime（`sandbox-runtime`，隔離強度：Good、效能開銷：極低、複雜度：低）**
   - 無需 Docker 容器，直接在作業系統層級強制檔案與網路限制（以 JSON 設定網域與路徑白名單）：
     - **檔案系統**：Linux 使用 `bubblewrap`，macOS 使用 `sandbox-exec`。
     - **網路**：在獨立網路命名空間（Linux）或 Seatbelt profile（macOS）中執行指令，將流量導向內建 Proxy 檢查網域白名單（跳過 Proxy 的外部連線直接失敗）。
   - **安全考量**：(1) 共用宿主機 Kernel；(2) 預設無 TLS 解密檢查（僅依用戶端提供的 hostname 過濾，可能受 Domain fronting 繞過；高威脅模型應改用 TLS-terminating proxy）；(3) 需確保白名單網域的憑證無法被濫用於跳板外洩。
2. **Containers（Docker，隔離強度：視設定而定、效能開銷：低、複雜度：中）**
   - **強化版 `docker run` 關鍵參數**：
     - `--cap-drop ALL`：移除所有 Linux capabilities（如 `NET_ADMIN`、`SYS_ADMIN`）防止提權。
     - `--security-opt no-new-privileges`：防止透過 setuid 二進位檔提權。
     - `--security-opt seccomp=/path/to/seccomp-profile.json`：限制可用系統呼叫（Docker 預設封鎖約 44 個 syscall）。
     - `--read-only`：將容器根檔案系統設為唯讀不可變。
     - `--tmpfs /tmp:rw,noexec,nosuid,size=100m` 與 `--tmpfs /home/agent:rw,noexec,nosuid,size=500m`：提供僅存於記憶體、停止即清除的可寫入暫存空間（亦可搭配 Overlay filesystem 先審核再寫入底層檔案）。
     - `--network none`：完全切斷外部網路連線，改透過 `-v /var/run/proxy.sock:/var/run/proxy.sock:ro` 掛載宿主機 Proxy 的 Unix socket（在容器內將 `localhost` 連接埠轉發至該 socket）。
     - `--memory 2g`、`--cpus 2`、`--pids-limit 600`（防止 fork bomb）、`--user 1000:1000`（非 root 執行）。
     - `-v /path/to/code:/workspace:ro`：唯讀掛載程式碼。
     - 進階選項：`--userns-remap`（映射容器 root 至宿主機非特權使用者）、`--ipc private`（隔離 IPC）。
   - **唯讀掛載仍須排除的敏感檔案清單**：`.env` / `.env.local`、`~/.git-credentials`、`~/.aws/credentials`、`~/.config/gcloud/application_default_credentials.json`、`~/.azure/`、`~/.docker/config.json`、`~/.kube/config`、`.npmrc` / `.pypirc`、`*-service-account.json`、`*.pem` / `*.key`。
3. **gVisor（`runsc` runtime，隔離強度：極佳、效能開銷：中至高、複雜度：中）**
   - 在使用者空間（Userspace）攔截並實作系統呼叫相容層，大幅縮小對宿主機真實 Kernel 的攻擊面（於 `/etc/docker/daemon.json` 註冊 `/usr/local/bin/runsc` 並以 `docker run --runtime=runsc agent-image` 啟動）。
   - **效能開銷數據**：CPU 密集運算約 `~0%`（無 syscall 攔截）；簡單 syscall 約慢 `~2×`；高頻率開啟/關閉檔案的密集 File I/O 最高可慢達 `10-200×`。
4. **Virtual machines（Firecracker / QEMU，隔離強度：極佳、效能開銷：高、複雜度：中至高）**
   - 透過 CPU 虛擬化延伸提供硬體級獨立 Kernel 隔離。**Firecracker** microVM 可在 **125ms 內啟動**且記憶體開銷**低於 5 MiB**；VM 不配置外部網卡，所有流量皆透過 `vsock`（Virtual sockets）送往宿主機 Proxy 進行白名單過濾與憑證注入。

### 憑證管理與外部 Proxy 模式（Credential Management）
- **核心原則**：將憑證保存在代理人安全邊界之外，由外部 Proxy 對發出的請求注入憑證、強制網域白名單並記錄稽核日誌，讓代理人永遠看不到真實金鑰。
- **設定 Claude Code 走 Proxy 的兩種環境變數**：
  1. `ANTHROPIC_BASE_URL="http://localhost:8080"`：僅將 Claude API 抽樣請求以明文 HTTP 送往 Proxy（Proxy 可直接檢視修改並注入 API Key 後轉發至真實 API）。
  2. `HTTP_PROXY="http://localhost:8080"` 與 `HTTPS_PROXY="http://localhost:8080"`：將所有系統 HTTP/HTTPS 流量導向 Proxy（對 HTTPS 會建立加密 CONNECT 通道，若無 TLS 攔截則無法檢視內容或注入憑證）。
- **常見 Proxy 工具**：**Envoy Proxy**（具 `credential_injector` filter）、**mitmproxy**（TLS-terminating proxy）、**Squid**（具 ACL 的快取 Proxy）、**LiteLLM**（具憑證注入與速率限制的 LLM Gateway）。
- **存取其他外部服務（Git、資料庫、內部 API）的兩種憑證隔離架構**：
  1. **Custom tools / MCP Server**：代理人呼叫 MCP 工具，由工具將請求轉發給安全邊界外的宿主機服務（如 Git proxy）加上驗證後再連線遠端，無需 TLS 解密攔截。
  2. **Traffic forwarding（TLS-terminating Proxy）**：在容器外運行解密並重新加密 HTTPS 的 Proxy，將 Proxy 的 CA 憑證安裝至代理人容器的信任儲存區（Trust store），並設定 `HTTP_PROXY` / `HTTPS_PROXY`。
     - 注意：並非所有程式都遵守 `HTTP_PROXY` / `HTTPS_PROXY`（例如 Node.js `fetch()` 預設忽略這些變數，在 **Node 24+** 可設定 `NODE_USE_ENV_PROXY=1` 啟用支援）。對於忽略環境變數的工具，可使用 `proxychains` 攔截網路呼叫，或用 `iptables` 將對外流量重導向至透明代理（Transparent proxy，如透明模式下的 Squid 或 mitmproxy）。

## 相關頁面
- [[concepts/agent-sdk-sessions]]
- [[concepts/agent-sdk-permissions]]
- [[guides/agent-sdk-observability-and-troubleshooting]]
- [[guides/agent-sdk-cost-and-todo-tracking]]
- [[versions/agent-sdk-migration-and-v2-preview]]

## 出處
- docs/agent-sdk/hosting.md
- docs/agent-sdk/secure-deployment.md
