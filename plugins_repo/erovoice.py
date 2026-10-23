import os
import re
import ctypes
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

PLUGIN_NAME = "erovoice-chダウンローダー"
PLUGIN_VERSION = "1.2.0"
PLUGIN_DESC = "erovoice-chから単一＆ユーザー全音声を保存するよ (ffmpegがあればMP3自動変換)"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36"

def extid(link):
    link = link.strip()
    m = re.search(r'/(?:ero-voice|ero-asmr|moe-asmr)/(\d+)', link)
    if m:
        return m.group(1)
    if link.isdigit():
        return link
    return None

def extuid(link):
    link = link.strip().rstrip('/')
    m = re.search(r'erovoice-ch\.com/([a-zA-Z0-9_\-]+)', link)
    if m:
        return m.group(1)
    if not link.startswith("http"):
        return link
    return None

def decaes(k, iv, data):
    try:
        from Crypto.Cipher import AES
        return AES.new(k, AES.MODE_CBC, iv=iv).decrypt(data)
    except Exception:
        pass
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        c = Cipher(algorithms.AES(k), modes.CBC(iv))
        dec = c.decryptor()
        return dec.update(data) + dec.finalize()
    except Exception:
        pass
    if os.name == 'nt':
        try:
            bcrypt = ctypes.windll.bcrypt
            hAlg = ctypes.c_void_p()
            bcrypt.BCryptOpenAlgorithmProvider(ctypes.byref(hAlg), ctypes.c_wchar_p('AES'), None, 0)
            mode = ctypes.create_unicode_buffer('ChainingModeCBC')
            bcrypt.BCryptSetProperty(hAlg, ctypes.c_wchar_p('ChainingMode'), ctypes.cast(mode, ctypes.c_char_p), ctypes.sizeof(mode), 0)
            hKey = ctypes.c_void_p()
            bcrypt.BCryptGenerateSymmetricKey(hAlg, ctypes.byref(hKey), None, 0, k, len(k), 0)
            iv_buf = ctypes.create_string_buffer(iv, len(iv))
            out_buf = ctypes.create_string_buffer(len(data))
            cb_res = ctypes.c_ulong(0)
            st = bcrypt.BCryptDecrypt(
                hKey, data, len(data),
                None, iv_buf, len(iv),
                out_buf, len(out_buf), ctypes.byref(cb_res), 0
            )
            bcrypt.BCryptDestroyKey(hKey)
            bcrypt.BCryptCloseAlgorithmProvider(hAlg, 0)
            if st == 0:
                return bytes(out_buf[:cb_res.value])
        except Exception:
            pass
    if shutil.which("openssl"):
        try:
            cmd = ["openssl", "enc", "-d", "-aes-128-cbc", "-K", k.hex(), "-iv", iv.hex(), "-nopad"]
            proc = subprocess.run(cmd, input=data, capture_output=True)
            if proc.returncode == 0 and proc.stdout:
                return proc.stdout
        except Exception:
            pass
    raise RuntimeError("decrypt error")

def tstoaac(ts_bytes):
    pes = bytearray()
    for i in range(0, len(ts_bytes), 188):
        pkt = ts_bytes[i:i+188]
        if len(pkt) < 188 or pkt[0] != 0x47:
            continue
        pid = ((pkt[1] & 0x1f) << 8) | pkt[2]
        if pid != 0x100:
            continue
        afc = (pkt[3] & 0x30) >> 4
        if afc == 1:
            pes.extend(pkt[4:])
        elif afc == 3:
            pes.extend(pkt[5 + pkt[4]:])

    aac = bytearray()
    idx = 0
    while idx < len(pes):
        p = pes.find(b'\x00\x00\x01', idx)
        if p == -1:
            break
        sid = pes[p+3]
        if sid in [0xC0, 0xBD] or 0xC0 <= sid <= 0xDF:
            plen = (pes[p+4] << 8) | pes[p+5]
            hlen = pes[p+8]
            h_end = p + 9 + hlen
            if plen > 0:
                nxt = p + 6 + plen
                aac.extend(pes[h_end:nxt])
                idx = nxt
            else:
                nxt = pes.find(b'\x00\x00\x01', h_end)
                if nxt != -1:
                    aac.extend(pes[h_end:nxt])
                    idx = nxt
                else:
                    aac.extend(pes[h_end:])
                    break
        else:
            idx = p + 3
    return aac

def gettitle(cast_id, req_mod, sanitie_fn):
    headers = {
        "User-Agent": UA,
        "Referer": f"https://erovoice-ch.com/ero-asmr/{cast_id}.html"
    }
    for prefix in ["ero-voice", "ero-asmr", "moe-asmr"]:
        try:
            url = f"https://erovoice-ch.com/{prefix}/{cast_id}.html"
            res = req_mod.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                txt = res.content.decode("utf-8", errors="ignore")
                m_title = re.search(r"<title>(.*?)</title>", txt)
                if m_title:
                    raw_t = m_title.group(1).split("|")[0].strip()
                    t = sanitie_fn(raw_t)
                    if t:
                        return t
                m = re.search(r'<h1[^>]*>(.*?)</h1>', txt)
                if m:
                    t = sanitie_fn(m.group(1))
                    if t:
                        return t
        except Exception:
            pass
    return f"erovoice_{cast_id}"

def getuseritems(user_slug, req_mod, sanitie_fn):
    headers = {"User-Agent": UA}
    url = f"https://erovoice-ch.com/{user_slug}"
    try:
        r = req_mod.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return None, []
        txt = r.content.decode("utf-8", errors="ignore")
        m_uname = re.search(r"<title>(.*?)さんのプロフィールページ", txt)
        user_name = sanitie_fn(m_uname.group(1)) if m_uname else f"user_{user_slug}"

        cards = re.findall(r'<a[^>]+href=[\'"]https://erovoice-ch\.com/(?:ero-voice|ero-asmr|moe-asmr)/(\d+)\.html[\'"][^>]*>([\s\S]*?)</a>', txt)
        items = []
        seen = set()
        for vid, inner in cards:
            if vid in seen:
                continue
            seen.add(vid)
            h_m = re.search(r'<h[2-4][^>]*>(.*?)</h[2-4]>', inner)
            alt_m = re.search(r'alt=[\'"]([^\'"]+)[\'"]', inner)
            title = ""
            if h_m:
                title = re.sub(r'<[^>]+>', '', h_m.group(1)).strip()
            elif alt_m:
                title = alt_m.group(1).strip()
            title = sanitie_fn(title) or f"voice_{vid}"
            items.append((vid, title))
        return user_name, items
    except Exception:
        return None, []

def dlone(cast_id, title, save_folder, max_workers, req_mod):
    headers = {
        "User-Agent": UA,
        "Referer": f"https://erovoice-ch.com/ero-asmr/{cast_id}.html"
    }
    os.makedirs(save_folder, exist_ok=True)
    aac_file = os.path.join(save_folder, f"{title}.aac")
    mp3_file = os.path.join(save_folder, f"{title}.mp3")
    if os.path.exists(mp3_file) or os.path.exists(aac_file):
        return "skip"

    m3u8_url = f"https://erovoice-ch.com/wp-content/themes/erovoice-ch/libs/getm3u8file_origints.php?id={cast_id}"
    try:
        m_res = req_mod.get(m3u8_url, headers=headers, timeout=10)
        if m_res.status_code != 200:
            return "fail"
        ts_urls = [l.strip() for l in m_res.text.splitlines() if l.strip().startswith("http")]
        if not ts_urls:
            return "fail"

        k_url = "https://erovoice-ch.com/wp-content/themes/erovoice-ch/libs/keygen.php"
        k_res = req_mod.get(k_url, headers=headers, timeout=10)
        if k_res.status_code != 200:
            return "fail"
        key = k_res.content

        total = len(ts_urls)
        seg_results = [None] * total

        def dl_seg(idx, url):
            try:
                r = req_mod.get(url, headers=headers, timeout=20)
                if r.status_code == 200:
                    dec = decaes(key, b'\x00' * 16, r.content)
                    seg_results[idx] = tstoaac(dec)
            except Exception:
                pass

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(dl_seg, i, u) for i, u in enumerate(ts_urls)]
            for f in futures:
                f.result()

        full_aac = bytearray()
        for seg in seg_results:
            if seg:
                full_aac.extend(seg)

        if not full_aac:
            return "fail"

        with open(aac_file, "wb") as f:
            f.write(full_aac)

        if shutil.which("ffmpeg"):
            cmd = ["ffmpeg", "-y", "-i", aac_file, "-vn", "-c:a", "libmp3lame", "-q:a", "2", mp3_file]
            p = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if p.returncode == 0 and os.path.exists(mp3_file):
                try:
                    os.remove(aac_file)
                except Exception:
                    pass
                return "ok_mp3"

        return "ok_aac"
    except Exception:
        return "fail"

def run(ctx):
    output_dir = ctx["output_dir"]
    max_workers = ctx.get("max_workers", 5)
    clear = ctx["clear"]
    sanitieflnm = ctx["sanitieflnm"]
    req = ctx["requests"]

    while True:
        clear()
        has_ff = "あり (MP3保存)" if shutil.which("ffmpeg") else "なし (AAC保存)"
        print("====================================")
        print("erovoice-ch ダウンローダー")
        print(f"ffmpeg状態: {has_ff}")
        print("※ffmpegがない環境では、ダウンロードした音声ファイルの拡張子が.aacになります。")
        print("====================================")
        print("1 音声1個DL")
        print("2 ユーザーの音声を全部DL")
        print("3 戻る")
        print("------------------------------------")

        c = input("選択して (1-3): ").strip()

        if c == "1":
            clear()
            print("音声1個DL")
            link = input("URLまたはIDを入力 (空白で戻る): ").strip()
            if not link:
                continue
            cast_id = extid(link)
            if not cast_id:
                print("無効なURLまたはIDです")
                input("\nEnterキーで戻ります...")
                continue
            print(f"\n情報取得ちゅう... (ID: {cast_id})")
            title = gettitle(cast_id, req, sanitieflnm)
            print(f"タイトル: {title}")
            print(f"ダウンロードちゅう... ({max_workers}並列)")
            res = dlone(cast_id, title, output_dir, max_workers, req)
            if res in ["ok_mp3", "ok_aac"]:
                ext = "mp3" if res == "ok_mp3" else "aac"
                print(f"\n保存せいこう！: {os.path.join(output_dir, f'{title}.{ext}')}")
            elif res == "skip":
                print(f"\nすでに保存されてるよ: {title}")
            else:
                print("\nダウンロードに失敗しました")
            input("\nEnterキーで戻ります...")

        elif c == "2":
            clear()
            print("ユーザーの音声を全部DL")
            print("※ ユーザーページのURL または ユーザーID (例: user_id_114514)")
            link = input("入力 (空白で戻る): ").strip()
            if not link:
                continue
            uid = extuid(link)
            if not uid:
                print("無効な入力です")
                input("\nEnterキーで戻ります...")
                continue
            print(f"\nユーザー ({uid}) の音声を取得ちゅう...")
            user_name, items = getuseritems(uid, req, sanitieflnm)
            if not items:
                print("音声が見つからなかった")
                input("\nEnterキーで戻ります...")
                continue

            user_folder = os.path.join(output_dir, user_name)
            total = len(items)
            print(f"\nユーザー: {user_name}")
            print(f"見つかった音声: {total} 件\n")

            ans = input("ダウンロード開始する？ (y/n): ").strip().lower()
            if ans != "y":
                continue

            print(f"\n{total} 件開始 ({max_workers}並列)\n")
            ok_cnt = 0
            skip_cnt = 0

            for idx, (vid, title) in enumerate(items, 1):
                res = dlone(vid, title, user_folder, max_workers, req)
                if res in ["ok_mp3", "ok_aac"]:
                    ok_cnt += 1
                    ext = "mp3" if res == "ok_mp3" else "aac"
                    print(f"[{idx}/{total}] せいこう: {title}.{ext}")
                elif res == "skip":
                    skip_cnt += 1
                    print(f"[{idx}/{total}] 既にある: {title}")
                else:
                    print(f"[{idx}/{total}] しっぱい: {title}")

            print(f"\n全部終わった (成功: {ok_cnt}件 / スキップ: {skip_cnt}件 / 合計: {total}件)")
            input("\nEnterキーで戻ります...")

        elif c == "3" or c.lower() == "b":
            break
