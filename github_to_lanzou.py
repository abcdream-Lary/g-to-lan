import os
import re
import sys
import time
import yaml
import shutil
import requests
import tempfile
import json
from tqdm import tqdm
from typing import Dict, List, Optional, Tuple
from config import LANZOU_CONFIG

# 终端颜色
GREEN = "\033[92m"      # 成功
RED = "\033[91m"        # 错误
BLUE = "\033[94m"       # 信息
YELLOW = "\033[93m"     # 警告
CYAN = "\033[96m"       # 提示
RESET = "\033[0m"       # 重置颜色

def read_tasks() -> List[Dict]:
    """读取YAML配置文件中的下载任务"""
    try:
        with open('download_tasks.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config.get('tasks', [])
    except Exception as e:
        print(f"{RED}✗ 读取配置文件失败: {str(e)}{RESET}")
        return []

def get_latest_release(url: str) -> Optional[List[Tuple[str, str]]]:
    """获取GitHub最新release信息
    Args:
        url: GitHub release页面URL
    Returns:
        List[Tuple[str, str]]: [(下载链接, 文件名)], 失败返回None
    """
    try:
        # 从URL中提取owner和repo
        pattern = r"github\.com/([^/]+)/([^/]+)"
        match = re.search(pattern, url)
        if not match:
            print(f"{RED}✗ 无效的GitHub URL{RESET}")
            return None
            
        owner, repo = match.groups()
        
        # 获取最新release信息
        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        response = requests.get(api_url)
        
        if response.status_code != 200:
            print(f"{RED}✗ 获取release信息失败: HTTP {response.status_code}{RESET}")
            return None
            
        release_data = response.json()
        assets = release_data.get('assets', [])
        
        if not assets:
            print(f"{RED}✗ 没有找到可下载的文件{RESET}")
            return None
            
        # 获取所有符合条件的资源文件
        download_files = []
        for asset in assets:
            file_name = asset.get('name', '').lower()
            # 排除源代码zip文件（通常包含 'source' 或 'src' 字样）
            if ('source' in file_name or 'src' in file_name):
                continue
            # 只下载apk、exe和zip文件
            if file_name.endswith(('.apk', '.exe', '.zip')):
                download_url = asset.get('browser_download_url')
                if download_url:
                    download_files.append((download_url, asset.get('name')))
        
        if not download_files:
            print(f"{RED}✗ 没有找到符合条件的文件{RESET}")
            return None
            
        return download_files
        
    except Exception as e:
        print(f"{RED}✗ 获取release信息失败: {str(e)}{RESET}")
        return None

def download_file(url: str, save_path: str) -> bool:
    """下载文件并显示进度
    Args:
        url: 下载链接
        save_path: 保存路径
    Returns:
        bool: 是否下载成功
    """
    try:
        # 发送HEAD请求获取文件大小
        response = requests.head(url)
        total_size = int(response.headers.get('content-length', 0))
        
        # 创建进度条
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(save_path, 'wb') as f:
                with tqdm(
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    desc="下载进度",
                    ncols=100
                ) as pbar:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
                            
        return True
        
    except Exception as e:
        print(f"{RED}✗ 下载文件失败: {str(e)}{RESET}")
        if os.path.exists(save_path):
            os.remove(save_path)
        return False

class FileInfo:
    def __init__(self, data: Dict):
        self.name = data.get('name', '')  # 文件名
        self.name_all = data.get('name_all', '')  # 完整文件名
        self.size = data.get('size', '0')  # 文件大小
        self.time = data.get('time', '')  # 上传时间
        self.id = data.get('id', '')  # 文件ID
        self.folder_id = data.get('folder_id', '0')  # 所在文件夹ID
        self.is_dir = False
        
    def __str__(self):
        return f"{self.name_all or self.name} ({self.size})"

class FolderInfo:
    def __init__(self, data: Dict):
        self.name = data.get('name', '')  # 文件夹名
        # 优先使用fol_id,如果没有则使用folder_id
        self.folder_id = data.get('fol_id', '') or data.get('folder_id', '')  # 文件夹ID
        self.size = data.get('size', '0')  # 文件夹大小
        self.time = data.get('time', '')  # 创建时间
        self.description = data.get('folder_des', '')  # 文件夹描述
        self.is_dir = True
        
    def __str__(self):
        return f"[目录] {self.name} (ID: {self.folder_id})"

class LanZouSession:
    def __init__(self, cookie_path: str):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.39 (KHTML, like Gecko) Chrome/89.0.4389.111 Safari/537.39'
        })
        self.base_url = 'https://up.woozooo.com'
        self.login_url = 'https://up.woozooo.com/mlogin.php'
        self.mydisk_url = 'https://up.woozooo.com/mydisk.php'
        self.cookie_file = cookie_path  # 使用传入的临时目录路径
        self.is_login = False
        self.user_info = {
            'uid': LANZOU_CONFIG.get('uid', '')
        }
        
    def _post(self, url: str, data: Dict = None, files: Dict = None, **kwargs) -> Dict:
        """发送POST请求并处理响应"""
        try:
            # 在URL中添加uid参数
            if '?' in url:
                url = f"{url}&uid={self.user_info['uid']}"
            else:
                url = f"{url}?uid={self.user_info['uid']}"
                
            response = self.session.post(url, data=data, files=files, **kwargs)
            if response.status_code != 200:
                raise Exception(f"请求失败: HTTP {response.status_code}")
                
            result = response.json()
            # 如果是获取文件夹列表的请求,特殊处理
            if data and data.get("task") == "47":
                return result
                
            if result.get('zt') != 1:
                raise Exception(result.get('info', '未知错误'))
                
            return result
        except Exception as e:
            raise Exception(f"请求出错: {str(e)}")
            
    def save_cookies(self):
        """保存cookie到文件"""
        cookie_dict = requests.utils.dict_from_cookiejar(self.session.cookies)
        with open(self.cookie_file, 'w') as f:
            json.dump(cookie_dict, f)
            
    def load_cookies(self) -> bool:
        """从文件加载cookie"""
        try:
            if os.path.exists(self.cookie_file):
                print("发现已保存的登录状态...")
                with open(self.cookie_file, 'r') as f:
                    cookie_dict = json.load(f)
                    self.session.cookies = requests.utils.cookiejar_from_dict(cookie_dict)
                print("正在验证登录状态...")
                if self.check_login():
                    print(f"{GREEN}✓ 使用已保存的登录状态{RESET}")
                    return True
                else:
                    print(f"{YELLOW}! 登录状态已失效{RESET}")
                    return False
        except Exception as e:
            print(f"{YELLOW}! 加载登录状态失败: {str(e)}{RESET}")
        return False
        
    def check_login(self) -> bool:
        """检查cookie是否有效"""
        try:
            print("正在验证登录状态...")
            response = self.session.get(self.mydisk_url)
            if "登录" not in response.text:
                self.is_login = True
                return True
        except Exception as e:
            print(f"验证登录状态失败: {str(e)}")
        return False
        
    def login(self) -> bool:
        """登录蓝奏云"""
        # 先尝试加载已保存的cookie
        if self.load_cookies():
            return True
            
        username = LANZOU_CONFIG.get("username")
        password = LANZOU_CONFIG.get("password")
        
        if not username or not password:
            print(f"{RED}✗ 请在config.py中配置账号密码{RESET}")
            return False
            
        try:
            print("\n正在登录蓝奏云...")
            print(f"账号: {username}")
            print("密码: ********")
            
            # 发送登录请求
            data = {
                "task": "3",
                "uid": username,
                "pwd": password,
                "setSessionId": "",
                "setSig": "",
                "setScene": "",
                "setTocen": "",
                "formhash": "",
            }
            
            headers = {
                'Accept': 'application/json, text/javascript, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://up.woozooo.com',
                'Referer': 'https://up.woozooo.com/',
                'User-Agent': self.session.headers['User-Agent']
            }
            
            # 发送登录请求
            response = self.session.post(
                self.login_url,
                data=data,
                headers=headers,
                allow_redirects=False
            )
            
            if response.status_code != 200:
                print(f"{RED}✗ 登录请求失败{RESET}")
                return False
                
            try:
                result = response.json()
                if result.get('zt') == 1:
                    print(f"{GREEN}✓ 登录成功!{RESET}")
                    self.save_cookies()
                    self.is_login = True
                    return True
                else:
                    print(f"{RED}✗ 登录失败: {result.get('info', '未知错误')}{RESET}")
                    return False
            except:
                if self.check_login():
                    print(f"{GREEN}✓ 登录成功!{RESET}")
                    self.save_cookies()
                    return True
                print(f"{RED}✗ 登录失败，无法解析响应{RESET}")
                return False
                
        except Exception as e:
            print(f"{RED}✗ 登录过程出错: {str(e)}{RESET}")
            return False
            
    def get_folders(self, parent_id: str = "-1") -> List[FolderInfo]:
        """获取文件夹列表
        Args:
            parent_id: 父文件夹ID，默认根目录
        Returns:
            List[FolderInfo]: 文件夹列表
        """
        try:
            result = self._post(
                f"{self.base_url}/doupload.php",
                data={
                    "task": "47",
                    "folder_id": parent_id
                }
            )
            
            folders = []
            text = result.get('text', [])
            # 如果text是列表,说明有子文件夹
            if isinstance(text, list):
                for item in text:
                    # 修正文件夹ID字段
                    if 'folderid' in item:
                        item['folder_id'] = item['folderid']
                    folders.append(FolderInfo(item))
                    
            return folders
            
        except Exception as e:
            print(f"{RED}✗ 获取文件夹列表失败: {str(e)}{RESET}")
            return []
            
    def get_files(self, folder_id: str) -> List[FileInfo]:
        """获取文件列表
        Args:
            folder_id: 文件夹ID
        Returns:
            List[FileInfo]: 文件列表
        """
        try:
            files = []
            page = 1
            
            while True:
                result = self._post(
                    f"{self.base_url}/doupload.php",
                    data={
                        "task": "5",
                        "folder_id": folder_id,
                        "pg": str(page)
                    }
                )
                
                text = result.get('text', [])
                if not isinstance(text, list) or text == "" or not text:
                    break
                    
                for item in text:
                    files.append(FileInfo(item))
                
                # 检查是否有更多页
                if len(text) < 50:  # 通常每页50条记录
                    break
                    
                page += 1
                time.sleep(0.5)  # 添加延时，避免请求过快
                
            return files
            
        except Exception as e:
            print(f"{RED}✗ 获取文件列表失败: {str(e)}{RESET}")
            return []
            
    def get_folder_id(self, folder_name: str) -> Optional[str]:
        """获取文件夹ID
        Args:
            folder_name: 文件夹名称
        Returns:
            str: 文件夹ID, 不存在返回None
        """
        folders = self.get_folders()
        for folder in folders:
            if folder.name == folder_name:
                return folder.folder_id
        return None
        
    def file_exists(self, folder_id: str, file_name: str) -> bool:
        """检查文件是否已存在
        Args:
            folder_id: 文件夹ID
            file_name: 文件名
        Returns:
            bool: 是否存在
        """
        files = self.get_files(folder_id)
        return any(f.name == file_name or f.name_all == file_name for f in files)
        
    def create_folder_path(self, folder_path: str) -> Optional[str]:
        """创建多层文件夹路径
        Args:
            folder_path: 文件夹路径，使用/分隔，如 "folder1/folder2/folder3"
        Returns:
            str: 最后一层文件夹的ID，失败返回None
        """
        if not self.is_login:
            print(f"{RED}✗ 请先登录{RESET}")
            return None

        try:
            folders = folder_path.strip('/').split('/')
            current_parent_id = "-1"  # 从根目录开始

            for folder_name in folders:
                # 检查当前层级是否已存在该文件夹
                folder_id = None
                current_folders = self.get_folders(current_parent_id)
                for folder in current_folders:
                    if folder.name == folder_name:
                        folder_id = folder.folder_id
                        break

                if folder_id:
                    print(f"{YELLOW}! 文件夹已存在: {folder_name}{RESET}")
                    current_parent_id = folder_id
                    continue

                print(f"\n[创建文件夹]")
                print(f"文件夹名称: {folder_name}")
                print(f"父文件夹ID: {current_parent_id}")

                result = self._post(
                    f"{self.base_url}/doupload.php",
                    data={
                        "task": "2",
                        "parent_id": current_parent_id,
                        "folder_name": folder_name,
                        "folder_description": ""
                    }
                )

                folder_id = result.get('text')
                if not folder_id:
                    print(f"{RED}✗ 创建失败，无法获取文件夹ID{RESET}")
                    return None

                print(f"{GREEN}✓ 创建成功，文件夹ID: {folder_id}{RESET}")
                current_parent_id = folder_id

            return current_parent_id

        except Exception as e:
            print(f"{RED}✗ 创建文件夹路径失败: {str(e)}{RESET}")
            return None

    def create_folder(self, folder_name: str) -> Optional[str]:
        """在蓝奏云创建文件夹，支持根目录和多层路径
        Args:
            folder_name: 文件夹名称，支持多层路径，如 "folder1/folder2/folder3"
        Returns:
            str: 文件夹ID，失败返回None
        """
        if not self.is_login:
            print(f"{RED}✗ 请先登录{RESET}")
            return None

        try:
            # 检查是否是多层路径
            if '/' in folder_name:
                return self.create_folder_path(folder_name)
            
            # 单层目录的处理
            # 先检查文件夹是否已存在
            folder_id = self.get_folder_id(folder_name)
            if folder_id:
                print(f"{YELLOW}! 文件夹已存在: {folder_name}{RESET}")
                return folder_id

            print(f"\n[创建文件夹]")
            print(f"文件夹名称: {folder_name}")

            result = self._post(
                f"{self.base_url}/doupload.php",
                data={
                    "task": "2",
                    "parent_id": "-1",  # 创建在根目录下
                    "folder_name": folder_name,
                    "folder_description": ""
                }
            )

            folder_id = result.get('text')
            if folder_id:
                print(f"{GREEN}✓ 创建成功，文件夹ID: {folder_id}{RESET}")
                return folder_id

            print(f"{RED}✗ 创建失败，无法获取文件夹ID{RESET}")
            return None

        except Exception as e:
            print(f"{RED}✗ 创建文件夹失败: {str(e)}{RESET}")
            return None

    def upload_file(self, file_path: str, folder_id: str) -> bool:
        """上传文件到蓝奏云"""
        if not self.is_login:
            print(f"{RED}✗ 请先登录{RESET}")
            return False
            
        try:
            file_name = os.path.basename(file_path)
            print(f"文件名称: {file_name}")
            print(f"文件大小: {os.path.getsize(file_path) / 1024 / 1024:.2f}MB")
            
            # 检查文件是否已存在
            if self.file_exists(folder_id, file_name):
                print(f"{YELLOW}! 文件已存在，跳过上传: {file_name}{RESET}")
                return True
                
            # 上传文件
            file_size = os.path.getsize(file_path)
            with open(file_path, "rb") as f:
                with tqdm(total=file_size, unit='B', unit_scale=True, desc="上传进度", ncols=100) as pbar:
                    files = {
                        "upload_file": (file_name, f, "application/octet-stream")
                    }
                    data = {
                        "task": "1",
                        "vie": "2",
                        "ve": "2",
                        "id": "WU_FILE_0",
                        "name": file_name,
                        "folder_id_bb_n": folder_id
                    }
                    response = self.session.post(
                        f"{self.base_url}/html5up.php",
                        files=files,
                        data=data
                    )
                    pbar.update(file_size)
                    
            if response.status_code != 200:
                print(f"{RED}✗ 上传失败: HTTP {response.status_code}{RESET}")
                return False
                
            # 解析响应
            try:
                result = response.json()
                if result.get("zt") == 1:
                    print(f"{GREEN}✓ 文件上传成功{RESET}")
                    return True
                    
                print(f"{RED}✗ 上传失败: {result.get('info', '未知错误')}{RESET}")
                return False
                
            except Exception as e:
                print(f"{RED}✗ 解析响应失败: {str(e)}{RESET}")
                return False
                
        except Exception as e:
            print(f"{RED}✗ 上传过程出错: {str(e)}{RESET}")
            return False

def check_file_size(file_path: str) -> bool:
    """检查文件大小是否超过限制(100MB)"""
    try:
        size = os.path.getsize(file_path)
        size_mb = size / (1024 * 1024)
        if size_mb > 100:
            print(f"{RED}✗ 文件大小 {size_mb:.2f}MB 超过限制(100MB){RESET}")
            return False
        return True
    except Exception as e:
        print(f"{RED}✗ 检查文件大小失败: {str(e)}{RESET}")
        return False

def main():
    """主函数"""
    print(f"\n{BLUE}=== GitHub Release 自动下载上传工具 ==={RESET}")
    
    # 读取任务配置
    tasks = read_tasks()
    if not tasks:
        print(f"{RED}✗ 没有找到任务配置{RESET}")
        return
        
    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建蓝奏云会话并登录
        cookie_path = os.path.join(temp_dir, 'cookie.json')
        lanzou = LanZouSession(cookie_path)
        if not lanzou.login():
            return
            
        # 遍历处理每个任务
        for task in tasks:
            url = task.get('url')
            folder_name = task.get('folder_name')
            
            if not url or not folder_name:
                print(f"{YELLOW}! 跳过无效任务配置{RESET}")
                continue
                
            print(f"\n{BLUE}=== 处理任务 ==={RESET}")
            print(f"GitHub URL: {url}")
            print(f"目标文件夹: {folder_name}")
            
            try:
                # 获取最新release信息
                release_files = get_latest_release(url)
                if not release_files:
                    print(f"{RED}✗ 获取release信息失败{RESET}")
                    continue
                
                # 创建文件夹
                print(f"\n{BLUE}[1/3] 创建目标文件夹{RESET}")
                folder_id = lanzou.create_folder(folder_name)
                if not folder_id:
                    continue
                
                # 下载并上传每个文件
                for index, (download_url, file_name) in enumerate(release_files, 1):
                    print(f"\n{BLUE}[2/3] 下载文件 ({index}/{len(release_files)}){RESET}")
                    save_path = os.path.join(temp_dir, file_name)
                    
                    # 下载文件
                    if not download_file(download_url, save_path):
                        continue
                        
                    # 检查文件大小
                    if not check_file_size(save_path):
                        continue
                        
                    # 上传文件
                    print(f"\n{BLUE}[3/3] 上传文件 ({index}/{len(release_files)}){RESET}")
                    if not lanzou.upload_file(save_path, folder_id):
                        continue
                    
                print(f"\n{GREEN}✓ 任务完成{RESET}")
                
            except Exception as e:
                print(f"{RED}✗ 处理任务失败: {str(e)}{RESET}")
                continue
                
    print(f"\n{GREEN}=== 所有任务处理完成 ==={RESET}")
        
if __name__ == "__main__":
    main() 