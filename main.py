from fastapi import FastAPI
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware # 新增這行
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from pydantic import BaseModel, Field
from typing import List, Optional
import os
from dotenv import load_dotenv

import json
from google import genai
from google.genai import types

# 1. 讀取 .env 檔案中的隱藏密碼
load_dotenv()

app = FastAPI()

# --- 新增 CORS 設定 ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允許所有來源 (測試階段先全開)
    allow_credentials=True,
    allow_methods=["*"],  # 允許所有方法 (GET, POST, PUT, DELETE)
    allow_headers=["*"],  # 允許所有標頭
)
# ----------------------

# 2. 建立 MongoDB 連線
MONGODB_URL = os.getenv("MONGODB_URL")
client = AsyncIOMotorClient(MONGODB_URL)
db = client.vocab_database      # 我們把資料庫命名為 vocab_database
collection = db.cards           # 我們把資料表(集合)命名為 cards

# --- 新增：設定 Gemini AI 客戶端 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
# ---------------------------------

# --- 升級：定義「單一解釋」的格式 ---
class Definition(BaseModel):
    pos: str
    meaning: str  # 這欄現在當作「簡短翻譯」
    explanation: Optional[str] = ""  # ✨ 新增：詳細解釋與適當場合
    sentence: Optional[str] = ""

# --- 升級：定義「整張單字卡」的完整格式 ---
class WordCard(BaseModel):
    
    word: str
    ipa: Optional[str] = ""
    definitions: List[Definition] # 這是一個陣列 (List)
    dateAdded: str
    level: int = 0
    nextReview: int
# --------------------------------------

@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI 伺服器與資料庫已準備就緒！"}

# --- 新增：取得所有單字的 API ---
@app.get("/api/words")
async def get_words():
    words_list = []
    
    # 找尋資料庫裡的所有單字
    cursor = collection.find({})
    async for document in cursor:
        # 統一將 MongoDB 的 _id 轉成字串，並命名為 id 傳給前端
        document["id"] = str(document["_id"]) 
        del document["_id"]
        # 清除可能殘留的舊 id 欄位
        if "id" in document and type(document["id"]) == int:
            del document["id"]
        words_list.append(document)
    return words_list
        
    return words_list
# --------------------------------

@app.get("/api/fetch_word/{word}")
async def fetch_word_info(word: str):
    # 給 AI 的超級指令：融合權威字典風格與生活化實用例句
    prompt = f"""
    你是一個精通多國語言的專業英文老師。
    請綜合參考「牛津字典 (Oxford)」、「劍橋字典 (Cambridge)」的權威定義，以及「Yahoo 奇摩字典」的繁體中文翻譯習慣，
    查閱單字 "{word}"，並嚴格回傳以下 JSON 格式的資料。
    
    注意：
    1. 例句請務必提供「最貼近日常生活、實用且道地」的用法，不要使用過於艱澀的學術句子。
    2. explanation 欄位請務必「簡明扼要」，嚴格限制在 1 到 2 句話 (約 30 字) 以內。

    必須嚴格遵守以下 JSON 格式，不要回傳任何額外的 Markdown 標記 (如 ```json) 或說明文字：
    {{
        "word": "{word}",
        "ipa": "音標，例如 [kəmˈpjuː.tɚ]",
        "definitions": [
            {{
                "pos": "詞性縮寫，例如 n., v., adj., adv., phr.",
                "meaning": "精準且簡短的繁體中文翻譯 (例如：演算法、部署)",
                "explanation": "用 1~2 句話簡短說明這個字詞的「核心概念」與「適用場合」，請勿長篇大論",
                "sentence": "生活化、實用且道地的英文例句"
            }}
        ]
    }}
    """
    
    try:
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", 
            )
        )
        
        ai_data = json.loads(response.text)
        return ai_data
        
    except Exception as e:
        print(f"AI API 錯誤: {e}")
        raise HTTPException(status_code=500, detail="AI 查詢失敗，請稍後再試或檢查單字拼寫。")
    
# 4. 寫一支 POST API，讓前端可以把單字存進資料庫
@app.post("/api/words")
async def create_word(card: WordCard):
    word_dict = card.dict()
    # 寫入資料庫時，MongoDB 會自動產生 _id
    result = await collection.insert_one(word_dict)
    # 回傳這把自動產生的鑰匙給前端
    return {"message": "單字新增成功！", "id": str(result.inserted_id)}

# --- 1. 修改單字 (Update) ---
@app.put("/api/words/{word_id}")
async def update_word(word_id: str, card: WordCard):
    update_data = card.dict()
    # 統一使用 ObjectId 來尋找資料
    result = await collection.update_one(
        {"_id": ObjectId(word_id)}, 
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="找不到這張單字卡")
    return {"message": "單字修改成功！"}

@app.delete("/api/words/{word_id}")
async def delete_word(word_id: str):
    # 統一使用 ObjectId 來刪除資料
    result = await collection.delete_one({"_id": ObjectId(word_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="找不到這張單字卡")
    return {"message": "單字刪除成功！"}