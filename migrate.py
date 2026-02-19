import json
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# 讀取 .env 密碼
load_dotenv()
MONGODB_URL = os.getenv("MONGODB_URL")

async def import_data():
    print("🚀 開始連線到 MongoDB...")
    client = AsyncIOMotorClient(MONGODB_URL)
    collection = client.vocab_database.cards

    # 打開你的備份檔
    print("📂 讀取 backup.json...")
    try:
        with open("backup.json", "r", encoding="utf-8") as file:
            data = json.load(file)
            
            if not data:
                print("⚠️ 備份檔是空的！")
                return
                
            # 一次把所有單字塞進資料庫 (這就是 NoSQL 的威力)
            print(f"⏳ 準備匯入 {len(data)} 筆單字...")
            await collection.insert_many(data)
            print("✅ 匯入大成功！請重新整理你的網頁看看！")
            
    except FileNotFoundError:
        print("❌ 找不到 backup.json，請確認檔案名稱與位置是否正確！")

# 執行非同步程式
asyncio.run(import_data())