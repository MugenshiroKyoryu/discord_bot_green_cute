# Schema drift check (heuristic)

เทียบ key ที่โค้ดอ่าน กับ property ระดับบนสุดของ response schema
ตรวจเฉพาะชั้นบนสุด - key ที่ซ้อนลึกกว่านั้นจะขึ้นเป็น 'ไม่พบ' ได้แม้จะถูกต้อง

## GET /series/{id}
- call site: `api/_client.py:58` ใน `fetch_series_detail._fetch()`
- อ่าน key จากขอบเขต `fetch_series_detail()`
- schema: SeriesModelV1
- โค้ดอ่าน 10 key · สเปกมี 27 property ชั้นบนสุด
- **โค้ดอ่านแต่สเปกไม่มี (ชั้นบนสุด): end, original, start**
- สเปกมีแต่โค้ดไม่ได้ใช้: admin, authors, bayesian_rating, categories, category_recommendations, completed, description, forum_id, genres, last_updated, latest_chapter, licensed (+8)

## POST /series/search
- call site: `api/_client.py:102` ใน `search_series()`
- schema: ApiResponseV1, SeriesSearchResponseV1
- โค้ดอ่าน 4 key · สเปกมี 7 property ชั้นบนสุด
- **โค้ดอ่านแต่สเปกไม่มี (ชั้นบนสุด): record, series_id, type**
- สเปกมีแต่โค้ดไม่ได้ใช้: context, page, per_page, reason, status, total_hits

## POST /series/search
- call site: `api/_client.py:119` ใน `search_series()`
- schema: ApiResponseV1, SeriesSearchResponseV1
- โค้ดอ่าน 4 key · สเปกมี 7 property ชั้นบนสุด
- **โค้ดอ่านแต่สเปกไม่มี (ชั้นบนสุด): record, series_id, type**
- สเปกมีแต่โค้ดไม่ได้ใช้: context, page, per_page, reason, status, total_hits
