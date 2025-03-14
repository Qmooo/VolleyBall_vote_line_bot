import schedule
import time
import threading
import logging
from datetime import datetime, timedelta

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scheduler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 全局變量，用於保存參考
line_bot_api = None
target_group_id = None
create_poll_func = None
end_poll_func = None
db = None

def initialize(line_api, group_id, create_func, end_func, db_instance):
    """
    初始化排程器
    參數:
        line_api: LINE Bot API 實例
        group_id: 目標群組ID
        create_func: 創建投票的函數
        end_func: 結束投票的函數
        db: 數據庫實例
    """
    global line_bot_api, target_group_id, create_poll_func, end_poll_func, db
    
    line_bot_api = line_api
    target_group_id = group_id
    create_poll_func = create_func
    end_poll_func = end_func
    db = db_instance
    
    logger.info("排程器已初始化")

def get_next_saturday():
    """
    獲取下一個週六的日期
    返回:
        datetime對象，表示下一個週六的日期
    """
    today = datetime.now()
    days_until_saturday = (5 - today.weekday()) % 7
    
    if days_until_saturday == 0:
        days_until_saturday = 7
    
    next_saturday = today + timedelta(days=days_until_saturday)
    next_saturday = next_saturday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    return next_saturday

def create_auto_poll():
    """自動創建週六出席調查投票"""
    try:
        next_saturday = get_next_saturday()
        poll_title = f"{next_saturday.strftime('%m/%d')} 週六活動出席調查"
        
        # 使用提供的創建投票函數
        _ , poll_id = create_poll_func(db, poll_title, target_group_id, line_bot_api)
        
        logger.info(f"已自動為群組 {target_group_id} 創建週六出席調查投票")
    except Exception as e:
        logger.error(f"自動創建投票時發生錯誤: {e}")

def end_auto_polls():
    """自動結束所有活動中的投票"""
    try:
        # 找出所有活動中的投票
        for poll_id in db.get_active_polls(target_group_id):
            try:
                # 使用提供的結束投票函數
                end_poll_func(None, poll_id, line_bot_api, db)
                logger.info(f"已自動結束投票: {poll_id}")
            except Exception as e:
                logger.error(f"自動結束投票 {poll_id} 時發生錯誤: {e}")
    except Exception as e:
        logger.error(f"執行自動結束投票任務時發生錯誤: {e}")

def clear_poll_db():
    """清空投票數據庫"""
    try:
        one_month_ago = datetime.now() - timedelta(days=30)
        for poll in db.get_closed_polls(target_group_id):
            if poll.get('timestamp') < one_month_ago:
                db.delete_poll(poll.get('poll_id'))
                logger.info(f"已刪除過期投票: {poll.get('poll_id')}")
    except Exception as e:
        logger.error(f"清空投票數據庫時發生錯誤: {e}")
    logger.info("已清空投票隊列")

def setup_scheduler():
    # """設定排程任務"""
    # # 設定每週六12:00自動開啟投票
    schedule.every().saturday.at("18:00").do(create_auto_poll)
    
    # # 設定每週五12:00自動結束投票   
    schedule.every().saturday.at("00:00").do(end_auto_polls)
    
    logger.info("已設定排程任務: 週六18:00自動創建投票，週六00:00自動結束投票")

def run_scheduler():
    """運行排程器"""
    while True:
        schedule.run_pending()
        time.sleep(60)  # 每分鐘檢查一次

def start_scheduler():
    """啟動排程器執行緒"""
    setup_scheduler()
    
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True  # 設為守護線程，主線程結束時會自動終止
    scheduler_thread.start()
    
    logger.info("排程器執行緒已啟動")
