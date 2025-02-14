import os
import re
import sys
import yaml
import json
import requests
import subprocess
from typing import Dict, List, Optional, Tuple
from config import LANZOU_CONFIG

# 终端颜色
GREEN = "\033[92m"      # 成功
RED = "\033[91m"        # 错误
BLUE = "\033[94m"       # 信息
YELLOW = "\033[93m"     # 警告
CYAN = "\033[96m"       # 提示
RESET = "\033[0m"       # 重置颜色

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
        self.folder_id = data.get('fol_id', '') or data.get('folder_id', '')  # 文件夹ID
        self.size = data.get('size', '0')  # 文件夹大小
        self.time = data.get('time', '')  # 创建时间
        self.description = data.get('folder_des', '')  # 文件夹描述
        self.is_dir = True
        
    def __str__(self):
        return f"[目录] {self.name} (ID: {self.folder_id})"

class LanZouSession:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.39 (KHTML, like Gecko) Chrome/89.0.4389.111 Safari/537.39'
        })
        self.base_url = 'https://up.woozooo.com'
        self.login_url = 'https://up.woozooo.com/mlogin.php'
        self.mydisk_url = 'https://up.woozooo.com/mydisk.php'
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
                    self.is_login = True
                    return True
                else:
                    print(f"{RED}✗ 登录失败: {result.get('info', '未知错误')}{RESET}")
                    return False
            except:
                if self.check_login():
                    print(f"{GREEN}✓ 登录成功!{RESET}")
                    return True
                print(f"{RED}✗ 登录失败，无法解析响应{RESET}")
                return False
                
        except Exception as e:
            print(f"{RED}✗ 登录过程出错: {str(e)}{RESET}")
            return False
            
    def get_folders(self, parent_id: str = "-1") -> List[FolderInfo]:
        """获取文件夹列表"""
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
            if isinstance(text, list):
                for item in text:
                    if 'folderid' in item:
                        item['folder_id'] = item['folderid']
                    folders.append(FolderInfo(item))
                    
            return folders
            
        except Exception as e:
            print(f"{RED}✗ 获取文件夹列表失败: {str(e)}{RESET}")
            return []
            
    def get_files(self, folder_id: str) -> List[FileInfo]:
        """获取文件列表"""
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
                
                if len(text) < 50:
                    break
                    
                page += 1
                
            return files
            
        except Exception as e:
            print(f"{RED}✗ 获取文件列表失败: {str(e)}{RESET}")
            return []
            
    def get_folder_id(self, folder_name: str) -> Optional[str]:
        """获取文件夹ID"""
        folders = self.get_folders()
        for folder in folders:
            if folder.name == folder_name:
                return folder.folder_id
        return None
        
    def file_exists(self, folder_id: str, file_name: str) -> bool:
        """检查文件是否已存在"""
        files = self.get_files(folder_id)
        return any(f.name == file_name or f.name_all == file_name for f in files)

def read_tasks() -> List[Dict]:
    """读取YAML配置文件中的下载任务"""
    try:
        with open('download_tasks.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config.get('tasks', [])
    except Exception as e:
        print(f"{RED}✗ 读取配置文件失败: {str(e)}{RESET}")
        return []

def get_latest_release_info(url: str) -> Optional[Tuple[str, str, str]]:
    """获取GitHub最新release信息
    Args:
        url: GitHub release页面URL
    Returns:
        Tuple[str, str, str]: (版本号, 下载链接, 文件名), 失败返回None
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
        version = release_data.get('tag_name')
        assets = release_data.get('assets', [])
        
        if not assets:
            print(f"{RED}✗ 没有找到可下载的文件{RESET}")
            return None
            
        # 获取第一个资源文件
        asset = assets[0]
        download_url = asset.get('browser_download_url')
        file_name = asset.get('name')
        
        if not download_url or not file_name or not version:
            print(f"{RED}✗ 无法获取下载信息{RESET}")
            return None
            
        return version, download_url, file_name
        
    except Exception as e:
        print(f"{RED}✗ 获取release信息失败: {str(e)}{RESET}")
        return None

def check_file_exists(lanzou: LanZouSession, folder_name: str, file_name: str) -> bool:
    """检查文件是否已存在于蓝奏云文件夹中"""
    try:
        # 获取文件夹ID
        folder_id = lanzou.get_folder_id(folder_name)
        if not folder_id:
            return False
            
        # 检查文件是否存在
        return lanzou.file_exists(folder_id, file_name)
        
    except Exception as e:
        print(f"{RED}✗ 检查文件失败: {str(e)}{RESET}")
        return False

def main():
    """主函数"""
    print(f"\n{BLUE}=== GitHub Release 更新检查工具 ==={RESET}")
    
    # 读取任务配置
    tasks = read_tasks()
    if not tasks:
        print(f"{RED}✗ 没有找到任务配置{RESET}")
        return
        
    # 创建蓝奏云会话
    lanzou = LanZouSession()
    if not lanzou.login():
        print(f"{RED}✗ 蓝奏云登录失败{RESET}")
        return
        
    need_update = False
    
    # 检查每个任务的更新
    for task in tasks:
        url = task.get('url')
        folder_name = task.get('folder_name')
        
        if not url or not folder_name:
            print(f"{YELLOW}! 跳过无效任务配置{RESET}")
            continue
            
        print(f"\n{BLUE}=== 检查更新 ==={RESET}")
        print(f"项目: {folder_name}")
        print(f"GitHub URL: {url}")
        
        # 获取最新版本信息
        release_info = get_latest_release_info(url)
        if not release_info:
            continue
            
        version, download_url, file_name = release_info
        print(f"最新版本: {version}")
        print(f"文件名称: {file_name}")
        
        # 检查文件是否已存在
        if check_file_exists(lanzou, folder_name, file_name):
            print(f"{BLUE}✓ 已是最新版本{RESET}")
        else:
            print(f"{GREEN}✓ 发现新版本{RESET}")
            need_update = True
            
    # 如果有更新，运行下载上传脚本
    if need_update:
        print(f"\n{GREEN}=== 发现更新，开始下载上传 ==={RESET}")
        try:
            subprocess.run([sys.executable, 'github_to_lanzou.py'], check=True)
        except subprocess.CalledProcessError as e:
            print(f"{RED}✗ 运行下载上传脚本失败: {str(e)}{RESET}")
    else:
        print(f"\n{BLUE}=== 所有项目均为最新版本 ==={RESET}")
        
if __name__ == "__main__":
    main() 