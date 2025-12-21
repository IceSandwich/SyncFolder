import os
import hashlib
import requests
import time
import argparse

class Args:
    local_dir: str
    server_ip: str
    server_port: int

def setup_parser() -> Args:
    parser = argparse.ArgumentParser(description="同步文件夹到服务器")
    parser.add_argument("-l", "--local_dir", type=str, required=True, help="本地文件夹路径")
    parser.add_argument("-s", "--server_ip", type=str, required=True, help="服务器IP地址")
    parser.add_argument("-p", "--server_port", type=int, default=7860, help="服务器端口 (默认为 7860)")
    args = parser.parse_args()
    return args

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

class ServerAPI:
    def __init__(self, server_ip: str, server_port: int):
        self.server_url = f"http://{server_ip}:{server_port}"

    def check(self, relative_path: str, size: int) -> bool:
        """检查服务器上是否存在指定的文件"""
        url = f"{self.server_url}/check"
        params = {'relative_path': relative_path, 'size': size}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    
    def upload(self, filepath: str, relative_path: str) -> bool:
        """上传文件到 B 电脑服务器"""
        upload_url = f"{self.server_url}/upload"
        with open(filepath, "rb") as f:
            files = {'file': (os.path.basename(filepath), f)}
            data = {'relative_path': relative_path}
            response = requests.post(upload_url, files=files, data=data, timeout=30)
            response.raise_for_status()
            return response.json().get("success")
        return False

def sync_folders(args: Args):
    """
    扫描 A 电脑的 source_dir，并与 B 电脑的服务器进行同步
    """
    server = ServerAPI(args.server_ip, args.server_port)

    print(f"--- 开始同步 (已优化) ---")
    print(f"源 (A电脑): {args.local_dir}")
    print(f"目标 (B电脑服务器): {args.server_ip}:{args.server_port}")
    print("-" * 20)
    
    start_time = time.time()
    files_synced = 0
    files_skipped = 0
    errors = 0
    source_dir = args.local_dir

    with open("run.log", "w", encoding='utf-8') as log:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                source_file_path = os.path.join(root, file)
                relative_path = os.path.relpath(source_file_path, source_dir).replace("\\", "/")
                
                print(f"检查: {relative_path}")
                try:
                    # 优化点: 获取源文件大小
                    source_size = os.path.getsize(source_file_path)

                    # 规则 1 & 2: 询问B电脑服务器 (带上 size)
                    data = server.check(relative_path, source_size)

                    if data.get("error"):
                        print(f"  !! 服务器检查失败: {data['error']}")
                        log.write(f"[server error] {relative_path} {data['error']}\n")
                        errors += 1
                        continue

                    # 规则 2: B电脑没有此文件
                    if not data.get("exists"):
                        print(f"  ✔ 上传 (新文件): {relative_path}")
                        if server.upload(source_file_path, relative_path):
                            files_synced += 1
                        else:
                            errors += 1
                        continue
                    
                    # 规则 1: B电脑有此文件
                    
                    # 优化点: 检查 B 电脑返回的 size_match 字段
                    if not data.get("size_match"):
                        # 大小不匹配，B电脑未计算MD5，直接上传
                        print(f"  ⭕ 跳过更新 (大小不匹配): {relative_path}")
                        log.write(f"[Size Notmatch] {relative_path}\n")
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
                        print(f"  ⭕ 无法读取源文件MD5，跳过")
                        log.write(f"[Can't calc local md5] {relative_path}\n")
                        errors += 1
                        continue
                    
                    if not dest_md5:
                        print(f"  ⭕ B电脑无法读取目标MD5 (大小相同)，跳过上传")
                        log.write(f"[Can't calc remote md5] {relative_path}\n")
                        # if upload_file(source_file_path, relative_path):
                        #     files_synced += 1
                        # else:
                        #     errors += 1
                        continue

                    if source_md5 != dest_md5:
                        print(f"  ⭕ 跳过更新 (MD5不匹配): {relative_path}")
                        log.write(f"[md5 notmatch] {relative_path}\n")
                        # if upload_file(source_file_path, relative_path):
                        #     files_synced += 1
                        # else:
                        #     errors += 1
                    else:
                        # print(f"  -> 跳过 (MD5/大小均匹配)")
                        files_skipped += 1
                
                except os.error as e:
                    print(f"!! 错误: 无法读取源文件 {source_file_path}: {e}")
                    log.write(f"[Can't read local file] {relative_path}\n")
                    errors += 1
                except requests.exceptions.ConnectionError:
                    print(f"!! 错误: 无法连接到 {server_url}。")
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
    args = setup_parser()
    sync_folders(args)