import os
import json
import requests
import feedparser

# 감시할 블로그 아이디
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
    "doctordk",
   "firelifestyle",
    "thingschange_",
    "hoki_investing_labs",
    "bigpicture-storage",
    "07leader",
    "highk27",
    "bambooinvesting",
    "rnjs1016k",
   "hwasikyuljeon",
   "opushk",
   "chacha36",
   "avarter",
   "ydygod2000",
   "iam_510",
   "kimsinvest",
  "cashcat_90",
  "hhhhnk",
  "noshortcut_life",
  "md21_vroom",
  "onion_asset",
  "limsk1212",
  "tosoha1",
  "kmsmir04",
  "cybermw",
  "shimseok12",
    "junsa26",
    "sungdory"
]

CACHE_FILE = "sent_posts.json"

# 저장소에 등록된 키를 찾음 (KAKAO_REST_KEY 또는 KAKAO_CLIENT_ID)
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
    
    # 실패 시 상세 원인 콘솔 출력
    if "access_token" not in result:
        print(f"❌ 카카오 응답 상세 에러: {result}")
        return None
        
    return result.get("access_token")

def send_kakao_memo(access_token, title, link, author):
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    template_object = {
        "object_type": "text",
        "text": f"📢 [{author}] 새 블로그 글\n\n{title}",
        "link": {
            "web_url": link,
            "mobile_web_url": link
        },
        "button_title": "글 보러가기"
    }
    
    data = {"template_object": json.dumps(template_object)}
    resp = requests.post(url, headers=headers, data=data)
    print(f"[{author}] 카카오 전송 상태코드: {resp.status_code}")

def main():
    if not REST_API_KEY or not REFRESH_TOKEN:
        print("❌ KAKAO_REST_KEY 또는 KAKAO_REFRESH_TOKEN 환경변수가 없습니다. GitHub Secrets를 확인하세요.")
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
        feed = feedparser.parse(rss_url)

        if not feed.entries:
            continue

        for entry in feed.entries[:3]:
            post_link = entry.link
            post_title = entry.title

            if post_link not in sent_posts:
                new_posts.append((blog_id, post_title, post_link))
                sent_posts.add(post_link)

    if new_posts:
        print(f"새로운 글 발견: {len(new_posts)}개")
        token = refresh_kakao_token()
        if not token:
            print("토큰 갱신 실패로 전송을 중단합니다.")
            return

        for blog_id, title, link in new_posts:
            send_kakao_memo(token, title, link, blog_id)

        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(sent_posts), f, ensure_ascii=False, indent=2)
    else:
        print("새로 등록된 글이 없습니다.")

if __name__ == "__main__":
    main()
