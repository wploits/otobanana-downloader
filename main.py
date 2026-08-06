import os
import re
import sys
import time
import json
import threading
import subprocess
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
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                if "output_dir" in config and config["output_dir"]:
                    return config
        except Exception:
            pass
    return {"output_dir": "."}

def svcfg(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"セーブ失敗した {e}")

config = ldcfg()

def sanitieflnm(filename):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename).strip()

def extcss(link):
    link = link.strip()
    match = re.search(r'/cast/([^/?#]+)', link)
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
                title = data.get('post', {}).get('title', 'default_title')
                sanitized_title = sanitieflnm(title)
                
                audurl = data.get('audurl', None)
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

    total_tasks = len(target_items)
    print(f"\n{total_tasks} 件開始 ({MAX_WORKERS}並列)\n")

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

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(download_worker, item, idx) for idx, item in enumerate(target_items, 1)]
        for future in futures:
            future.result()

    print(f"\n全部終わった (成功: {success_count}件 / スキップ: {skip_count}件 / 合計: {total_tasks}件)")
    print("Github Repositoryにスターお願いします()")

def main():
    global config
    
    while True:
        clear()
        print("====================================")
        print("DLしていただきありがとうございます！！！")
        print("Github Repositoryにスターお願いします()")
        print("==================================")
        print("v2")
        
        output_dir = os.path.abspath(config.get("output_dir", "."))
        print(f"\n現在の保存先: {output_dir}")
        print("------------------------------------")
        print("1 音声DL")
        print("2 ユーザーの音声を全部DL")
        print("3 出力先フォルダー変更(選択)")
        print("4 exit")
        print("------------------------------------")
        
        sentaku = input("選択して (1-4): ").strip()
        
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
                    print(f"\設定失敗: {e}")
                    
            input("\nEnterキーを押すとメニューに戻ります...")

        elif sentaku == "4" or sentaku.lower() == "exit":
            clear()
            print("スターお忘れなく！！！()")
            sys.exit(0)

if __name__ == '__main__':
    main()
