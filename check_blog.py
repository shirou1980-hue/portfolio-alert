import os
import json
import time
from datetime import datetime, timezone, timedelta
import requests
import feedparser

# 감시할 네이버 블로그 아이디 목록
BLOG_IDS = [
    "changed_value",
    "startale-",
    "blissfulnara",
    "dodo2020_",
    "asuranet",
    "gaunyu",
    "gafield8785",
    "martin332",
    "usforall",
    "doctordk"
   "firelifestyle"
    "thingschange_"
    "hoki_investing_labs"
    "bigpicture-storage"
    "07leader"
    "highk27"
    "bambooinvesting"
    "rnjs1016k"
   "hwasikyuljeon"
   "opushk"
   "chacha36"
   "avarter"
   "ydygod2000"
   "iam_510"
   "kimsinvest"
  "cashcat_90"
  "hhhhnk"
  "noshortcut_life"
  "md21_vroom"
  "onion_asset"
  "limsk1212"
  "tosoha1"
  "kmsmir04"
  "cybermw"
  "shimseok12"
    "junsa26"
    "sungdory"
]

CACHE_FILE = "sent_posts.json"
REST_API_KEY = os.environ.get("KAKAO_REST_KEY") or os.environ.get("KAKAO_CLIENT_ID")
REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN")

def refresh_kakao_token():
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": REST_API_KEY,
        "refresh_token": REFRESH_TOKEN
    }
    resp = requests.post(url, data=data)
    result = resp.json()
    if "access_token" not in result:
        print(f"❌ 카카오 토큰 갱신 에러: {result}")
        return None
    return result.get("access_token")

def send_kakao_memo(access_token, title, link, author_name):
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # 텍스트 본문 자체에 URL을 넣어 터치/클릭 즉시 이동하도록 구성
    message_text = f"📢 [{author_name}] 새 글 등록\n\n📌 {title}\n\n🔗 바로가기:\n{link}"
    
    template_object = {
        "object_type": "text",
        "text": message_text,
        "link": {
            "web_url": link,
            "mobile_web_url": link
        },
        "button_title": "블로그로 이동"
    }
    
    data = {"template_object": json.dumps(template_object)}
    resp = requests.post(url, headers=headers, data=data)
    print(f"[{author_name}] 전송 상태: {resp.status_code}")

def is_recent(entry, hours=24):
    """최근 N시간 이내에 작성된 글인지 확인"""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        pub_time = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - pub_time) <= timedelta(hours=hours)
    return True  # 발행일 정보가 없는 특이 케이스는 통과

def main():
    if not REST_API_KEY or not REFRESH_TOKEN:
        print("❌ KAKAO_CLIENT_ID 또는 KAKAO_REFRESH_TOKEN 환경변수가 누락되었습니다.")
        return

    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            try:
                sent_posts = set(json.load(f))
            except Exception:
                sent_posts = set()
    else:
        sent_posts = set()

    new_posts = []

    for blog_id in BLOG_IDS:
        rss_url = f"https://rss.blog.naver.com/{blog_id}.xml"
        try:
            feed = feedparser.parse(rss_url)
        except Exception as e:
            print(f"[{blog_id}] RSS 파싱 에러: {e}")
            continue

        if not feed.entries:
            continue

        author_name = feed.feed.get("title", blog_id).replace(" : 네이버 블로그", "").strip()

        for entry in feed.entries[:3]:
            post_link = entry.link
            post_title = entry.title

            # 이미 보낸 글은 제외
            if post_link in sent_posts:
                continue

            # 최근 24시간 이내 글만 수집 (오래된 글 유입 방지)
            if not is_recent(entry, hours=24):
                sent_posts.add(post_link)
                continue

            new_posts.append((author_name, post_title, post_link))
            sent_posts.add(post_link)

    if new_posts:
        print(f"발송 대상 신규 글: {len(new_posts)}개")
        token = refresh_kakao_token()
        if not token:
            return

        for author_name, title, link in new_posts:
            send_kakao_memo(token, title, link, author_name)
            time.sleep(0.3)  # 카카오 API 호출 간격 조절

        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(sent_posts), f, ensure_ascii=False, indent=2)
    else:
        print("최근 24시간 이내에 새로 등록된 글이 없습니다.")
        # 신규 글이 없더라도 캐시 파일이 갱신되었다면 저장
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(sent_posts), f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
