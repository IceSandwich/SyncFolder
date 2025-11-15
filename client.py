import os
import hashlib
import requests
import time

# --- A 电脑配置 ---
SOURCE_DIR = R"D:\电子书"
B_COMPUTER_IP = "192.168.31.102"  # <--- !!! 必须修改这里
SERVER_URL = f"http://{B_COMPUTER_IP}:7860"
# --------------------

def get_md5(filepath):
    """计算大文件的MD5值"""
    hash_md5 = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        print(f"  !! 无法计算MD5 {filepath}: {e}")
        return None

def upload_file(source_file_path, relative_path):
    """上传单个文件到 B 电脑服务器 (此部分无需更改)"""
    upload_url = f"{SERVER_URL}/upload"
    try:
        with open(source_file_path, 'rb') as f:
            files = {'file': (os.path.basename(source_file_path), f)}
            data = {'relative_path': relative_path}
            response = requests.post(upload_url, files=files, data=data, timeout=30)
            response.raise_for_status()
            return response.json().get("success")
    except requests.exceptions.RequestException as e:
        print(f"  !! 上传请求失败: {e}")
        return False

def sync_folders(source_dir):
    """
    扫描 A 电脑的 source_dir，并与 B 电脑的服务器进行同步
    """
    print(f"--- 开始同步 (已优化) ---")
    print(f"源 (A电脑): {source_dir}")
    print(f"目标 (B电脑服务器): {SERVER_URL}")
    print("-" * 20)
    
    start_time = time.time()
    files_synced = 0
    files_skipped = 0
    errors = 0

    check_url = f"{SERVER_URL}/check"

    for root, dirs, files in os.walk(source_dir):
        for file in files:
            source_file_path = os.path.join(root, file)
            relative_path = os.path.relpath(source_file_path, source_dir).replace("\\", "/")
            
            print(f"检查: {relative_path}")

            try:
                # 优化点: 获取源文件大小
                source_size = os.path.getsize(source_file_path)

                # 规则 1 & 2: 询问B电脑服务器 (带上 size)
                params = {'relative_path': relative_path, 'size': source_size}
                response = requests.get(check_url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

                if data.get("error"):
                    print(f"  !! 服务器检查失败: {data['error']}")
                    errors += 1
                    continue

                # 规则 2: B电脑没有此文件
                if not data.get("exists"):
                    print(f"  -> 上传 (新文件): {relative_path}")
                    if upload_file(source_file_path, relative_path):
                        files_synced += 1
                    else:
                        errors += 1
                    continue
                
                # 规则 1: B电脑有此文件
                
                # 优化点: 检查 B 电脑返回的 size_match 字段
                if not data.get("size_match"):
                    # 大小不匹配，B电脑未计算MD5，直接上传
                    print(f"  -> 更新 (大小不匹配): {relative_path}")
                    # if upload_file(source_file_path, relative_path):
                    #     files_synced += 1
                    # else:
                    #     errors += 1
                    continue

                # 大小匹配 (size_match: True)，B电脑返回了MD5
                # A 电脑现在才需要计算自己的 MD5
                source_md5 = get_md5(source_file_path)
                dest_md5 = data.get("md5")

                if not source_md5:
                    print(f"  !! 无法读取源文件MD5，跳过")
                    errors += 1
                    continue
                
                if not dest_md5:
                    print(f"  !! B电脑无法读取目标MD5 (大小相同)，强制上传")
                    # if upload_file(source_file_path, relative_path):
                    #     files_synced += 1
                    # else:
                    #     errors += 1
                    continue

                if source_md5 != dest_md5:
                    print(f"  -> 更新 (MD5不匹配): {relative_path}")
                    # if upload_file(source_file_path, relative_path):
                    #     files_synced += 1
                    # else:
                    #     errors += 1
                else:
                    # print(f"  -> 跳过 (MD5/大小均匹配)")
                    files_skipped += 1
            
            except os.error as e:
                print(f"!! 错误: 无法读取源文件 {source_file_path}: {e}")
                errors += 1
            except requests.exceptions.ConnectionError:
                print(f"!! 错误: 无法连接到 {SERVER_URL}。")
                print("请确保 B 电脑的服务器脚本正在运行，并且IP地址正确。")
                return
            except requests.exceptions.RequestException as e:
                print(f"!! 严重错误: {e}")
                errors += 1

    end_time = time.time()
    print("-" * 20)
    print("--- 同步完成 ---")
    print(f"总耗时: {end_time - start_time:.2f} 秒")
    print(f"已同步/更新文件: {files_synced}")
    print(f"已跳过文件: {files_skipped}")
    print(f"错误: {errors}")

# --- 主程序入口 ---
if __name__ == "__main__":
    if B_COMPUTER_IP == "192.168.x.x":
        print("错误：请先在 A_client.py 脚本中修改 'B_COMPUTER_IP' 变量！")
    else:
        sync_folders(SOURCE_DIR)