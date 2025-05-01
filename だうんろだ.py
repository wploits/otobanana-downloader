import requests
import os
import re

def extract(link):
    baseurl1 = "https://otobanana.com/deep/cast/"
    baseurl2 = "https://otobanana.com/general/cast/"
    if link.startswith(baseurl1):
        path = link[len(baseurl1):]
        return path
    elif link.startswith(baseurl2):
        path = link[len(baseurl2):]
        return path
    else:
        return None

def sanitize(filename):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)

def fetch(cast_path):
    api_url = f"https://api.v2.otobanana.com/api/casts/{cast_path}"
    response = requests.get(api_url)

    if response.status_code == 200:
        try:
            data = response.json()
            title = data.get('post', {}).get('title', 'default_title')
            sanitized_title = sanitize(title)
            
            audio_url = data.get('audio_url', None)
            if audio_url:
                audio_response = requests.get(audio_url)
                
                if audio_response.status_code == 200:
                    file_extension = audio_url.split('.')[-1]
                    filename = f"{sanitized_title}.{file_extension}"
                    
                    with open(filename, 'wb') as file:
                        file.write(audio_response.content)
                    print(f"ほぞんせいこーw: {filename}")
                    main()
                else:
                    print("だうんろどしっぱい")
                    main()
            else:
                print("おーでぃおゆーあーるえるみつからね～！")
                main()
        except ValueError:
            print("じぇーそんじゃないよぉ、、、")
            main()
    else:
        print("りくえすとしっぱい！すてーたすこーど～:", response.status_code)
        main()

def main():
    input_link = input("りんく: ")
    cast_path = extract(input_link)

    if cast_path:
        fetch(cast_path)
    else:
        print("むこうだにょ～ん")
        main()

print("ダウンロードしていただきありがとうございます！！！")
print("Github Repositoryにスターお願いします()")
print("\nv1.0.2")
print("通常版の音声がダウンロードできないバグを修正")
print("changelog表示機能を追加。\n")
main()
