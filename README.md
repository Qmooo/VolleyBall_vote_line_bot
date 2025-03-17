# LINE投票系統

一個自動化的LINE群組投票系統，可用於追蹤活動出席情況，支持定時創建與結束投票，並將結果保存至MongoDB數據庫。

## 功能特點

- 自動創建周期性投票（每週六活動出席調查）
- 自動結束投票並展示美觀的結果統計
- 支持用戶更改投票選擇
- 漂亮的Flex Message介面
- MongoDB數據持久化存儲
- 支持本地部署或Docker容器化部署

## 系統架構

系統由以下主要組件組成：

- **app.py**: 主應用程序，處理LINE Webhook和用戶交互
- **poll.py**: 投票功能模組，包含創建投票、處理投票和結束投票的功能
- **scheduler.py**: 排程器模組，負責自動創建和結束投票
- **mongo_db.py**: 數據庫模組，處理與MongoDB的交互
- **docker-compose.yml**: Docker配置文件，用於容器化部署

## 安裝指南

### 前置需求

- Python 3.8+
- Docker和Docker Compose (僅Docker部署需要)
- LINE開發者帳號
- LINE官方帳號

### 選項1: 本地部署

1. 複製代碼庫
```bash
git clone <repository-url>
cd line-poll-bot
```

2. 創建虛擬環境（建議）
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate  # Windows
```

3. 安裝Python依賴
```bash
pip install -r requirements.txt
```

4. 安裝MongoDB
   - 請參考[MongoDB官方文檔](https://docs.mongodb.com/manual/installation/)安裝MongoDB
   - 啟動MongoDB服務

5. 創建並設置環境變量文件 (.env)
```
LINE_CHANNEL_ACCESS_TOKEN=你的頻道訪問令牌
LINE_CHANNEL_SECRET=你的頻道密鑰
GROUP_ID=目標群組ID
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB=line_poll_db
```

6. 啟動應用程序
```bash
python app.py
```

### 選項2: Docker部署

1. 複製代碼庫
```bash
git clone <repository-url>
cd line-poll-bot
```

2. 創建並設置環境變量文件 (.env)
```
LINE_CHANNEL_ACCESS_TOKEN=你的頻道訪問令牌
LINE_CHANNEL_SECRET=你的頻道密鑰
GROUP_ID=目標群組ID
MONGODB_URI=mongodb://admin:password@mongodb:27017/
MONGODB_DB=line_poll_db
```

3. 使用Docker Compose啟動所有服務
```bash
docker-compose up -d
```

這將一次性啟動MongoDB和LINE Bot應用程序，並會設置好所需的網絡連接。

## 使用指南

### 基本命令

- `/poll [標題]` - 創建新投票
- `/endpoll [投票ID]` - 結束指定投票，如果不指定ID則結束最新投票
- `/help` - 顯示幫助信息

### 投票參與

用戶可通過點擊投票訊息中的按鈕選擇"出席"或"請假"。用戶可以隨時更改自己的選擇。

## 排程設置

系統默認配置為自動執行以下任務：

- 每週六中午12:00自動創建出席調查投票
- 每週五中午12:00自動結束所有進行中的投票

可在`scheduler.py`文件中調整排程設置。

## 數據庫結構

系統使用MongoDB儲存以下數據：

### 集合：polls

存儲所有投票數據：
- poll_id: 投票ID
- title: 投票標題
- group_id: 群組ID
- created_at: 創建時間
- updated_at: 更新時間
- status: 狀態 ('active' 或 'closed')
- options: 選項及參與者 {option: [user_ids]}
- voters: 投票記錄 {user_id: selected_option}

### 集合：members

存儲群組成員信息：
- group_id: 群組ID
- user_id: 用戶ID
- name: 用戶名稱 (如果可獲取)
- updated_at: 更新時間

## Docker Compose配置

docker-compose.yml文件配置了兩個服務：

1. **mongodb**: MongoDB數據庫服務
   - 使用官方MongoDB鏡像
   - 持久化數據存儲
   - 設置管理員帳號密碼

2. **app**: LINE Bot應用服務
   - 使用Python環境
   - 依賴MongoDB服務
   - 自動重啟

可以單獨啟動MongoDB：
```bash
docker-compose up -d mongodb
```

也可以單獨啟動應用程序：
```bash
docker-compose up -d app
```

## 常見問題解決

**問題**: 排程器創建重複投票  
**解決方案**: 系統已實現防重複機制，每5分鐘內只會創建一次投票

**問題**: MongoDB連接失敗  
**解決方案**: 檢查MongoDB容器是否運行，確認連接字串中的用戶名和密碼是否正確

**問題**: LINE訊息無法發送  
**解決方案**: 確認LINE Channel Access Token是否有效，以及Bot是否有發送訊息的權限

## 後續開發計劃

- 添加更多投票類型和選項
- 實現定制化排程
- 添加用戶參與統計和報表
- 增強錯誤處理和通知機制

## 貢獻指南

歡迎提交問題報告和改進建議。如果您想貢獻代碼，請先fork此項目，然後提交pull request。
