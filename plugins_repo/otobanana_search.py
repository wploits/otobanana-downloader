import os
import re
import sys
import time
import threading
import subprocess
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

PLUGIN_NAME = "otobanana-search"
PLUGIN_VERSION = "1.0.0"
PLUGIN_DESC = "OTOBANANAの音声をキーワード・カテゴリ・性別・並び順で検索してDL＆再生できるよ"

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
    cats = []
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
                        cats.append({"key": ck, "name": cname})
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

    sfprt(f"\nユーザー {user_name}")
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
    page_urls = {1: cur_url}
    page_cache = {}
    page_num = 1

    while True:
        mode_str = "R18" if is_adult else "一般"
        if page_num in page_cache:
            data = page_cache[page_num]
        else:
            clear_fn()
            sfprt("====================================")
            sfprt(f"ユーザー: {user_name} [{mode_str}] (ページ {page_num})")
            sfprt("====================================")
            sfprt("読み込みちゅう...")
            fetch_url = page_urls.get(page_num)
            if not fetch_url:
                sfprt("URLが見つからない")
                input("\nEnterキーで戻ります...")
                return
            try:
                r = req_mod.get(fetch_url, headers=headers, timeout=10)
                if r.status_code != 200:
                    sfprt(f"取得失敗 ({r.status_code})")
                    input("\nEnterキーで戻ります...")
                    return
                data = r.json()
                page_cache[page_num] = data
                nxt = data.get("next_page_url")
                if nxt:
                    page_urls[page_num + 1] = nxt
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
        if next_url or (page_num + 1) in page_urls:
            sfprt("n: 次のページ (next page)")
        if page_num > 1:
            sfprt("p: 前のページ (prev page)")
        sfprt("p[数字] (例: p4): 指定ページへジャンプ")
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
            page_urls = {1: cur_url}
            page_cache = {}
            page_num = 1
        elif c.lower() == "n":
            if next_url or (page_num + 1) in page_urls:
                page_num += 1
        elif c.lower() == "p":
            if page_num > 1:
                page_num -= 1
        elif re.match(r"^p\d+$", c.lower()):
            tp = int(c.lower()[1:])
            if tp < 1:
                tp = 1
            if tp == page_num:
                pass
            elif tp < page_num:
                page_num = tp
            else:
                while page_num < tp:
                    if page_num not in page_cache:
                        curl = page_urls.get(page_num)
                        if not curl:
                            break
                        try:
                            r = req_mod.get(curl, headers=headers, timeout=10)
                            if r.status_code != 200:
                                break
                            d = r.json()
                            page_cache[page_num] = d
                            nxt = d.get("next_page_url")
                            if nxt:
                                page_urls[page_num + 1] = nxt
                        except Exception:
                            break
                    d = page_cache.get(page_num, {})
                    nxt = d.get("next_page_url")
                    if not nxt:
                        sfprt(f"\nこれ以上ページがないよ (最大ページ: {page_num})")
                        time.sleep(1)
                        break
                    page_num += 1
                    page_urls[page_num] = nxt
                    clear_fn()
                    sfprt("====================================")
                    sfprt(f"ユーザー: {user_name} [{mode_str}]")
                    sfprt(f"ページ {tp} へ移動ちゅう... ({page_num}/{tp})")
                    sfprt("====================================")
        elif c.isdigit():
            val = int(c)
            if 1 <= val <= len(items):
                dlandply(items[val - 1], output_dir, req_mod, headers, sanitie_fn)

def brwscast(is_adult, query_summary, init_url, output_dir, max_workers, req_mod, headers, clear_fn, sanitie_fn):
    page_urls = {1: init_url}
    page_cache = {}
    page_num = 1

    while True:
        if page_num in page_cache:
            data = page_cache[page_num]
        else:
            clear_fn()
            sfprt("====================================")
            sfprt(f"検索結果: {query_summary} (ページ {page_num})")
            sfprt("====================================")
            sfprt("読み込みちゅう...")
            fetch_url = page_urls.get(page_num)
            if not fetch_url:
                sfprt("URLが見つからない")
                input("\nEnterキーで戻ります...")
                return
            try:
                r = req_mod.get(fetch_url, headers=headers, timeout=10)
                if r.status_code != 200:
                    sfprt(f"取得失敗 ({r.status_code})")
                    input("\nEnterキーで戻ります...")
                    return
                data = r.json()
                page_cache[page_num] = data
                nxt = data.get("next_page_url")
                if nxt:
                    page_urls[page_num + 1] = nxt
            except Exception as e:
                sfprt(f"えらー: {e}")
                input("\nEnterキーで戻ります...")
                return

        items = data.get("data", [])
        next_url = data.get("next_page_url")
        prev_url = data.get("prev_page_url")

        clear_fn()
        sfprt("====================================")
        sfprt(f"検索結果: {query_summary} (ページ {page_num})")
        sfprt("====================================")

        if not items:
            sfprt("該当する投稿が見つからなかった")
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
        if next_url or (page_num + 1) in page_urls:
            sfprt("n: 次のページ (next page)")
        if page_num > 1:
            sfprt("p: 前のページ (prev page)")
        sfprt("p[数字] (例: p4): 指定ページへジャンプ")
        sfprt("b: 検索条件に戻る")
        sfprt("------------------------------------")

        c = input("選択して: ").strip()
        if not c or c.lower() == "b":
            break
        elif c.lower() == "n":
            if next_url or (page_num + 1) in page_urls:
                page_num += 1
        elif c.lower() == "p":
            if page_num > 1:
                page_num -= 1
        elif re.match(r"^p\d+$", c.lower()):
            tp = int(c.lower()[1:])
            if tp < 1:
                tp = 1
            if tp == page_num:
                pass
            elif tp < page_num:
                page_num = tp
            else:
                while page_num < tp:
                    if page_num not in page_cache:
                        curl = page_urls.get(page_num)
                        if not curl:
                            break
                        try:
                            r = req_mod.get(curl, headers=headers, timeout=10)
                            if r.status_code != 200:
                                break
                            d = r.json()
                            page_cache[page_num] = d
                            nxt = d.get("next_page_url")
                            if nxt:
                                page_urls[page_num + 1] = nxt
                        except Exception:
                            break
                    d = page_cache.get(page_num, {})
                    nxt = d.get("next_page_url")
                    if not nxt:
                        sfprt(f"\nこれ以上ページがないよ (最大ページ: {page_num})")
                        time.sleep(1)
                        break
                    page_num += 1
                    page_urls[page_num] = nxt
                    clear_fn()
                    sfprt("====================================")
                    sfprt(f"検索結果: {query_summary}")
                    sfprt(f"ページ {tp} へ移動ちゅう... ({page_num}/{tp})")
                    sfprt("====================================")
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

def srchcfg(init_adult, output_dir, max_workers, req_mod, headers, clear_fn, sanitie_fn):
    is_adult = init_adult
    word = ""
    sel_cat = None
    gender = 0
    ordering = "-created_at"

    order_map = {
        "-created_at": "新着順",
        "-score": "人気順",
        "-liked": "ライク順",
        "created_at": "投稿順 (古い順)"
    }
    gender_map = {
        0: "指定なし",
        1: "男性",
        2: "女性",
        3: "その他"
    }

    while True:
        clear_fn()
        mode_label = "R18" if is_adult else "一般"
        cat_disp = sel_cat["name"] if sel_cat else "全カテゴリ"
        word_disp = word if word else "(指定なし)"
        gender_disp = gender_map.get(gender, "指定なし")
        order_disp = order_map.get(ordering, ordering)

        sfprt("====================================")
        sfprt(f"otobanana-search [{mode_label}]")
        sfprt("====================================")
        sfprt(f"1. キーワード : {word_disp}")
        sfprt(f"2. カテゴリ   : {cat_disp}")
        sfprt(f"3. 投稿者性別 : {gender_disp}")
        sfprt(f"4. 並び順     : {order_disp}")
        sfprt("------------------------------------")
        sfprt("s: この条件で検索実行")
        sfprt("t: 一般 / R18 切り替え")
        sfprt("c: 条件をクリア")
        sfprt("b: 戻る")
        sfprt("------------------------------------")

        c = input("選択して: ").strip()
        if not c or c.lower() == "b":
            break
        elif c.lower() == "t":
            is_adult = not is_adult
            sel_cat = None
        elif c.lower() == "c":
            word = ""
            sel_cat = None
            gender = 0
            ordering = "-created_at"
        elif c == "1":
            new_w = input(f"\n検索キーワードを入力 (現在: {word_disp} / 空欄で解除): ").strip()
            word = new_w
        elif c == "2":
            clear_fn()
            sfprt("カテゴリ取得ちゅう...")
            cats = getcats(is_adult, req_mod, headers)
            clear_fn()
            sfprt("====================================")
            sfprt(f"カテゴリ選択 [{mode_label}]")
            sfprt("====================================")
            sfprt("0. 指定なし (全カテゴリ)")
            for idx, ct in enumerate(cats, 1):
                sfprt(f"{idx}. {ct['name']}")
            sfprt("------------------------------------")
            sc = input("番号を選択: ").strip()
            if sc == "0":
                sel_cat = None
            elif sc.isdigit():
                val = int(sc)
                if 1 <= val <= len(cats):
                    sel_cat = cats[val - 1]
        elif c == "3":
            clear_fn()
            sfprt("====================================")
            sfprt("投稿者の性別を選択")
            sfprt("====================================")
            sfprt("0. 指定なし")
            sfprt("1. 男性")
            sfprt("2. 女性")
            sfprt("3. その他")
            sfprt("------------------------------------")
            sg = input("選択して (0-3): ").strip()
            if sg in ["0", "1", "2", "3"]:
                gender = int(sg)
        elif c == "4":
            clear_fn()
            sfprt("====================================")
            sfprt("並び順を選択")
            sfprt("====================================")
            sfprt("1. 新着順 (-created_at)")
            sfprt("2. 人気順 (-score)")
            sfprt("3. ライク順 (-liked)")
            sfprt("4. 投稿順 / 古い順 (created_at)")
            sfprt("------------------------------------")
            so = input("選択して (1-4): ").strip()
            if so == "1":
                ordering = "-created_at"
            elif so == "2":
                ordering = "-score"
            elif so == "3":
                ordering = "-liked"
            elif so == "4":
                ordering = "created_at"
        elif c.lower() == "s":
            b_str = "true" if is_adult else "false"
            params = [f"is_adult={b_str}"]
            if word:
                params.append(f"search={urllib.parse.quote(word)}")
            if sel_cat and sel_cat.get("key"):
                params.append(f"categoryKey={sel_cat['key']}")
            if gender and gender in [1, 2, 3]:
                params.append(f"user__gender={gender}")
            if ordering:
                params.append(f"ordering={ordering}")
            req_url = f"https://api.v2.otobanana.com/api/casts?{'&'.join(params)}"

            summary_parts = [f"[{mode_label}]"]
            if word:
                summary_parts.append(f"「{word}」")
            if sel_cat:
                summary_parts.append(sel_cat["name"])
            if gender in [1, 2, 3]:
                summary_parts.append(gender_map[gender])
            summary_parts.append(order_map.get(ordering, ordering))
            summary_str = " ".join(summary_parts)

            brwscast(is_adult, summary_str, req_url, output_dir, max_workers, req_mod, headers, clear_fn, sanitie_fn)

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
        sfprt("otobanana-search")
        sfprt("====================================")
        sfprt("1 R18音声を検索")
        sfprt("2 一般音声を検索")
        sfprt("3 戻る")
        sfprt("------------------------------------")

        c = input("選択して (1-3): ").strip()
        if c == "1":
            srchcfg(True, output_dir, max_workers, req_mod, headers, clear_fn, sanitie_fn)
        elif c == "2":
            srchcfg(False, output_dir, max_workers, req_mod, headers, clear_fn, sanitie_fn)
        elif c == "3" or c.lower() == "b" or not c:
            break
