# Schema drift check (heuristic)

เทียบ key ที่โค้ดอ่าน กับ property ของ response schema
ฝั่ง 'สเปกไม่มี' เทียบกับ property ทุกชั้น (ตาม $ref) จึงไม่ฟ้อง key ที่ซ้อนลึก
ฝั่ง 'โค้ดไม่ได้ใช้' เทียบเฉพาะชั้นบนสุด ไม่งั้นจะยาวจนอ่านไม่ไหว
เทียบด้วยชื่อ key ล้วน ไม่ได้ดูว่าอยู่ถูกที่ - key ชื่อซ้ำข้ามชั้นจึงหลุดได้

## GET /series/{id}
- call site: `api/_client.py:159` ใน `fetch_series_detail._fetch()`
- อ่าน key จากขอบเขต `fetch_series_detail()`
- schema: SeriesModelV1
- โค้ดอ่าน 10 key · สเปกมี 27 property ชั้นบนสุด (91 รวมทุกชั้น)
- key ที่โค้ดอ่าน อยู่ในสเปกครบ
- สเปกมีแต่โค้ดไม่ได้ใช้: admin, authors, bayesian_rating, categories, category_recommendations, completed, description, forum_id, genres, last_updated, latest_chapter, licensed (+8)

## POST /series/search
- call site: `api/_client.py:220` ใน `search_series()`
- schema: ApiResponseV1, SeriesSearchResponseV1
- โค้ดอ่าน 7 key · สเปกมี 7 property ชั้นบนสุด (78 รวมทุกชั้น)
- key ที่โค้ดอ่าน อยู่ในสเปกครบ
- สเปกมีแต่โค้ดไม่ได้ใช้: context, page, per_page, reason, status

## POST /series/search
- call site: `api/_client.py:247` ใน `search_series()`
- schema: ApiResponseV1, SeriesSearchResponseV1
- โค้ดอ่าน 7 key · สเปกมี 7 property ชั้นบนสุด (78 รวมทุกชั้น)
- key ที่โค้ดอ่าน อยู่ในสเปกครบ
- สเปกมีแต่โค้ดไม่ได้ใช้: context, page, per_page, reason, status
