import os
import sys
import subprocess

PLUGIN_NAME = "otobanana-featured"
PLUGIN_VERSION = "1.0.0"
PLUGIN_DESC = "OTOBANANAの新着・人気・カテゴリ別音声をCLIで見てそのままDL＆再生できるよ"

def sfprt(txt):
    try:
        print(txt)
    except Exception:
        enc = sys.stdout.encoding or "utf-8"
        print(str(txt).encode(enc, errors="replace").decode(enc, errors="replace"))

def opnfl(filepath):
    try:
        if os.name == "nt":
            os.startfile(filepath)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", filepath])
        else:
            subprocess.Popen(["xdg-open", filepath])
    except Exception as e:
        sfprt(f"再生アプリを開けなかった: {e}")

def getcats(is_adult, req_mod, headers):
    b_str = "true" if is_adult else "false"
    cats = [
        {"name": "新着順", "ep": f"https://api.v2.otobanana.com/api/casts/latestindex?is_adult={b_str}"},
        {"name": "人気順", "ep": f"https://api.v2.otobanana.com/api/casts/scoreindex?is_adult={b_str}"}
    ]
    try:
        url = f"https://api.v2.otobanana.com/api/casts/categories?is_adult={b_str}"
        r = req_mod.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                for c in data:
                    ck = c.get("category_key")
                    cname = c.get("name", ck)
                    if ck:
                        cats.append({
                            "name": cname,
                            "ep": f"https://api.v2.otobanana.com/api/casts/scoreindex/{ck}?is_adult={b_str}"
                        })
    except Exception:
        pass
    return cats

def dlandply(cast, output_dir, req_mod, headers, sanitie_fn):
    post = cast.get("post") or {}
    cast_id = post.get("id") or cast.get("post_ptr_id") or "unknown"
    title = post.get("title") or post.get("mask_title") or f"cast_{cast_id}"
    safe_title = sanitie_fn(title) or f"cast_{cast_id}"
    audurl = cast.get("audio_url") or cast.get("audurl")

    if not audurl:
        try:
            r = req_mod.get(f"https://api.v2.otobanana.com/api/casts/{cast_id}", headers=headers, timeout=10)
            if r.status_code == 200:
                d = r.json()
                audurl = d.get("audio_url") or d.get("audurl")
        except Exception:
            pass

    if not audurl:
        sfprt("オーディオURLがみつからない")
        input("\nEnterキーで戻ります...")
        return

    ext = audurl.split(".")[-1].split("?")[0]
    if len(ext) > 5 or not ext:
        ext = "mp3"

    os.makedirs(output_dir, exist_ok=True)
    filename = f"{safe_title}.{ext}"
    file_path = os.path.join(output_dir, filename)

    if os.path.exists(file_path):
        sfprt(f"\nすでに保存済み: {file_path}")
    else:
        sfprt(f"\nダウンロードちゅう: {filename} ...")
        try:
            ar = req_mod.get(audurl, headers=headers, timeout=30)
            if ar.status_code == 200:
                with open(file_path, "wb") as f:
                    f.write(ar.content)
                sfprt(f"保存せいこう！: {file_path}")
            else:
                sfprt(f"ダウンロード失敗 ({ar.status_code})")
                input("\nEnterキーで戻ります...")
                return
        except Exception as e:
            sfprt(f"えらー: {e}")
            input("\nEnterキーで戻ります...")
            return

    ans = input("\n今すぐ再生する？ (y/n): ").strip().lower()
    if ans == "y":
        opnfl(file_path)

def brwscast(mode_label, cat_name, init_url, output_dir, req_mod, headers, clear_fn, sanitie_fn):
    cur_url = init_url
    page_num = 1
    history = []

    while True:
        clear_fn()
        sfprt("====================================")
        sfprt(f"[{mode_label}] {cat_name} (ページ {page_num})")
        sfprt("====================================")
        sfprt("読み込みちゅう...")

        try:
            r = req_mod.get(cur_url, headers=headers, timeout=10)
            if r.status_code != 200:
                sfprt(f"取得失敗 ({r.status_code})")
                input("\nEnterキーで戻ります...")
                return
            data = r.json()
        except Exception as e:
            sfprt(f"えらー: {e}")
            input("\nEnterキーで戻ります...")
            return

        items = data.get("data", [])
        next_url = data.get("next_page_url")
        prev_url = data.get("prev_page_url")

        clear_fn()
        sfprt("====================================")
        sfprt(f"[{mode_label}] {cat_name} (ページ {page_num})")
        sfprt("====================================")

        if not items:
            sfprt("投稿が見つからなかった")
        else:
            for idx, item in enumerate(items, 1):
                post = item.get("post") or {}
                title = post.get("title") or post.get("mask_title") or "無題"
                user = post.get("user") or {}
                uname = user.get("name") or user.get("mask_name") or "不明"
                dur = item.get("duration_time") or "--:--"
                likes = post.get("like_count", 0)
                plays = post.get("play_count", 0)
                sfprt(f" {idx}. {title}")
                sfprt(f"    └ {uname} | 時間: {dur} | 再生: {plays} | いいね: {likes}")

        sfprt("------------------------------------")
        if items:
            sfprt(f"番号 (1-{len(items)}): ダウンロード＆再生")
        if next_url:
            sfprt("n: 次のページ (next page)")
        if prev_url or history:
            sfprt("p: 前のページ (prev page)")
        sfprt("b: カテゴリ選択に戻る")
        sfprt("------------------------------------")

        c = input("選択して: ").strip()
        if not c or c.lower() == "b":
            break
        elif c.lower() == "n" and next_url:
            history.append(cur_url)
            cur_url = next_url
            page_num += 1
        elif c.lower() == "p" and (history or prev_url):
            if history:
                cur_url = history.pop()
            else:
                cur_url = prev_url
            page_num = max(1, page_num - 1)
        elif c.isdigit():
            val = int(c)
            if 1 <= val <= len(items):
                dlandply(items[val - 1], output_dir, req_mod, headers, sanitie_fn)

def catmnu(is_adult, output_dir, req_mod, headers, clear_fn, sanitie_fn):
    mode_label = "R18 (Deep)" if is_adult else "一般 (General)"
    clear_fn()
    sfprt("カテゴリ取得ちゅう...")
    cats = getcats(is_adult, req_mod, headers)

    while True:
        clear_fn()
        sfprt("====================================")
        sfprt(f"otobanana-featured [{mode_label}]")
        sfprt("====================================")
        for idx, cat in enumerate(cats, 1):
            sfprt(f" {idx}. {cat['name']}")
        sfprt("------------------------------------")
        sfprt("b: 戻る")
        sfprt("------------------------------------")

        c = input(f"選択して (1-{len(cats)} / b): ").strip()
        if not c or c.lower() == "b":
            break
        if c.isdigit():
            val = int(c)
            if 1 <= val <= len(cats):
                target = cats[val - 1]
                brwscast(mode_label, target["name"], target["ep"], output_dir, req_mod, headers, clear_fn, sanitie_fn)

def run(ctx):
    output_dir = ctx["output_dir"]
    headers = ctx["headers"]
    clear_fn = ctx["clear"]
    sanitie_fn = ctx["sanitieflnm"]
    req_mod = ctx["requests"]

    while True:
        clear_fn()
        sfprt("====================================")
        sfprt("otobanana-featured")
        sfprt("====================================")
        sfprt("1 R18 (新着・人気・男性向け・女性向け・BL・GL・マニアック・その他)")
        sfprt("2 一般 (新着・人気・雑談・読み聞かせ・ASMR・趣味・その他)")
        sfprt("3 戻る")
        sfprt("------------------------------------")

        c = input("選択して (1-3): ").strip()
        if c == "1":
            catmnu(True, output_dir, req_mod, headers, clear_fn, sanitie_fn)
        elif c == "2":
            catmnu(False, output_dir, req_mod, headers, clear_fn, sanitie_fn)
        elif c == "3" or c.lower() == "b" or not c:
            break
