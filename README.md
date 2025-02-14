# g-to-lan

一个命令行工具，用于自动同步 GitHub Release 到蓝奏云。支持多个项目的自动检查、下载和上传，可配置 GitHub Actions 实现定时自动更新。

## 功能特点

- 自动检查 GitHub Release 更新
- 支持多个项目同时监控
- 自动下载最新版本文件
- 自动上传到蓝奏云指定文件夹
- 支持 GitHub Actions 自动运行
- 避免重复下载和上传
- 文件大小限制检查（蓝奏云限制100MB）

## 使用方法

### 1. 配置文件

在 `download_tasks.yaml` 中配置需要监控的项目：

```yaml
tasks:
  - url: https://github.com/用户名/项目名/releases/latest
    folder_name: 蓝奏云文件夹名称
    
  - url: https://github.com/用户名/项目名/releases/latest
    folder_name: 蓝奏云文件夹名称
```

### 2. 设置 GitHub Secrets

在 GitHub 仓库的 Settings -> Secrets and variables -> Actions 中添加以下 Secrets：

- `LANZOU_USERNAME`: 蓝奏云账号
- `LANZOU_PASSWORD`: 蓝奏云密码
- `LANZOU_UID`: 蓝奏云用户ID（可从浏览器开发者工具中获取）

### 3. 自动运行

项目设置了自动运行计划：

- 每12小时自动检查一次更新
- 可以在 GitHub Actions 页面手动触发运行
- 发现更新时自动下载并上传

## 文件说明

- `check_github_update.py`: 检查更新的主程序
- `github_to_lanzou.py`: 下载和上传的实现
- `download_tasks.yaml`: 任务配置文件
- `config.py`: 蓝奏云账号配置（通过 GitHub Secrets 设置）
- `.github/workflows/check_update.yml`: GitHub Actions 工作流配置

## 运行环境

- Python 3.10+
- 依赖包：
  - requests
  - PyYAML
  - tqdm

## 本地运行

1. 安装依赖：

    ```bash
    pip install -r requirements.txt
    ```

2. 配置蓝奏云账号：
在 `config.py` 中填写账号信息

3. 运行检查：

    ```bash
    python check_github_update.py
    ```

## 注意事项

1. 蓝奏云限制：
   - 单个文件最大100MB
   - 仅支持特定类型文件上传

2. GitHub API限制：
   - 未认证用户每小时60次请求限制
   - 建议使用合适的运行间隔

3. 安全建议：
   - 不要在配置文件中保存真实账号密码
   - 使用 GitHub Secrets 保存敏感信息

## License

MIT License
