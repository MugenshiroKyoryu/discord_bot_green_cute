import asyncio
import time

import aiohttp

from api._ranking import rank, rerank_details

SEARCH_URL = "https://api.mangaupdates.com/v1/series/search"
SERIES_URL = "https://api.mangaupdates.com/v1/series"

_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "GreenCuteBot"
}

# กันคำสั่งแขวนถ้า API ค้าง
_TIMEOUT = aiohttp.ClientTimeout(total=15)

# จำกัดจำนวน request รายละเอียดที่ยิงพร้อมกัน เพื่อลดโอกาสโดน rate limit
_MAX_CONCURRENT = 5
_MAX_RETRIES = 3

# status ที่เป็นปัญหาชั่วคราว ลองใหม่ได้
_RETRY_STATUSES = {429, 500, 502, 503, 504}

# ขอผลมาเยอะแล้วค่อยจัดอันดับใหม่เอง จากนั้นดึงรายละเอียดเฉพาะตัวที่จะโชว์จริง
# recall เท่าเดิมแต่ยิง detail น้อยลงจาก 25 เหลือ 10 (สเปกจำกัด perpage 1-100)
_SEARCH_PERPAGE = 25
_MAX_RESULTS = 10

# ตาม SeriesSearchRequestV1.search - ยิงไปก็ได้แค่ 400 กลับมา
_SEARCH_MIN_LEN = 1
_SEARCH_MAX_LEN = 400

# AUP ของ MangaUpdates ขอให้ทำ cache และรายละเอียดเรื่องแทบไม่เปลี่ยนรายวัน
_DETAIL_TTL = 900
_DETAIL_CACHE_MAX = 256

# relation_type ที่แปลว่า "เรื่องเดียวกันคนละสื่อ" ตาม enum ของ SeriesModelV1.related_series
# ไม่เอา Sequel / Prequel / Spin-Off เพราะเป็นคนละเรื่องที่ผู้ใช้ไม่ได้ค้นหา
_RELATED_RELATIONS = {"Adapted From", "Alternate Version", "Main Story"}

# ตามสายจากผลอันดับ 1 เท่านั้น และจำกัดจำนวน กันยิง detail เพิ่มจนโดน rate limit
_MAX_RELATED = 3

# series_id -> (เวลาที่เก็บ, ข้อมูล)
_detail_cache: dict[int, tuple[float, dict]] = {}


def _cache_get(series_id: int) -> dict | None:
    entry = _detail_cache.get(series_id)
    if entry is None:
        return None

    stored_at, data = entry
    if time.monotonic() - stored_at > _DETAIL_TTL:
        _detail_cache.pop(series_id, None)
        return None

    # คืน copy เพราะผู้เรียกเติม total_hits / relation ลงไปทีหลัง
    return dict(data)


def _cache_put(series_id: int, data: dict) -> None:
    if len(_detail_cache) >= _DETAIL_CACHE_MAX:
        oldest = min(_detail_cache, key=lambda key: _detail_cache[key][0])
        _detail_cache.pop(oldest, None)

    _detail_cache[series_id] = (time.monotonic(), dict(data))


def _clean_query(name: str) -> str:
    """ตัดคำค้นที่สเปกไม่รับตั้งแต่ต้นทาง จะได้ไม่เสีย request ไปกับ 400"""
    query = (name or "").strip()

    if len(query) < _SEARCH_MIN_LEN:
        raise Exception("กรุณาระบุชื่อเรื่องที่ต้องการค้นหา")

    if len(query) > _SEARCH_MAX_LEN:
        raise Exception(f"ชื่อเรื่องยาวเกินไป (ไม่เกิน {_SEARCH_MAX_LEN} ตัวอักษร)")

    return query


def _format_context(context: dict) -> list[str]:
    """แปลง context ของ ApiResponseV1 เป็นข้อความสั้น ๆ ต่อฟิลด์"""
    messages = []

    for field, value in context.items():
        if isinstance(value, str):
            messages.append(f"{field}: {value}")
            continue

        # รูปแบบ ApiValidationErrorsV1 คือ list ของ {index, errors[]}
        if isinstance(value, list):
            for entry in value:
                errors = entry.get("errors") if isinstance(entry, dict) else None
                if isinstance(errors, list) and errors:
                    messages.append(f"{field}: {errors[0]}")

    return messages


async def _error_detail(resp) -> str:
    """ดึง reason/context ตาม ApiResponseV1 ออกมา ดีกว่าโชว์แค่ตัวเลข status"""
    try:
        body = await resp.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        return str(resp.status)

    if not isinstance(body, dict):
        return str(resp.status)

    reason = body.get("reason")
    if not reason:
        return str(resp.status)

    context = body.get("context")
    messages = _format_context(context) if isinstance(context, dict) else []

    if messages:
        return f"{resp.status} {reason} ({'; '.join(messages[:3])})"

    return f"{resp.status} {reason}"


async def _request_json(session, method, url, *, json_payload=None, error_label="API"):

    for attempt in range(_MAX_RETRIES):

        try:
            async with session.request(method, url, json=json_payload) as resp:

                if resp.status in _RETRY_STATUSES and attempt < _MAX_RETRIES - 1:
                    retry_after = resp.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 2 ** attempt
                    await asyncio.sleep(min(delay, 5))
                    continue

                if resp.status != 200:
                    raise Exception(f"{error_label} error : {await _error_detail(resp)}")

                return await resp.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            # ปัญหา network/timeout ชั่วคราว ลองใหม่ก่อนค่อยยอมแพ้
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            raise Exception(f"{error_label} error : {e}") from e

    raise Exception(f"{error_label} error : 429")


async def fetch_series_detail(
    session: aiohttp.ClientSession,
    series_id: int,
    semaphore: asyncio.Semaphore | None = None
) -> dict:

    cached = _cache_get(series_id)
    if cached is not None:
        return cached

    async def _fetch():
        return await _request_json(
            session, "get", f"{SERIES_URL}/{series_id}", error_label="Series API"
        )

    if semaphore is None:
        series = await _fetch()
    else:
        async with semaphore:
            series = await _fetch()

    associated_names = [
        a["title"] for a in series.get("associated", []) if "title" in a
    ]

    anime_data = series.get("anime") or {}

    image = series.get("image") or {}
    image_url = (image.get("url") or {}).get("original")

    # เก็บไว้ตามสายไปหาเรื่องเดียวกันคนละสื่อ ผลค้นหา (SeriesModelSearchV1) ไม่มีฟิลด์นี้
    related = [
        {
            "id": r.get("related_series_id"),
            "relation": r.get("relation_type"),
            "name": r.get("related_series_name")
        }
        for r in (series.get("related_series") or [])
        if r.get("related_series_id")
    ]

    # ใช้ or แทน default ของ .get เพราะ API อาจส่ง null มาทั้งที่มี key
    detail = {
        # ติดไว้เพื่อรู้ว่าเรื่องไหนถูกดึงมาแล้วบ้าง หลังจัดอันดับรอบสองสลับลำดับไป
        "series_id": series_id,
        "title": series.get("title") or "Unknown",
        "url": series.get("url"),
        "status": series.get("status") or "Unknown",
        "type": series.get("type") or "Unknown",
        "associated_names": associated_names,
        "anime": {
            "start": anime_data.get("start") or "Unknown",
            "end": anime_data.get("end") or "Unknown"
        },
        "image": image_url,
        "related": related
    }

    _cache_put(series_id, detail)
    return detail


def _related_to_fetch(
    detail: dict,
    seen_ids: set[int],
    limit: int = _MAX_RELATED
) -> list[tuple[int, str]]:
    """เลือกเรื่องที่เกี่ยวข้องซึ่งควรตามไปดึงต่อ - คืน (series_id, relation_type)

    ไม่แตะเน็ตและไม่แก้ seen_ids ที่รับมา จึงเทสได้ตรง ๆ
    """
    picked: list[tuple[int, str]] = []
    taken = set(seen_ids)

    for entry in detail.get("related") or []:

        if len(picked) >= limit:
            break

        series_id = entry.get("id")
        relation = entry.get("relation")

        if series_id is None or series_id in taken:
            continue

        if relation not in _RELATED_RELATIONS:
            continue

        taken.add(series_id)
        picked.append((series_id, relation))

    return picked


async def _fetch_related(
    session: aiohttp.ClientSession,
    detail: dict,
    seen_ids: set[int],
    allowed_types: set[str],
    semaphore: asyncio.Semaphore
) -> list[dict]:
    """ตามสายความสัมพันธ์ของผลอันดับ 1 ไปเอาเรื่องเดียวกันคนละสื่อ

    ค้นด้วยชื่อเต็มของฉบับมังงะแล้วฉบับนิยายที่ใช้ชื่อสั้นกว่าอาจคะแนนไม่ถึงเกณฑ์
    แต่ MangaUpdates ผูกความสัมพันธ์ไว้ให้แล้ว ตามไปดึงตรง ๆ จึงแน่นอนกว่าเทียบชื่อ
    """
    picked = _related_to_fetch(detail, seen_ids)

    if not picked:
        return []

    outcomes = await asyncio.gather(
        *[fetch_series_detail(session, sid, semaphore) for sid, _ in picked],
        return_exceptions=True
    )

    extra = []
    for (_, relation), outcome in zip(picked, outcomes):

        if isinstance(outcome, BaseException):
            continue

        # ผลค้นหาไม่บอก type ของเรื่องที่เกี่ยวข้อง ต้องดึงมาก่อนถึงกรองได้
        if outcome.get("type") not in allowed_types:
            continue

        outcome["relation"] = relation
        extra.append(outcome)

    return extra


async def search_series(
    name: str,
    allowed_types: set[str],
    no_results_msg: str,
    no_match_msg: str,
    options: dict | None = None
) -> list[dict]:

    query = _clean_query(name)

    payload = {
        "search": query,
        # กรองประเภทตั้งแต่ฝั่ง server จะได้ไม่ยิง detail ของประเภทที่ไม่เอา
        "type": sorted(allowed_types),
        # ระบุให้ชัดว่าค้นจากชื่อ ไม่ใช่เนื้อเรื่อง (ตอนนี้ API default เป็น title อยู่แล้ว)
        "stype": "title",
        "perpage": _SEARCH_PERPAGE
    }

    if options:
        payload.update(options)

    async with aiohttp.ClientSession(headers=_HEADERS, timeout=_TIMEOUT) as session:

        data = await _request_json(
            session, "post", SEARCH_URL,
            json_payload=payload,
            error_label="Search API"
        )

        results = data.get("results") or []
        total_hits = data.get("total_hits")

        # กรองซ้ำฝั่ง client กันกรณี server filter ส่งประเภทอื่นปนมา
        typed = [
            item for item in results
            if (item.get("record") or {}).get("type") in allowed_types
        ]

        # API คืนทุกเรื่องที่มีคำค้นอยู่ในชื่อ ต้องจัดอันดับเองถึงจะได้ตัวที่ใช่ขึ้นก่อน
        ranked = rank(query, typed, limit=_MAX_RESULTS)

        wanted = [(item.get("record") or {}).get("series_id") for item in ranked]
        wanted = [sid for sid in wanted if sid is not None]

        if not wanted:
            # ค้นแบบไม่กรองประเภทอีกครั้ง เพื่อแยกว่าไม่พบเลย หรือเจอแต่ประเภทอื่น
            plain_payload = {k: v for k, v in payload.items() if k != "type"}
            plain = await _request_json(
                session, "post", SEARCH_URL,
                json_payload=plain_payload, error_label="Search API"
            )

            if not (plain.get("results") or []):
                raise Exception(no_results_msg)

            raise Exception(no_match_msg)

        semaphore = asyncio.Semaphore(_MAX_CONCURRENT)

        outcomes = await asyncio.gather(
            *[fetch_series_detail(session, sid, semaphore) for sid in wanted],
            return_exceptions=True
        )

        # ข้ามเรื่องที่ดึงรายละเอียดไม่สำเร็จ แสดงเท่าที่ได้
        details = [
            outcome for outcome in outcomes
            if not isinstance(outcome, BaseException)
        ]

        if not details:
            raise next(e for e in outcomes if isinstance(e, BaseException))

        # จัดอันดับรอบสอง - รอบแรกเห็นแค่ชื่อหลัก แต่รายละเอียดมีชื่อรองครบแล้ว
        # เช่น 'akame ga kill' รอบแรกทุกเรื่องตกเกณฑ์จนร่วงไปใช้ลำดับดิบของ API
        # ภาคก่อนหน้าเลยมาก่อนภาคหลัก รอบสองเทียบกับ 'Akame ga KILL!' จึงได้ตัวที่ใช่
        # ต้องทำก่อน _fetch_related เพราะมันตามสายจาก details[0]
        details = rerank_details(query, details)

        for item in details:
            item["total_hits"] = total_hits

        # เรื่องที่รอบสองตัดทิ้งไม่นับว่า 'เห็นแล้ว' - ถ้ามันเป็นเรื่องเดียวกันคนละสื่อ
        # ของอันดับ 1 ก็ควรได้กลับเข้ามาพร้อมป้ายบอกความสัมพันธ์ (ดึงจาก cache ไม่เสีย request)
        seen_ids = {
            item["series_id"] for item in details if item.get("series_id") is not None
        }

        # เติมเรื่องเดียวกันคนละสื่อที่คะแนนชื่อไม่พาขึ้นมาเอง เช่นค้นชื่อเต็มของ
        # ฉบับมังงะแล้วฉบับนิยายใช้ชื่อสั้นกว่า จะได้ไม่ตกหล่นไปทั้งที่ MU ผูกไว้ให้แล้ว
        extra = await _fetch_related(
            session,
            details[0],
            seen_ids,
            allowed_types,
            semaphore
        )

        for item in extra:
            item["total_hits"] = total_hits

        details.extend(extra)

        return details
