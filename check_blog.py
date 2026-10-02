import os
import json
import requests
import feedparser

# 감시할 네이버 블로그 아이디 목록 (원하는 아이디로 변경)
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
REST_API_KEY = os.environ.get("KAKAO_REST_KEY")
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
    return result.get("access_token")

def send_kakao_memo(access_token, title, link, author):
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    template_object = {
        "object_type": "text",
        "text": f"📢 [{author}] 새 블로그 글 등록\n\n{title}",
        "link": {
            "web_url": link,
            "mobile_web_url": link
        },
        "button_title": "글 보러가기"
    }
    
    data = {"template_object": json.dumps(template_object)}
    resp = requests.post(url, headers=headers, data=data)
    print(f"[{author}] 카카오톡 전송 결과: {resp.status_code}")

def main():
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

        # 최신 글 3개 대조
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
            print("카카오 토큰 갱신 실패! REFRESH_TOKEN 값을 점검하세요.")
            return

        for blog_id, title, link in new_posts:
            send_kakao_memo(token, title, link, blog_id)

        # 발송 완료된 링크 저장
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(sent_posts), f, ensure_ascii=False, indent=2)
    else:
        print("새로 등록된 글이 없습니다.")

if __name__ == "__main__":
    main()
