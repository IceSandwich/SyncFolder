import os
import hashlib
from flask import Flask, request, jsonify
import argparse

class Args:
    port: int
    base_dir: str

def setup_parser() -> Args:
    parser = argparse.ArgumentParser(description="SyncFolder")
    parser.add_argument("--port", type=int, default=7860, help="服务器端口，注意防火墙放行")
    parser.add_argument("--base_dir", type=str, required=True, help="目标目录")
    return parser.parse_args()

app = Flask(__name__)

def get_md5(filepath):
    """计算文件的MD5值"""
    hash_md5 = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return None

def secure_path(relative_path):
    """防止路径遍历攻击"""
    clean_path = os.path.normpath(relative_path)
    if os.path.isabs(clean_path) or clean_path.startswith(".."):
        return None
    full_path = os.path.join(BASE_DIR, clean_path)
    if os.path.commonprefix([os.path.abspath(full_path), BASE_DIR]) == BASE_DIR:
        return full_path
    return None

@app.route('/check', methods=['GET'])
def check_file():
    """
    检查文件是否存在、大小及MD5
    接收 ?relative_path=...&size=...
    """
    relative_path = request.args.get('relative_path')
    # 从 A 电脑获取文件大小
    remote_size = request.args.get('size', type=int)

    if not relative_path:
        return jsonify({"error": "缺少 relative_path"}), 400
    if remote_size is None:
        return jsonify({"error": "缺少 size 参数"}), 400

    full_path = secure_path(relative_path)
    if not full_path:
        return jsonify({"error": "无效的路径"}), 400

    if not os.path.exists(full_path):
        # 规则 2: B电脑没有这个文件
        return jsonify({"exists": False})

    try:
        # B电脑上的文件存在
        # 1. 获取 B 电脑本地的文件大小
        local_size = os.path.getsize(full_path)

        # 2. 优化点：比较大小
        if local_size != remote_size:
            # 大小不匹配，立即返回，不计算MD5
            return jsonify({"exists": True, "size_match": False})

        # 3. 大小匹配，才计算MD5
        print(f"Info: 大小匹配 {relative_path}，正在计算 MD5...")
        md5_val = get_md5(full_path)

        if md5_val:
            return jsonify({"exists": True, "size_match": True, "md5": md5_val})
        else:
            # 文件存在，大小也匹配，但MD5计算失败
            return jsonify({"exists": True, "size_match": True, "md5": None, "error": "无法计算MD5"})
            
    except Exception as e:
        return jsonify({"error": f"检查文件时出错: {e}"}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    """
    接收文件上传 (此部分无需更改)
    """
    relative_path = request.form.get('relative_path')
    file = request.files.get('file')

    if not relative_path or not file:
        return jsonify({"error": "缺少 relative_path 或文件"}), 400

    full_path = secure_path(relative_path)
    if not full_path:
        return jsonify({"error": "无效的路径"}), 400

    try:
        dest_dir = os.path.dirname(full_path)
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
        file.save(full_path)
        return jsonify({"success": True, "message": f"文件 {relative_path} 已保存"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

def get_local_ip():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    local_ip = s.getsockname()[0]
    s.close()
    return local_ip

if __name__ == "__main__":
    args = setup_parser()
    local_ip = get_local_ip()
    print(f"--- 目标电脑服务器 ---")
    print(f"目标目录: {args.base_dir}")
    if not os.path.exists(args.base_dir):
        print("目标电脑上不存在指定目录，请检查！")
    else:
        print(f"正在启动服务器，监听 {local_ip}:{args.port} ...")
        app.run(host='0.0.0.0', port=args.port)