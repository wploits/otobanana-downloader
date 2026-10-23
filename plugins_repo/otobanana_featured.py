import os
import re
import sys
import time
import threading
import subprocess
from concurrent.futures import ThreadPoolExecutor

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

def dlallusr(user_id, base_save_folder, max_workers, req_mod, headers, sanitie_fn):
    gen_casts = []
    adult_casts = []

    sfprt(f"\nユーザー ({user_id}) の全投稿を取得ちゅう...")

    url_gen = f"https://api.v2.otobanana.com/api/users/{user_id}/casts?is_adult=false"
    try:
        while url_gen:
            resp = req_mod.get(url_gen, headers=headers, timeout=10)
            if resp.status_code != 200:
                break
            data = resp.json()
            gen_casts.extend(data.get("data", []))
            url_gen = data.get("next_page_url")
            if url_gen:
                time.sleep(0.05)
    except Exception:
        pass

    url_adult = f"https://api.v2.otobanana.com/api/users/{user_id}/casts?is_adult=true"
    try:
        while url_adult:
            resp = req_mod.get(url_adult, headers=headers, timeout=10)
            if resp.status_code != 200:
                break
            data = resp.json()
            adult_casts.extend(data.get("data", []))
            url_adult = data.get("next_page_url")
            if url_adult:
                time.sleep(0.05)
    except Exception:
        pass

    total_gen = len(gen_casts)
    total_adult = len(adult_casts)
    total_all = total_gen + total_adult

    if total_all == 0:
        sfprt("投稿見つからなかったw")
        input("\nEnterキーで戻ります...")
        return

    sample_cast = gen_casts[0] if gen_casts else adult_casts[0]
    user_name = sample_cast.get("post", {}).get("user", {}).get("name", f"user_{user_id}")
    safe_username = sanitie_fn(user_name) or f"user_{user_id}"
    user_root_folder = os.path.join(base_save_folder, safe_username)

    sfprt(f"\nユーざー {user_name}")
    sfprt(f"一般: {total_gen} 件 / R18: {total_adult} 件 (合計 {total_all} 件)\n")

    mode = "3"
    if total_gen > 0 and total_adult > 0:
        sfprt("------------------------------------")
        sfprt(f"1 一般だけDL ({total_gen} 件)")
        sfprt(f"2 R18だけDL ({total_adult} 件)")
        sfprt(f"3 両方ダウンロード ({total_all} 件)")
        sfprt("------------------------------------")
        mode = input("選択して (1-3 / 空欄でキャンセル): ").strip()
    elif total_gen > 0:
        sfprt("一般だけみつかった")
        mode = "1"
    else:
        sfprt("R18だけみつかった")
        mode = "2"

    target_items = []
    if mode == "1" or mode == "3":
        folder_path = os.path.join(user_root_folder, "一般")
        for cast in gen_casts:
            target_items.append({"cast": cast, "folder": folder_path, "cat": "一般"})
    if mode == "2" or mode == "3":
        folder_path = os.path.join(user_root_folder, "R18")
        for cast in adult_casts:
            target_items.append({"cast": cast, "folder": folder_path, "cat": "R18"})

    if not target_items:
        sfprt("キャンセルされた")
        input("\nEnterキーで戻ります...")
        return

    total_tasks = len(target_items)
    sfprt(f"\n{total_tasks} 件開始 ({max_workers}並列)\n")

    completed_count = 0
    success_count = 0
    skip_count = 0
    print_lock = threading.Lock()

    def download_worker(item_data, task_idx):
        nonlocal completed_count, success_count, skip_count
        cast = item_data["cast"]
        target_folder = item_data["folder"]
        post = cast.get("post", {})
        title = post.get("title") or post.get("mask_title") or f"cast_{task_idx}"
        audurl = cast.get("audio_url")

        if not audurl:
            with print_lock:
                completed_count += 1
                sfprt(f"[{completed_count}/{total_tasks}] オーディオみつからんかった: {title}")
            return

        safe_title = sanitie_fn(title) or f"cast_{task_idx}"
        file_extension = audurl.split(".")[-1].split("?")[0]
        if len(file_extension) > 5 or not file_extension:
            file_extension = "mp3"

        filename = f"{safe_title}.{file_extension}"
        os.makedirs(target_folder, exist_ok=True)
        file_path = os.path.join(target_folder, filename)

        if os.path.exists(file_path):
            with print_lock:
                completed_count += 1
                skip_count += 1
                sfprt(f"[{completed_count}/{total_tasks}] 既にある？: [{item_data['cat']}] {filename}")
            return

        try:
            audio_resp = req_mod.get(audurl, headers=headers, timeout=30)
            if audio_resp.status_code == 200:
                with open(file_path, "wb") as f:
                    f.write(audio_resp.content)
                with print_lock:
                    completed_count += 1
                    success_count += 1
                    sfprt(f"[{completed_count}/{total_tasks}] せいこう: [{item_data['cat']}] {filename}")
            else:
                with print_lock:
                    completed_count += 1
                    sfprt(f"[{completed_count}/{total_tasks}] しっぱい: [{item_data['cat']}] {filename}")
        except Exception as inner_e:
            with print_lock:
                completed_count += 1
                sfprt(f"[{completed_count}/{total_tasks}] えらー: {filename} ({inner_e})")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(download_worker, item, idx) for idx, item in enumerate(target_items, 1)]
        for future in futures:
            future.result()

    sfprt(f"\n全部終わった (成功: {success_count}件 / スキップ: {skip_count}件 / 合計: {total_tasks}件)")
    input("\nEnterキーで戻ります...")

def brwsusr(user_id, user_name, init_adult, output_dir, max_workers, req_mod, headers, clear_fn, sanitie_fn):
    is_adult = init_adult
    b_str = "true" if is_adult else "false"
    cur_url = f"https://api.v2.otobanana.com/api/users/{user_id}/casts?is_adult={b_str}"
    page_num = 1
    history = []

    while True:
        mode_str = "R18" if is_adult else "一般"
        clear_fn()
        sfprt("====================================")
        sfprt(f"ユーザー: {user_name} [{mode_str}] (ページ {page_num})")
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
        sfprt(f"ユーザー: {user_name} [{mode_str}] (ページ {page_num})")
        sfprt("====================================")

        if not items:
            sfprt(f"このユーザーの[{mode_str}]投稿は見つからなかった (tで一般/R18切替)")
        else:
            for idx, item in enumerate(items, 1):
                post = item.get("post") or {}
                title = post.get("title") or post.get("mask_title") or "無題"
                dur = item.get("duration_time") or "--:--"
                likes = post.get("like_count", 0)
                plays = post.get("play_count", 0)
                sfprt(f" {idx}. {title}")
                sfprt(f"    └ 時間: {dur} | 再生: {plays} | いいね: {likes}")

        sfprt("------------------------------------")
        if items:
            sfprt(f"番号 (1-{len(items)}): ダウンロード＆再生")
        sfprt("a: このユーザーの音声を全部一括DL")
        sfprt("t: 一般 / R18 の表示切り替え")
        if next_url:
            sfprt("n: 次のページ (next page)")
        if prev_url or history:
            sfprt("p: 前のページ (prev page)")
        sfprt("b: 元のリストに戻る")
        sfprt("------------------------------------")

        c = input("選択して: ").strip()
        if not c or c.lower() == "b":
            break
        elif c.lower() == "a":
            dlallusr(user_id, output_dir, max_workers, req_mod, headers, sanitie_fn)
        elif c.lower() == "t":
            is_adult = not is_adult
            b_str = "true" if is_adult else "false"
            cur_url = f"https://api.v2.otobanana.com/api/users/{user_id}/casts?is_adult={b_str}"
            page_num = 1
            history = []
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

def brwscast(is_adult, mode_label, cat_name, init_url, output_dir, max_workers, req_mod, headers, clear_fn, sanitie_fn):
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
            sfprt(f"番号+u (例: 1u): そのユーザーの音声一覧・一括DL")
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
        else:
            m = re.match(r"^(?:(\d+)u|u(\d+))$", c.lower())
            if m:
                val = int(m.group(1) or m.group(2))
                if 1 <= val <= len(items):
                    target_item = items[val - 1]
                    post = target_item.get("post") or {}
                    user = post.get("user") or {}
                    uid = post.get("user_id") or user.get("id")
                    uname = user.get("name") or user.get("mask_name") or f"user_{uid}"
                    if uid:
                        brwsusr(uid, uname, is_adult, output_dir, max_workers, req_mod, headers, clear_fn, sanitie_fn)

def catmnu(is_adult, output_dir, max_workers, req_mod, headers, clear_fn, sanitie_fn):
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
                brwscast(is_adult, mode_label, target["name"], target["ep"], output_dir, max_workers, req_mod, headers, clear_fn, sanitie_fn)

def run(ctx):
    output_dir = ctx["output_dir"]
    max_workers = ctx.get("max_workers", 5)
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
            catmnu(True, output_dir, max_workers, req_mod, headers, clear_fn, sanitie_fn)
        elif c == "2":
            catmnu(False, output_dir, max_workers, req_mod, headers, clear_fn, sanitie_fn)
        elif c == "3" or c.lower() == "b" or not c:
            break
