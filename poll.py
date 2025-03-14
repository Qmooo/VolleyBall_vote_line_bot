import os
from linebot.models import (
    TextSendMessage, FlexSendMessage,
)
import json
from datetime import datetime
import logging

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("poll.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 投票選項和對應的表情符號
mapping = {"attend": "✅出席", "absent": "❌請假"}

# 創建投票功能
def create_poll(db, title, group_id, line_bot_api):
    """創建新投票\n
    參數:
        db: Database對象
        title: 投票標題
        group_id: 群組ID
        line_bot_api: LineBotApi對象
        active_polls: 活動投票數據
    """
    
    try:
        # 生成投票ID（使用時間戳）
        poll_id = f"{int(datetime.now().timestamp())}"
        
         # 初始化投票數據
        poll_data = {
            'poll_id': poll_id,
            'title': title,
            'group_id': group_id,
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'status': 'active',
            'options': {
                'attend': [],
                'absent': [],
            },
            'voters': {}
        }
        
        # 保存到MongoDB
        db.save_poll(poll_data)

        # 創建Flex Message
        bubble = {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "📊 投票",
                        "weight": "bold",
                        "size": "xl",
                        "color": "#ffffff"
                    }
                ],
                "backgroundColor": "#4A90E2",
                "paddingTop": "12px",
                "paddingBottom": "12px"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": title,
                        "weight": "bold",
                        "size": "lg",
                        "wrap": True,
                        "margin": "md"
                    },
                    {
                        "type": "text",
                        "text": "請選擇您的出席狀況:",
                        "size": "sm",
                        "color": "#888888",
                        "margin": "md",
                        "wrap": True
                    },
                    {
                        "type": "separator",
                        "margin": "lg"
                    }
                ],
                "spacing": "md",
                "paddingAll": "12px"
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "✅出席",
                            "data": f"vote_{poll_id}_attend",
                        },
                        "style": "primary",
                        "color": "#28a745",
                        "margin": "sm"
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "❌請假",
                            "data": f"vote_{poll_id}_absent",
                        },
                        "style": "primary",
                        "color": "#dc3545",
                        "margin": "sm"
                    }
                ],
                "spacing": "sm",
                "paddingAll": "12px"
            },
            "styles": {
                "footer": {
                    "separator": True
                }
            }
        }
        
        flex_message = FlexSendMessage(
            alt_text=f"投票: {title}",
            contents=bubble
        )

        # 發送投票訊息
        line_bot_api.push_message(
            os.getenv('DEV_USER_ID'),
            [
                TextSendMessage(text=f"📊 Created a new poll: {title}\n\nPoll ID: {poll_id}\n\nUse /endpoll to see results when ready.")
            ]
        )

        line_bot_api.push_message(
            group_id,
            flex_message
        )
        
        logger.info(f"創建了新投票: {poll_id}, 標題: {title}")
        return True, poll_id
    
    except Exception as e:
        logger.error(f"創建投票時發生錯誤: {e}")
        line_bot_api.push_message(
            os.getenv('DEV_USER_ID'),
            TextSendMessage(text=f"創建投票時發生錯誤: {str(e)}")
        )
        return False

# 觸發投票功能
def handle_postback(event, line_bot_api, db):
    """處理按鈕點擊事件\n
    參數:
        event: Line事件對象
        active_polls: 活動投票數據
        line_bot_api: LineBotApi對象
    """
    postback_data = event.postback.data
    user_id = event.source.user_id

    # 處理投票
    if postback_data.startswith('vote_'):
        parts = postback_data.split('_')
        if len(parts) >= 3:
            poll_id = parts[1]
            vote = parts[2]
            
            # 獲取投票數據
            poll = db.get_poll(poll_id)
            if not poll:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="找不到該投票")
                )
                return
            
            elif poll.get('status') != 'active':
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="投票已關閉")
                )
                return
            group_id = poll.get('group_id')

            # 保存成員信息
            try:
                user_profile = line_bot_api.get_profile(user_id)
                user_name = user_profile.display_name
                db.save_member(group_id, user_id, user_name)
            except Exception:
                user_name = f"User_{user_id[-4:]}"
                db.save_member(group_id, user_id)
            
            logger.info(f"用戶 {user_name} 投票: {poll_id}, 選項: {vote}")

            option = None
            if vote == 'attend':
                option = 'attend'
            elif vote == 'absent':
                option = 'absent'

            if option:
                # 添加投票選擇
                success, prev_option = db.add_vote(poll_id, user_id, option)
                
                if success:
                    # 回覆用戶
                    send_beautiful_vote_confirmation(user_id=user_id, poll_title=poll.get('title'), pre_option=prev_option, option=option, line_bot_api=line_bot_api)
                    logger.info(f"用戶 {user_name} 投票: {poll_id}, 選項: {option}")
                    return
            
            # 如果投票ID不存在
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="投票處理時發生錯誤，請重試")
            )

# 結束投票功能
def end_poll(event, poll_id, line_bot_api, db):
    """
    結束投票並顯示美觀的結果\n
    參數:
        event: Line事件對象
        poll_id: 投票ID
    """
    poll = db.get_poll(poll_id)
    if not poll:
        if event:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"找不到指定的投票ID: {poll_id}")
            )
        return False
    
    try:
        logger.info(f"{poll}")
        # 計算總票數和百分比
        options = poll.get('options', {})
        attend_count = len(options.get('attend', []))
        absent_count = len(options.get('absent', []))
        total_votes = len(poll.get('voters', {}))
        logger.info(f"結束投票: {poll_id}, 出席: {attend_count}, 缺席: {absent_count}, 總票數: {total_votes}")
        
        # 創建Flex Message顯示結果
        contents = []
        
        # 標題部分
        contents.append({
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "📊 投票結果",
                    "weight": "bold",
                    "size": "xl",
                    "color": "#ffffff"
                }
            ],
            "backgroundColor": "#4A90E2",
            "paddingAll": "15px"
        })
        
        # 投票標題
        contents.append({
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": poll['title'],
                    "weight": "bold",
                    "size": "lg",
                    "wrap": True
                },
                {
                    "type": "text",
                    "text": f"Total votes: {total_votes}",
                    "size": "sm",
                    "color": "#888888",
                    "margin": "md"
                },
                {
                    "type": "separator",
                    "margin": "lg"
                }
            ],
            "paddingAll": "15px"
        })

        # 每個選項的結果
        options_contents = []
        
        # 準時出席
        attend_percent = 0 if total_votes == 0 else (attend_count / total_votes) * 100
        options_contents.append({
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "✅出席",
                            "size": "md",
                            "flex": 5
                        },
                        {
                            "type": "text",
                            "text": f"{attend_count} ({attend_percent:.1f}%)",
                            "size": "md",
                            "align": "end",
                            "flex": 2
                        }
                    ]
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [],
                            "backgroundColor": "#28a745",
                            "height": "6px",
                            "width": f"{attend_percent}%"
                        }
                    ],
                    "backgroundColor": "#EEEEEE",
                    "height": "6px",
                    "margin": "sm"
                }
            ],
            "margin": "lg"
        })

        # 無法出席
        absent_percent = 0 if total_votes == 0 else (absent_count / total_votes) * 100
        options_contents.append({
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "❌請假",
                            "size": "md",
                            "flex": 5
                        },
                        {
                            "type": "text",
                            "text": f"{absent_count} ({absent_percent:.1f}%)",
                            "size": "md",
                            "align": "end",
                            "flex": 2
                        }
                    ]
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [],
                            "backgroundColor": "#dc3545",
                            "height": "6px",
                            "width": f"{absent_percent}%"
                        }
                    ],
                    "backgroundColor": "#EEEEEE",
                    "height": "6px",
                    "margin": "sm"
                }
            ],
            "margin": "lg"
        })
        
        # 添加選項結果
        contents.append({
            "type": "box",
            "layout": "vertical",
            "contents": options_contents,
            "paddingAll": "15px"
        })
        # 參與者列表
        participants_contents = []
        
        # 添加出席者列表
        if attend_count > 0:
            # 獲取參與者名稱
            attend_users = []
            for user_id in options.get('attend', []):
                try:
                    user_profile = line_bot_api.get_profile(user_id)
                    user_name = user_profile.display_name
                    attend_users.append(f'@{user_name}')
                except Exception:
                    user_name = f"User_{user_id[-4:]}"
            logger.info(f"出席者: {attend_users}")
            participants_contents.append({
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "✅出席",
                        "weight": "bold",
                        "size": "sm",
                        "color": "#28a745"
                    },
                    {
                        "type": "text",
                        "text": "\n".join(attend_users),
                        "size": "xs",
                        "wrap": True,
                        "margin": "sm",
                        "color": "#888888"
                    }
                ],
                "margin": "md"
            })
        
        # 添加缺席者列表
        if absent_count > 0:
            absent_users = []
            
            for user_id in options.get('absent', []):
                try:
                    user_profile = line_bot_api.get_profile(user_id)
                    user_name = user_profile.display_name
                    absent_users.append(f'@{user_name}')
                except Exception:
                    user_name = f"User_{user_id[-4:]}"
            logger.info(f"缺席者: {absent_users}")
            participants_contents.append({
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "❌請假",
                        "weight": "bold",
                        "size": "sm",
                        "color": "#dc3545"
                    },
                    {
                        "type": "text",
                        "text": "\n".join(absent_users),
                        "size": "xs",
                        "wrap": True,
                        "margin": "sm",
                        "color": "#888888"
                    }
                ],
                "margin": "md"
            })
        
        # 添加參與者列表到內容中
        if participants_contents:
            contents.append({
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    {
                        "type": "text",
                        "text": "Participants:",
                        "weight": "bold",
                        "margin": "lg"
                    },
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": participants_contents,
                        "margin": "md"
                    }
                ],
                "paddingAll": "15px"
            })
        
        # 計算出席率
        total_attendance = attend_count
        attendance_rate = 0 if total_votes == 0 else (total_attendance / total_votes) * 100
        
        # 添加出席率
        contents.append({
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "separator",
                    "margin": "sm"
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "出席率:",
                            "size": "md",
                            "weight": "bold",
                            "flex": 4
                        },
                        {
                            "type": "text",
                            "text": f"{attendance_rate:.1f}%",
                            "size": "md",
                            "weight": "bold",
                            "color": "#4A90E2",
                            "align": "end",
                            "flex": 2
                        }
                    ],
                    "margin": "lg"
                }
            ],
            "paddingAll": "15px"
        })
        
        # 建立Flex訊息
        flex_message = FlexSendMessage(
            alt_text=f"Poll Results: {poll['title']}",
            contents={
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": contents
                }
            }
        )

        # 發送結果
        group_id = poll['group_id']
        line_bot_api.push_message(group_id, flex_message)
        
        # 更新投票狀態為已關閉
        db.update_poll_status(poll_id, 'closed')
        
        logger.info(f"結束投票: {poll_id}")
        return True
    except Exception as e:
        logger.error(f"結束投票時發生錯誤: {e}")
        if event:
            line_bot_api.push_message(
                os.getenv('DEV_USER_ID'),
                TextSendMessage(text=f"結束投票時發生錯誤: {str(e)}")
            )     
        return False  

def send_beautiful_vote_confirmation(user_id, poll_title, pre_option, option, line_bot_api):
    """
    發送增強版的投票確認訊息，處理三種情況：
    1. 重複投票 (prev_option == option)
    2. 更改投票 (prev_option != option 且 prev_option 不為 None)
    3. 新投票 (prev_option 為 None)
    參數:
        user_id: 用戶ID
        poll_title: 投票標題
        pre_option: 之前的選項
        option: 用戶選擇的選項
        line_bot_api: LINE Bot API對象
    """
    # 根據選項設定顏色
    color = "#28a745"  # 綠色 (出席)
    if "absent" in option.lower():
        color = "#dc3545"  # 紅色 (請假)
    
    pre_text = None
    # 確定訊息類型和內容
    if pre_option is None:
        # 新投票
        header_text = "投票已確認"
        body_text = "感謝您的參與!"
        status_text = "您的選擇:"
    elif pre_option == option:
        # 重複投票
        header_text = "重複投票"
        body_text = "您已經選擇過相同選項"
        status_text = "您的選擇維持不變:"
    else:
        # 更改投票
        header_text = "投票已更新"
        body_text = "您的選擇已更新"
        status_text = "您的新選擇:"

        # 獲取之前選項的顏色
        pre_color = "#28a745"  # 綠色 (出席)
        if "absent" in pre_option.lower():
            pre_color = "#dc3545"  # 紅色 (請假)
        
        pre_text = {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": "之前選擇:",
                    "size": "sm",
                    "color": "#aaaaaa"
                },
                {
                    "type": "text",
                    "text": f"{mapping[pre_option]}",
                    "size": "sm",
                    "color": pre_color,
                    "align": "end"
                }
            ],
            "margin": "sm"
        }

    # 創建Flex Message
    bubble = {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": header_text,
                    "color": "#ffffff",
                    "weight": "bold"
                }
            ],
            "backgroundColor": color,
            "paddingAll": "12px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": poll_title,
                    "weight": "bold",
                    "wrap": True,
                    "size": "sm"
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": status_text,
                            "size": "sm",
                            "color": "#aaaaaa"
                        },
                        {
                            "type": "text",
                            "text": f"{mapping[option]}",
                            "size": "sm",
                            "color": color,
                            "align": "end",
                            "weight": "bold"
                        }
                    ],
                    "margin": "md"
                },
            ],
            "paddingAll": "16px"
        },
        "styles": {
            "body": {
                "separator": True
            }
        }
    }
    if pre_text:
        bubble["body"]["contents"].insert(1,pre_text)
                                      
    # 添加底部說明文字
    bubble["body"]["contents"].append({
        "type": "box",
        "layout": "vertical",
        "contents": [
            {
                "type": "text",
                "text": body_text,
                "size": "xs",
                "color": "#aaaaaa",
                "align": "center",
                "margin": "md"
            }
        ]
    })
    
    # 發送訊息
    try:
        flex_message = FlexSendMessage(
            alt_text="投票確認",
            contents=bubble
        )
        line_bot_api.push_message(user_id, flex_message)
        return True
    except Exception as e:
        logger.error(f"發送美化投票確認訊息時發生錯誤: {e}")
        # 如果失敗，嘗試發送普通文本
        try:
            if pre_option is None:
                # 新投票
                message = f"您在: {poll_title}中\n選擇了: {mapping[option]}"
            elif pre_option == option:
                # 重複投票
                message = f"您在: {poll_title}中\n已經選擇過: {mapping[option]}"
            else:
                # 更改投票
                message = f"您在: {poll_title}中\n將選擇從 {mapping[pre_option]} 更改為 {mapping[option]}"
            
            line_bot_api.push_message(user_id, TextSendMessage(text=message))
        except:
            pass
        return False
    
    except Exception as e:
        logger.error(f"獲取群組成員時發生錯誤: {e}")
        return []