import pymongo
import os
from datetime import datetime
import logging

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("mongodb.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# MongoDB連接設定
class Database:
    def __init__(self):
        # 從環境變量獲取MongoDB連接字串，或使用默認值
        self.mongo_uri = os.getenv('MONGODB_URI', 'mongodb://admin:password@140.113.110.77:27017/')
        self.db_name = os.getenv('MONGODB_DB', 'line_poll_db')
        self.client = None
        self.db = None
        
        # 集合名稱
        self.polls_collection = 'polls'
        self.members_collection = 'members'
        
        # 連接數據庫
        self.connect()
    
    def connect(self):
        """連接到MongoDB數據庫"""
        try:
            self.client = pymongo.MongoClient(self.mongo_uri)
            self.db = self.client[self.db_name]
            logger.info(f"成功連接到MongoDB: {self.db_name}")
            
            # 創建索引（如果尚未存在）
            self.db[self.polls_collection].create_index("poll_id", unique=True)
            self.db[self.members_collection].create_index([("group_id", 1), ("user_id", 1),("user_name",1)], unique=True)
            
        except Exception as e:
            logger.error(f"連接MongoDB時發生錯誤: {e}")
            raise
    
    def close(self):
        """關閉數據庫連接"""
        if self.client:
            self.client.close()
            logger.info("已關閉MongoDB連接")
    
    # ===== 投票相關操作 =====
    
    def save_poll(self, poll_data):
        """保存或更新投票數據
        參數:
            poll_data: 包含投票數據的字典，必須包含'poll_id'字段
        返回:
            操作結果
        """
        try:
            poll_id = poll_data.get('poll_id')
            if not poll_id:
                logger.error("保存投票時未提供poll_id")
                return False
            
            # 添加時間戳
            poll_data['updated_at'] = datetime.now()
            
            # 使用upsert模式，如果不存在則插入，存在則更新
            result = self.db[self.polls_collection].update_one(
                {"poll_id": poll_id},
                {"$set": poll_data},
                upsert=True
            )
            
            logger.info(f"保存投票成功: {poll_id}")
            return True
        except Exception as e:
            logger.error(f"保存投票時發生錯誤: {e}")
            return False
    
    def get_poll(self, poll_id):
        """獲取指定ID的投票數據
        參數:
            poll_id: 投票ID
        返回:
            投票數據字典，不存在則返回None
        """
        try:
            poll = self.db[self.polls_collection].find_one({"poll_id": poll_id})
            return poll
        except Exception as e:
            logger.error(f"獲取投票時發生錯誤: {e}")
            return None
    
    def get_active_polls(self, group_id=None):
        """獲取所有活動中的投票
        參數:
            group_id: 可選，群組ID
        返回:
            活動投票列表
        """
        try:
            query = {"status": "active"}
            if group_id:
                query["group_id"] = group_id
                
            polls = list(self.db[self.polls_collection].find(query))
            return polls
        except Exception as e:
            logger.error(f"獲取活動投票時發生錯誤: {e}")
            return []
    
    def get_closed_polls(self, group_id=None):
        """獲取所有已結束的投票
        參數:
            group_id: 可選，群組ID
        返回:
            已結束投票列表
        """
        try:
            query = {"status": "closed"}
            if group_id:
                query["group_id"] = group_id
                
            polls = list(self.db[self.polls_collection].find(query))
            return polls
        except Exception as e:
            logger.error(f"獲取已結束投票時發生錯誤: {e}")
            return []

    def delete_poll(self, poll_id):
        """刪除指定ID的投票
        參數:
            poll_id: 投票ID
        返回:
            操作結果
        """
        try:
            result = self.db[self.polls_collection].delete_one({"poll_id": poll_id})
            logger.info(f"刪除投票: {poll_id}, 刪除數量: {result.deleted_count}")
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"刪除投票時發生錯誤: {e}")
            return False
    
    def update_poll_status(self, poll_id, status):
        """更新投票狀態
        參數:
            poll_id: 投票ID
            status: 新狀態，如'active'、'closed'
        返回:
            操作結果
        """
        try:
            result = self.db[self.polls_collection].update_one(
                {"poll_id": poll_id},
                {"$set": {"status": status, "updated_at": datetime.now()}}
            )
            logger.info(f"更新投票狀態: {poll_id} -> {status}")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"更新投票狀態時發生錯誤: {e}")
            return False
    
    def add_vote(self, poll_id, user_id, option):
        """添加投票選擇
        參數:
            poll_id: 投票ID
            user_id: 用戶ID
            option: 選擇的選項
        返回:
            操作結果和先前的選擇（如果有）
        """
        try:
            # 獲取投票數據
            poll = self.get_poll(poll_id)
            if not poll:
                logger.error(f"添加投票選擇時找不到投票: {poll_id}")
                return False, None
            
            # 獲取用戶先前的選擇（如果有）
            voters = poll.get('voters', {})
            prev_option = voters.get(user_id)
            
            # 如果用戶之前有選擇，從該選項的列表中移除用戶
            if prev_option:
                # 從先前選項中移除用戶
                self.db[self.polls_collection].update_one(
                    {"poll_id": poll_id}, 
                    {"$pull": {f"options.{prev_option}": user_id}}
                )
                        
            # 添加用戶到新選項
            self.db[self.polls_collection].update_one(
                {"poll_id": poll_id}, 
                {"$addToSet": {f"options.{option}": user_id}}
            )

            # 更新用戶的選擇記錄
            self.db[self.polls_collection].update_one(
                {"poll_id": poll_id}, 
                {"$set": {f"voters.{user_id}": option, "updated_at": datetime.now()}}
            )
                  
            logger.info(f"添加投票選擇: {poll_id}, 用戶: {user_id}, 選項: {option}, 之前選項: {prev_option}")
            return True, prev_option
        except Exception as e:
            logger.error(f"添加投票選擇時發生錯誤: {e}")
            return False, None
    
    # ===== 成員相關操作 =====
    
    def save_member(self, group_id, user_id, name):
        """保存或更新成員信息
        參數:
            group_id: 群組ID
            user_id: 用戶ID
            name: 用戶名稱
        返回:
            操作結果
        """
        try:
            member_data = {
                "group_id": group_id,
                "user_id": user_id,
                "updated_at": datetime.now(),
                "name": name
            }
            
            result = self.db[self.members_collection].update_one(
                {"group_id": group_id, "user_id": user_id},
                {"$set": member_data},
                upsert=True
            )
            
            logger.info(f"保存成員信息: 群組 {group_id}, 用戶 {user_id}, 名稱 {name}")
            return True
        except Exception as e:
            logger.error(f"保存成員信息時發生錯誤: {e}")
            return False
    
    def get_group_members(self, group_id):
        """獲取群組所有成員
        參數:
            group_id: 群組ID
        返回:
            成員列表
        """
        try:
            members = list(self.db[self.members_collection].find({"group_id": group_id}))
            return members
        except Exception as e:
            logger.error(f"獲取群組成員時發生錯誤: {e}")
            return []