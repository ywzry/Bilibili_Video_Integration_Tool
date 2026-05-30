import sys
import locale
import shutil
import platform
import subprocess
import File_processing as file_p

# 强制 stdout/stderr 使用 UTF-8 编码，确保中英文在所有平台上正常显示
_stdout_reconfigured = False
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, 'reconfigure'):
        _stream.reconfigure(encoding='utf-8', errors='replace')
        _stdout_reconfigured = True
if not _stdout_reconfigured:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def _ensure_ffmpeg(is_zh):
    if shutil.which('ffmpeg'):
        return True

    system = platform.system()
    print('未找到 ffmpeg，尝试自动安装...' if is_zh else 'ffmpeg not found, attempting auto-install...')

    install_cmd = None
    if system == 'Windows':
        if shutil.which('winget'):
            install_cmd = ['winget', 'install', '--accept-source-agreements', 'ffmpeg']
    elif system == 'Darwin':
        if shutil.which('brew'):
            install_cmd = ['brew', 'install', 'ffmpeg']
    elif system == 'Linux':
        for pm, cmd in [
            ('apt-get', ['sudo', '-n', 'apt-get', 'install', '-y', 'ffmpeg']),
            ('dnf',    ['sudo', '-n', 'dnf', 'install', '-y', 'ffmpeg']),
            ('pacman', ['sudo', '-n', 'pacman', '-S', '--noconfirm', 'ffmpeg']),
            ('zypper', ['sudo', '-n', 'zypper', 'install', '-y', 'ffmpeg']),
            ('yum',    ['sudo', '-n', 'yum', 'install', '-y', 'ffmpeg']),
        ]:
            if shutil.which(pm):
                install_cmd = cmd
                break

    if install_cmd:
        try:
            subprocess.run(install_cmd, check=True)
            if shutil.which('ffmpeg'):
                print('ffmpeg 安装成功！' if is_zh else 'ffmpeg installed successfully!')
                return True
        except Exception:
            pass

    # 手动安装指引
    if system == 'Windows':
        print('自动安装失败。请以管理员身份运行: winget install ffmpeg'
              if is_zh else 'Auto-install failed. Run as admin: winget install ffmpeg')
    elif system == 'Darwin':
        print('自动安装失败。请先安装 Homebrew (https://brew.sh)，然后运行: brew install ffmpeg'
              if is_zh else 'Auto-install failed. Install Homebrew first (https://brew.sh), then: brew install ffmpeg')
    elif system == 'Linux':
        print('自动安装失败。请使用系统包管理器手动安装 ffmpeg 后重试。'
              if is_zh else 'Auto-install failed. Please install ffmpeg manually using your package manager.')
    else:
        print('不支持的操作系统，请手动安装 ffmpeg: https://ffmpeg.org/download.html'
              if is_zh else 'Unsupported OS. Please install ffmpeg manually: https://ffmpeg.org/download.html')
    return False


language, encoding = locale.getdefaultlocale()
is_zh = language.startswith('zh') if language else False
file_p.init_lang(is_zh)

if not _ensure_ffmpeg(is_zh):
    sys.exit(1)

if is_zh:
    path = input('请输入你的bilibili下载目录:\t')
else:
    path = input('Please enter your Bilibili download directory:\t')
file_p.Get_Filepath(path)
