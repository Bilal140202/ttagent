"""100% synthetic fixtures — no real IDs, no real accounts, no network.

Repo rule (inherited from the sibling projects): tests never contain real
handles, real video ids of live posts, or real CDN URLs.  Everything here
is fabricated to mirror the *shape* of the public surfaces as documented
in docs/endpoint-matrix.md.
"""

FAKE_ID = "7299999999999999999"   # 19 digits, synthetic
FAKE_HANDLE = "synthetic_creator"

CDN_HOST = "v16-fake.tiktokcdn.com"
MIRROR_HOST = "www.tikwm-fake.com"
CDN_MP4 = f"https://{CDN_HOST}/video/tos/synthetic-video.mp4"
CDN_HD = f"https://{CDN_HOST}/video/tos/synthetic-hd.mp4"
CDN_WM = f"https://{CDN_HOST}/video/tos/synthetic-wm.mp4"
CDN_JPEG = f"https://{CDN_HOST}/img/synthetic-cover.jpeg"
CDN_MUSIC = f"https://{CDN_HOST}/music/synthetic-sound.mp3"
OUTSIDE_URL = "https://evil.example.com/video.mp4"
HTTP_URL = "http://v16-fake.tiktokcdn.com/a.mp4"

JPEG_HEAD = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 16
MP4_HEAD = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 16
MP3_HEAD = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 16
HTML_HEAD = b"<!DOCTYPE html><html><body>not media</body></html>"


def tikwm_payload(code=0, msg="success", data=None):
    """tikwm-shaped API envelope."""
    if data is None:
        data = {
            "id": FAKE_ID,
            "region": "US",
            "title": "synthetic title #fyp",
            "cover": f"https://{MIRROR_HOST}/cover/syn.jpg",
            "origin_cover": f"https://{MIRROR_HOST}/ocover/syn.jpg",
            "duration": 12,
            "play": f"/video/media/play/syn.mp4",          # relative path
            "hdplay": CDN_HD,
            "wmplay": CDN_WM,
            "size": 1000000,
            "hd_size": 2000000,
            "music": CDN_MUSIC,
            "music_info": {"id": "7111111111111111111",
                           "title": "original sound - synthetic",
                           "play": CDN_MUSIC, "author": "synthetic",
                           "original": True, "duration": 12},
            "play_count": 1000, "digg_count": 100,
            "comment_count": 10, "share_count": 5,
            "download_count": 2, "collect_count": 7,
            "create_time": 1700000000,
            "author": {"id": "5222222222222222222",
                       "unique_id": FAKE_HANDLE,
                       "nickname": "Synthetic Creator",
                       "avatar": f"https://{MIRROR_HOST}/ava/syn.jpg"},
        }
    return {"code": code, "msg": msg, "processed_time": 0.1, "data": data}


def tikwm_error_payload(msg="Url parsing is failed! Please check url."):
    return {"code": -1, "msg": msg, "processed_time": 0.1, "data": None}


UNIVERSAL_BLOB = {
    "__DEFAULT_SCOPE__": {
        "webapp.video-detail": {
            "itemInfo": {
                "itemStruct": {
                    "id": FAKE_ID,
                    "desc": "synthetic embed title",
                    "createTime": "1700000001",
                    "video": {"playAddr": CDN_MP4, "downloadAddr": CDN_WM,
                              "cover": CDN_JPEG, "originCover": CDN_JPEG,
                              "duration": 12, "width": 1080, "height": 1920},
                    "music": {"id": "7111111111111111111",
                              "title": "synthetic sound",
                              "playUrl": CDN_MUSIC,
                              "authorName": "synthetic", "duration": 12},
                    "author": {"id": "5222222222222222222",
                               "uniqueId": FAKE_HANDLE,
                               "nickname": "Synthetic Creator",
                               "avatarLarger": CDN_JPEG},
                    "stats": {"playCount": "900", "diggCount": "90",
                              "commentCount": "9", "shareCount": "4",
                              "collectCount": "6"},
                }
            }
        }
    }
}


def embed_html_universal() -> str:
    import json
    return ("<!DOCTYPE html><html><head><title>TikTok</title></head><body>"
            '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
            + json.dumps(UNIVERSAL_BLOB) + "</script></body></html>")


def embed_html_shell() -> str:
    return "<!DOCTYPE html><html><head><title>TikTok</title></head>" \
           "<body><div class='shell'></div></body></html>"


def oembed_payload():
    return {
        "title": "synthetic oembed title",
        "author_name": "Synthetic Creator",
        "author_url": f"https://www.tiktok.com/@{FAKE_HANDLE}",
        "author_unique_id": FAKE_HANDLE,
        "thumbnail_url": CDN_JPEG,
        "html": f"<blockquote class=\"tiktok-embed\" "
                f"data-video-id=\"{FAKE_ID}\">",
        "width": 325, "height": 580,
    }
