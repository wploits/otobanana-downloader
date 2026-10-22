import os
import re
import sys
import time
import json
import threading
import subprocess
import importlib.util
from concurrent.futures import ThreadPoolExecutor

try:
    import requests
except ImportError:
    print("ライブラリインストール中")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

CONFIG_FILE = "config.json"
MAX_WORKERS = 5
VERSION = "2.1.0"
INFO_URL = "https://raw.githubusercontent.com/wploits/otobanana-downloader/main/info.json"
PLUGINS_URL = "https://raw.githubusercontent.com/wploits/otobanana-downloader/main/plugins.json"

BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
PLUGINS_DIR = os.path.join(BASE_DIR, "plugins")

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

def guivs():
    if os.name != 'nt':
        return None
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes('-topmost', True)
        except Exception:
            pass
        root.focus_force()
        folder_selected = filedialog.askdirectory(title="保存先フォルダーを選択して")
        root.destroy()
        return folder_selected if folder_selected else None
    except Exception:
        return None

def ldcfg():
    default_cfg = {"output_dir": ".", "max_workers": MAX_WORKERS, "never_update": False}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                if "output_dir" not in config or not config["output_dir"]:
                    config["output_dir"] = "."
                if "max_workers" not in config or not isinstance(config["max_workers"], int) or config["max_workers"] < 1:
                    config["max_workers"] = MAX_WORKERS
                if "never_update" not in config:
                    config["never_update"] = False
                return config
        except Exception:
            pass
    return default_cfg

def svcfg(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"セーブ失敗した {e}")

config = ldcfg()

def prsvr(v):
    return tuple(int(x) for x in re.findall(r'\d+', str(v)))

def chkupd():
    global config
    if getattr(sys, 'frozen', False):
        old_exe = sys.executable + ".old"
        if os.path.exists(old_exe):
            try:
                os.remove(old_exe)
            except Exception:
                pass

    if config.get("never_update"):
        return

    try:
        resp = requests.get(f"{INFO_URL}?t={int(time.time())}", headers=HEADERS, timeout=5)
        if resp.status_code != 200:
            return
        info = resp.json()
    except Exception:
        return

    rmt_ver = info.get("version")
    if not rmt_ver:
        return

    try:
        if prsvr(rmt_ver) <= prsvr(VERSION):
            return
    except Exception:
        if rmt_ver == VERSION:
            return

    clear()
    print("====================================")
    print(f"新しいバージョンがあるよ！ (v{VERSION} -> v{rmt_ver})")
    print("====================================")
    changelog = info.get("changelog")
    if changelog:
        print("\n【更新内容】")
        if isinstance(changelog, list):
            for line in changelog:
                print(f"・{line}")
        else:
            print(changelog)
        print()

    while True:
        ans = input("アプデあるよ！更新する？(y/n/never): ").strip().lower()
        if ans in ["y", "n", "never"]:
            break

    if ans == "n":
        return
    elif ans == "never":
        config["never_update"] = True
        svcfg(config)
        print("今後は通知しないようにしたよ")
        time.sleep(1)
        return

    is_exe = getattr(sys, 'frozen', False)
    dl_url = info.get("exeurl") if is_exe else info.get("pyrawurl")
    if not dl_url:
        print("ダウンロードURLがみつからない")
        time.sleep(2)
        return

    print("\nアップデートをダウンロードちゅう...")
    try:
        r = requests.get(dl_url, headers=HEADERS, timeout=60)
        if r.status_code != 200:
            print(f"ダウンロード失敗... ステータスコード: {r.status_code}")
            time.sleep(2)
            return

        if is_exe:
            cur_exe = sys.executable
            tmp_exe = cur_exe + ".new"
            old_exe = cur_exe + ".old"
            with open(tmp_exe, "wb") as f:
                f.write(r.content)
            if os.path.exists(old_exe):
                try:
                    os.remove(old_exe)
                except Exception:
                    pass
            try:
                os.rename(cur_exe, old_exe)
                os.rename(tmp_exe, cur_exe)
                print("更新せいこう！再起動するよ...")
                time.sleep(1)
                subprocess.Popen([cur_exe] + sys.argv[1:])
                sys.exit(0)
            except Exception:
                bat_path = os.path.join(os.path.dirname(cur_exe), "upd_tmp.bat")
                with open(bat_path, "w", encoding="cp932") as bf:
                    bf.write(
                        f'@echo off\n'
                        f'timeout /t 2 /nobreak >nul\n'
                        f'move /y "{tmp_exe}" "{cur_exe}" >nul\n'
                        f'start "" "{cur_exe}"\n'
                        f'del "%~f0"\n'
                    )
                print("更新せいこう！再起動するよ...")
                time.sleep(1)
                subprocess.Popen(["cmd", "/c", bat_path], creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                sys.exit(0)
        else:
            cur_py = os.path.abspath(__file__)
            with open(cur_py, "wb") as f:
                f.write(r.content)
            print("更新せいこう！再起動するよ...")
            time.sleep(1)
            os.execv(sys.executable, [sys.executable, cur_py] + sys.argv[1:])
    except Exception as e:
        print(f"アップデートえらー {e}")
        time.sleep(2)

def sanitieflnm(filename):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename).strip()

def extcss(link):
    link = link.strip()
    match = re.search(r'/casts?/([^/?#]+)', link)
    if match:
        return match.group(1)
    if not link.startswith("http"):
        return link
    return None

def byhandl(handle):
    handle = handle.lstrip('@').strip()
    if not handle:
        return None
    for is_adult in ['false', 'true']:
        try:
            url = f"https://api.v2.otobanana.com/api/users?is_adult={is_adult}&search={handle}"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                for user in data:
                    if user.get("username", "").lower() == handle.lower():
                        return user.get("id")
                for user in data:
                    if user.get("name", "").lower() == handle.lower():
                        return user.get("id")
                if data and "id" in data[0]:
                    return data[0]["id"]
        except Exception:
            pass
    return None

def extusrid(link):
    link = link.strip()
    
    match = re.search(r'/user/([^/?#]+)', link)
    target = match.group(1) if match else link
    
    if re.match(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$', target):
        return target
        
    found_id = byhandl(target)
    if found_id:
        return found_id
        
    if not link.startswith("http"):
        return link
        
    return None

def dlsgc(cast_id, save_folder):
    api_url = f"https://api.v2.otobanana.com/api/casts/{cast_id}"
    try:
        response = requests.get(api_url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            try:
                data = response.json()
                post = data.get('post') or {}
                title = post.get('title') or f"cast_{cast_id}"
                sanitized_title = sanitieflnm(title) or f"cast_{cast_id}"
                
                audurl = data.get('audio_url') or data.get('audurl')
                if audurl:
                    audio_response = requests.get(audurl, headers=HEADERS, timeout=30)
                    if audio_response.status_code == 200:
                        file_extension = audurl.split('.')[-1].split('?')[0]
                        if len(file_extension) > 5 or not file_extension:
                            file_extension = "mp3"
                        
                        filename = f"{sanitized_title}.{file_extension}"
                        os.makedirs(save_folder, exist_ok=True)
                        file_path = os.path.join(save_folder, filename)
                        
                        with open(file_path, 'wb') as file:
                            file.write(audio_response.content)
                        print(f"保存せいこう {filename}")
                        return True
                    else:
                        print("失敗...")
                else:
                    print("オーディオURLみつからない")
            except ValueError:
                print("err jsonじゃなかった")
        else:
            print("失敗。ステータスコード:", response.status_code)
    except Exception as e:
        print(f"えらー {e}")
    return False

def dlallc(user_id, base_save_folder):
    gen_casts = []
    adult_casts = []
    
    print(f"\nユーザー ({user_id}) の投稿を取得ちゅう")
    
    url_gen = f"https://api.v2.otobanana.com/api/users/{user_id}/casts?is_adult=false"
    try:
        while url_gen:
            resp = requests.get(url_gen, headers=HEADERS, timeout=10)
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
            resp = requests.get(url_adult, headers=HEADERS, timeout=10)
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
        print("投稿見つからなかったw")
        return

    sample_cast = gen_casts[0] if gen_casts else adult_casts[0]
    user_name = sample_cast.get('post', {}).get('user', {}).get('name', f"user_{user_id}")
    safe_username = sanitieflnm(user_name)
    user_root_folder = os.path.join(base_save_folder, safe_username)

    print(f"\nユーざー {user_name}")
    print(f"一般: {total_gen} 件 / R18: {total_adult} 件 (合計 {total_all} 件)\n")

    mode = "3"
    if total_gen > 0 and total_adult > 0:
        print("------------------------------------")
        print(f"1 一般だけDL ({total_gen} 件)")
        print(f"2 R18だけDL ({total_adult} 件)")
        print(f"3 両方ダウンロード ({total_all} 件)")
        print("------------------------------------")
        mode = input("選択して (1-3): ").strip()
    elif total_gen > 0:
        print("一般だけみつかった")
        mode = "1"
    else:
        print("R18だけみつかった")
        mode = "2"

    target_items = []
    
    if mode == "1" or mode == "3":
        folder_path = os.path.join(user_root_folder, "一般") if (total_gen > 0 and total_adult > 0) else os.path.join(user_root_folder, "一般")
        for cast in gen_casts:
            target_items.append({"cast": cast, "folder": folder_path, "cat": "一般"})
            
    if mode == "2" or mode == "3":
        folder_path = os.path.join(user_root_folder, "R18") if (total_gen > 0 and total_adult > 0) else os.path.join(user_root_folder, "R18")
        for cast in adult_casts:
            target_items.append({"cast": cast, "folder": folder_path, "cat": "R18"})

    if not target_items:
        print("キャンセルされた")
        return

    workers = config.get("max_workers", MAX_WORKERS)
    total_tasks = len(target_items)
    print(f"\n{total_tasks} 件開始 ({workers}並列)\n")

    completed_count = 0
    success_count = 0
    skip_count = 0
    print_lock = threading.Lock()

    def download_worker(item_data, task_idx):
        nonlocal completed_count, success_count, skip_count
        cast = item_data["cast"]
        target_folder = item_data["folder"]
        
        post = cast.get('post', {})
        title = post.get('title', f"cast_{task_idx}")
        audurl = cast.get('audio_url')
        
        if not audurl:
            with print_lock:
                completed_count += 1
                print(f"[{completed_count}/{total_tasks}] オーディオみつからんかった: {title}")
            return

        safe_title = sanitieflnm(title)
        file_extension = audurl.split('.')[-1].split('?')[0]
        if len(file_extension) > 5 or not file_extension:
            file_extension = "mp3"
            
        filename = f"{safe_title}.{file_extension}"
        os.makedirs(target_folder, exist_ok=True)
        file_path = os.path.join(target_folder, filename)

        if os.path.exists(file_path):
            with print_lock:
                completed_count += 1
                skip_count += 1
                print(f"[{completed_count}/{total_tasks}] 既にある？: [{item_data['cat']}] {filename}")
            return

        try:
            audio_resp = requests.get(audurl, headers=HEADERS, timeout=30)
            if audio_resp.status_code == 200:
                with open(file_path, "wb") as f:
                    f.write(audio_resp.content)
                with print_lock:
                    completed_count += 1
                    success_count += 1
                    print(f"[{completed_count}/{total_tasks}] せいこう: [{item_data['cat']}] {filename}")
            else:
                with print_lock:
                    completed_count += 1
                    print(f"[{completed_count}/{total_tasks}] しっぱい: [{item_data['cat']}] {filename}")
        except Exception as inner_e:
            with print_lock:
                completed_count += 1
                print(f"[{completed_count}/{total_tasks}] えらー: {filename} ({inner_e})")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(download_worker, item, idx) for idx, item in enumerate(target_items, 1)]
        for future in futures:
            future.result()

    print(f"\n全部終わった (成功: {success_count}件 / スキップ: {skip_count}件 / 合計: {total_tasks}件)")
    print("Github Repositoryにスターお願いします()")

def stgmnu():
    global config
    while True:
        clear()
        output_dir = os.path.abspath(config.get("output_dir", "."))
        workers = config.get("max_workers", MAX_WORKERS)
        never_upd = config.get("never_update", False)
        upd_str = "OFF (通知しない)" if never_upd else "ON (通知する)"

        print("====================================")
        print("設定")
        print("====================================")
        print(f"現在の保存先: {output_dir}")
        print(f"現在の並列数: {workers}")
        print(f"アプデ通知  : {upd_str}")
        print("------------------------------------")
        print("1 出力先フォルダー変更(選択)")
        print("2 並列数の変更")
        print("3 アプデ通知の切り替え")
        print("4 戻る")
        print("------------------------------------")

        sub = input("選択して (1-4): ").strip()

        if sub == "1":
            clear()
            print("出力先フォルダー変更")
            print(f"今の保存先: {output_dir}\n")
            
            slpath = None
            
            if os.name == 'nt':
                slpath = guivs()
            
            if not slpath:
                newpath = input("新しい保存先フォルダーのパスを入力 (空欄でキャンセル): ").strip()
                if newpath:
                    slpath = os.path.expanduser(newpath)
                else:
                    print("辞めた")
            
            if slpath:
                try:
                    os.makedirs(slpath, exist_ok=True)
                    config["output_dir"] = slpath
                    svcfg(config)
                    print(f"\n成功 新しい保存先: {os.path.abspath(slpath)}")
                except Exception as e:
                    print(f"\n設定失敗: {e}")
                    
            input("\nEnterキーを押すと設定に戻ります...")

        elif sub == "2":
            clear()
            print("並列数の変更")
            print(f"今の並列数: {workers}\n")
            newwk = input("新しい並列数を入力 (1〜20くらい推奨 / 空欄でキャンセル): ").strip()
            if newwk:
                if newwk.isdigit() and int(newwk) >= 1:
                    config["max_workers"] = int(newwk)
                    svcfg(config)
                    print(f"\n成功 新しい並列数: {config['max_workers']}")
                else:
                    print("\n1以上の数字を入れて")
            else:
                print("辞めた")
            input("\nEnterキーを押すと設定に戻ります...")

        elif sub == "3":
            config["never_update"] = not never_upd
            svcfg(config)
            new_str = "OFF (通知しない)" if config["never_update"] else "ON (通知する)"
            print(f"\nアプデ通知を {new_str} に変更したよ")
            time.sleep(1)

        elif sub == "4":
            break

def ldplgns():
    os.makedirs(PLUGINS_DIR, exist_ok=True)
    loaded = []
    for fn in sorted(os.listdir(PLUGINS_DIR)):
        if fn.endswith(".py") and not fn.startswith("__"):
            fp = os.path.join(PLUGINS_DIR, fn)
            mod_id = f"plg_{os.path.splitext(fn)[0]}"
            try:
                spec = importlib.util.spec_from_file_location(mod_id, fp)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                pname = getattr(mod, "PLUGIN_NAME", fn)
                pdesc = getattr(mod, "PLUGIN_DESC", "")
                pver = getattr(mod, "PLUGIN_VERSION", "")
                loaded.append({
                    "file": fn,
                    "path": fp,
                    "name": pname,
                    "desc": pdesc,
                    "ver": pver,
                    "mod": mod
                })
            except Exception:
                pass
    return loaded

def plgnbrws():
    clear()
    print("====================================")
    print("プラグインブラウザー")
    print("====================================")
    print("プラグインリスト取得ちゅう...")

    try:
        r = requests.get(f"{PLUGINS_URL}?t={int(time.time())}", headers=HEADERS, timeout=10)
        if r.status_code != 200:
            print(f"取得失敗 ステータスコード: {r.status_code}")
            input("\nEnterキーで戻ります...")
            return
        plist = r.json()
    except Exception as e:
        print(f"エラー: {e}")
        input("\nEnterキーで戻ります...")
        return

    if not isinstance(plist, list) or not plist:
        print("プラグインがみつからない")
        input("\nEnterキーで戻ります...")
        return

    installed_files = [f.lower() for f in os.listdir(PLUGINS_DIR)] if os.path.exists(PLUGINS_DIR) else []

    while True:
        clear()
        print("====================================")
        print("プラグインブラウザー (オンライン)")
        print("====================================")
        
        for idx, p in enumerate(plist, 1):
            pid = p.get("id", f"p_{idx}")
            target_fn = f"{pid}.py".lower()
            status = "[導入済]" if target_fn in installed_files else "[未導入]"
            ver_str = f" (v{p.get('version')})" if p.get("version") else ""
            print(f"{idx}. {status} {p.get('name', pid)}{ver_str}")
            if p.get("desc"):
                print(f"   └ {p.get('desc')}")

        print("------------------------------------")
        print("番号: インストール / 再インストール")
        print("u: URLから手動ダウンロード")
        print("b: 戻る")
        print("------------------------------------")
        
        c = input("選択して: ").strip()
        if c.lower() == "b" or not c:
            break
        elif c.lower() == "u":
            u_link = input("プラグインの raw URL: ").strip()
            if u_link:
                try:
                    res = requests.get(u_link, headers=HEADERS, timeout=15)
                    if res.status_code == 200:
                        fn = u_link.split("/")[-1].split("?")[0]
                        if not fn.endswith(".py"):
                            fn += ".py"
                        fn = sanitieflnm(fn)
                        out_p = os.path.join(PLUGINS_DIR, fn)
                        with open(out_p, "wb") as f:
                            f.write(res.content)
                        print(f"\nインストール成功: {fn}")
                        installed_files = [f.lower() for f in os.listdir(PLUGINS_DIR)]
                    else:
                        print(f"ダウンロード失敗 ({res.status_code})")
                except Exception as ex:
                    print(f"エラー: {ex}")
            input("\nEnterキーで続行...")
        elif c.isdigit():
            val = int(c)
            if 1 <= val <= len(plist):
                target = plist[val - 1]
                t_url = target.get("url")
                t_id = target.get("id", f"plugin_{val}")
                t_fn = f"{t_id}.py"
                if not t_url:
                    print("URLが見つからない")
                    input("\nEnterキーで続行...")
                    continue
                print(f"\n{target.get('name', t_id)} をダウンロードちゅう...")
                try:
                    res = requests.get(t_url, headers=HEADERS, timeout=15)
                    if res.status_code == 200:
                        os.makedirs(PLUGINS_DIR, exist_ok=True)
                        out_p = os.path.join(PLUGINS_DIR, t_fn)
                        with open(out_p, "wb") as f:
                            f.write(res.content)
                        print(f"インストール成功: {t_fn}")
                        installed_files = [f.lower() for f in os.listdir(PLUGINS_DIR)]
                    else:
                        print(f"ダウンロード失敗 ({res.status_code})")
                except Exception as ex:
                    print(f"エラー: {ex}")
                input("\nEnterキーで続行...")

def plgnmnu():
    global config
    while True:
        clear()
        plugins = ldplgns()
        print("====================================")
        print("プラグイン")
        print("====================================")
        if plugins:
            print("【導入済みプラグイン】")
            for idx, p in enumerate(plugins, 1):
                ver = f" (v{p['ver']})" if p['ver'] else ""
                print(f" {idx}. {p['name']}{ver}")
                if p['desc']:
                    print(f"    └ {p['desc']}")
        else:
            print("プラグインはまだありません")

        print("------------------------------------")
        print("番号: プラグインを実行")
        print("s: プラグインブラウザー (探してDL)")
        print("d: プラグインを削除")
        print("b: 戻る")
        print("------------------------------------")

        ans = input("選択して: ").strip()

        if ans.lower() == "b" or not ans:
            break
        elif ans.lower() == "s":
            plgnbrws()
        elif ans.lower() == "d":
            if not plugins:
                print("削除できるプラグインがないよ")
                time.sleep(1)
                continue
            d_idx = input(f"削除するプラグインの番号 (1-{len(plugins)} / 空欄でキャンセル): ").strip()
            if d_idx.isdigit():
                val = int(d_idx)
                if 1 <= val <= len(plugins):
                    target = plugins[val - 1]
                    try:
                        os.remove(target["path"])
                        print(f"\n{target['name']} を削除したよ")
                    except Exception as e:
                        print(f"削除失敗: {e}")
                    time.sleep(1)
        elif ans.isdigit():
            val = int(ans)
            if 1 <= val <= len(plugins):
                target = plugins[val - 1]
                mod = target["mod"]
                clear()
                ctx = {
                    "output_dir": os.path.abspath(config.get("output_dir", ".")),
                    "max_workers": config.get("max_workers", MAX_WORKERS),
                    "headers": HEADERS,
                    "clear": clear,
                    "sanitieflnm": sanitieflnm,
                    "requests": requests,
                    "base_dir": BASE_DIR
                }
                if hasattr(mod, "run"):
                    try:
                        mod.run(ctx)
                    except Exception as e:
                        print(f"\nプラグイン実行エラー: {e}")
                        input("\nEnterキーで戻ります...")
                else:
                    print("このプラグインには run(ctx) が定義されていません")
                    input("\nEnterキーで戻ります...")

def main():
    global config
    chkupd()
    
    while True:
        clear()
        print("====================================")
        print("DLしていただきありがとうございます！！！")
        print("Github Repositoryにスターお願いします()")
        print("==================================")
        print(f"v{VERSION}")
        
        output_dir = os.path.abspath(config.get("output_dir", "."))
        workers = config.get("max_workers", MAX_WORKERS)
        print(f"\n現在の保存先: {output_dir} ({workers}並列)")
        print("------------------------------------")
        print("1 音声DL")
        print("2 ユーザーの音声を全部DL")
        print("3 設定")
        print("4 プラグイン")
        print("5 exit")
        print("------------------------------------")
        
        sentaku = input("選択して (1-5): ").strip()
        
        if sentaku == "1":
            clear()
            print("音声一個DL")
            link = input("リンク (URLまたはID): ").strip()
            if link:
                cast_id = extcss(link)
                if cast_id:
                    dlsgc(cast_id, output_dir)
                else:
                    print("無効")
            input("\nEnterキーを押すとメニューに戻ります...")

        elif sentaku == "2":
            clear()
            print("ユーザーの音声を全部DL")
            print("※ 以下のどれでもいけます:")
            print("   ・URL: https://otobanana.com/general/user/xxx みたいな")
            print("   ・ハンドル名: @handle か handle そのまま")
            print("   ・ユーザーID: URLのxxxの部分\n")
            link = input("上記のどれか: ").strip()
            if link:
                usid = extusrid(link)
                if usid:
                    dlallc(usid, output_dir)
                else:
                    print("無効")
            input("\nEnterキーを押すとメニューに戻ります...")

        elif sentaku == "3":
            stgmnu()

        elif sentaku == "4":
            plgnmnu()

        elif sentaku == "5" or sentaku.lower() == "exit":
            clear()
            print("スターお忘れなく！！！()")
            sys.exit(0)

if __name__ == '__main__':
    main()
