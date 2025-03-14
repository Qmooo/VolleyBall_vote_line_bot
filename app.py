import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    PostbackEvent,
)
from dotenv import load_dotenv
import logging
from poll import create_poll, end_poll, handle_postback
import volleyScheduler as scheduler
from db import Database

load_dotenv()
app = Flask(__name__)
# 初始化數據庫連接
db = Database()

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("line_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# 設定Line API密鑰
# 請替換為您的Channel Access Token和Channel Secret
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', None)

# 您需要獲取目標群組的ID
TARGET_GROUP_ID = os.getenv('GROUP_ID')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)



# 初始化排程器
def init_scheduler():
    """初始化排程器"""
    scheduler.initialize(
        line_bot_api,
        TARGET_GROUP_ID,
        create_poll,
        end_poll,
        db
    )
    scheduler.start_scheduler()
    logger.info("排程器已初始化並啟動")

@app.route("/callback", methods=['POST'])
def callback():
    """Line Bot Webhook回調處理"""
    # 獲取Line傳來的簽名與請求內容
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    # 記錄接收到的請求
    logger.info("Request body: " + body)

    try:
        # 驗證簽名並處理webhook事件
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("簽名驗證失敗")
        abort(400)
    
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """處理文字消息事件"""
    text = event.message.text
    user_id = event.source.user_id

    # 記錄用戶ID
    logger.info(f"收到用戶 {user_id} 的消息: {text}")
    
    # 檢查消息來源
    source_type = event.source.type
    group_id = TARGET_GROUP_ID  if source_type != 'group' else event.source.group_id

    # 記錄消息目標地點
    logger.info(f"消息傳入群組: {group_id}")

    # 處理指令
    if text.startswith('/'):
        command = text.split(' ')[0].lower()
        
        if command == '/poll':
            # 格式: /createpoll 投票標題
            if len(text.split(' ', 1)) > 1:
                title = text.split(' ', 1)[1]
                create_poll(db=db, title=title, group_id=group_id, line_bot_api=line_bot_api)
            else:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="請提供投票標題，格式：/poll 投票標題")
                )
        
        elif command == '/endpoll':
            # 格式: /endpoll 投票ID
            if len(text.split(' ', 1)) > 1:
                poll_id = text.split(' ', 1)[1]
                end_poll(event=event, poll_id=poll_id, line_bot_api=line_bot_api, db=db)
            else:
                # 如果沒有提供ID，嘗試找出最新的投票
                relevant_polls = []
                active_polls = db.get_active_polls()
                for poll in active_polls:
                    if poll.get('group_id') == group_id:
                        relevant_polls.append((poll.get('poll_id')))
                logger.info(f"找到的活動投票: {relevant_polls}")
                if relevant_polls:
                    # 按時間排序，選最新的結束
                    newest_poll = sorted(relevant_polls)
                    end_poll(event, newest_poll[0], line_bot_api, db)
                else:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text="沒有找到活動的投票。請提供投票ID，格式：/endpoll 投票ID")
                    )

        elif command == '/help':
            help_message = (
                "📋 投票系統使用說明：\n"
                "- /createpoll 標題 - 創建新投票\n"
                "- /endpoll 投票ID - 結束投票並顯示結果\n"
                "- /help - 顯示此幫助信息"
            )
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=help_message)
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="無效的指令。使用 /help 來獲取幫助信息")
            )
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="請使用 /help 來獲取幫助信息")
        )   
    
@handler.add(PostbackEvent)
def handle_postback_func(event):
   handle_postback(event=event,line_bot_api=line_bot_api,db=db)


if __name__ == "__main__":
    
    # 初始化並啟動排程器
    init_scheduler()

    # 設定服務器端口
    port = int(os.environ.get('PORT', 7988))
    
    # 啟動Flask服務器
    app.run(host='0.0.0.0', port=port)
