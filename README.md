# Global News Radar MVP

這是一個用 GDELT 2.0 即時事件資料做的全球新聞事件地圖 MVP。

## 功能
- 抓取 GDELT 最新 15 分鐘事件檔
- 地圖標記全球事件
- 點擊地點看：誰、何時、何地、何事、來源 URL
- 用 Actor1 / Actor2 / Event / Location 建立簡易關係圖

## 安裝

```bash
pip install -r requirements.txt
```

## 執行

```bash
streamlit run app.py
```

## 下一步
1. 加入 GDELT GKG：抽人物、組織、地點、主題、情緒
2. 加入 LLM 摘要：把事件改寫成中文一句話
3. 加入 Neo4j / PostgreSQL：做長期事件資料庫
4. 加入事件去重與因果鏈：同一地點、同一角色、同一主題、時間接近就串起來
