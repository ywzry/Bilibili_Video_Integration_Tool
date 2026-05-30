'''
    ZH_CN:
            这个脚本获取处理后的数据并进行合成

    EN_US:
            This script obtains the processed data and performs synthesis.
'''
import subprocess
import os

language = [['视频音频合成完成', '音频文件不存在'],
            ['Video and audio synthesis completed', 'Audio file does not exist']]
i = 0
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def init_lang(is_zh):
    global i
    i = 0 if is_zh else 1

ffmpeg_base = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y']


def _make_result(status, reason, output=''):
    """返回标准化的处理结果字典。"""
    return {'status': status, 'reason': reason, 'output': output}


def _safe_output_basename(filename):
    filename = str(filename or '')
    return 'unnamed_video' if not filename.strip(' ._') else filename


def _stream_kinds(file_path):
    """用 ffprobe 读取媒体流类型，失败时返回空集合。"""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type',
             '-of', 'csv=p=0', file_path],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=4
        )
    except Exception:
        return set()

    return {line.strip().lower() for line in result.stdout.splitlines() if line.strip()}


def _pick_pc_streams(path, oldname):
    """从 PC 端解密后的数字文件中选择 video/audio，ffprobe 失败时回退到排序顺序。"""
    files = [os.path.join(path, item) for item in oldname if item]
    existing_files = [item for item in files if os.path.exists(item)]
    if not existing_files:
        return '', ''

    stream_info = [(item, _stream_kinds(item)) for item in existing_files]
    probed = any(kinds for _, kinds in stream_info)
    video_file = next((item for item, kinds in stream_info if 'video' in kinds), '')
    audio_file = next((item for item, kinds in stream_info if item != video_file and 'audio' in kinds), '')

    if not video_file:
        if probed:
            return '', audio_file
        video_file = existing_files[0]

    if not audio_file and not probed:
        audio_file = next((item for item in existing_files if item != video_file), '')

    return video_file, audio_file


def Win_File_Processing(path, oldname, filename, collection):
    '''
        ZH_CN:
                接收四个参数(地址，旧的文件名，合成文件名，集合名称)，根据参数进行合成

        EN_US:
                Accept four parameters (address, old filename, composite filename, collection name),
                and perform synthesis based on these parameters.
    '''
    out_PATH = os.path.join(BASE_DIR, 'win_bilibili')
    filename = _safe_output_basename(filename)

    if not collection:
        os.makedirs(out_PATH, exist_ok=True)
    else:
        out_PATH = os.path.join(out_PATH, collection)
        os.makedirs(out_PATH, exist_ok=True)

    output_file = os.path.join(out_PATH, filename + '.mp4')
    if os.path.exists(output_file):
        return _make_result('skipped', 'exists', output_file)

    src_v, src_m = _pick_pc_streams(path, oldname)

    if not os.path.exists(src_v):
        return _make_result('skipped', 'missing_video', output_file)

    if src_m and os.path.exists(src_v) and os.path.exists(src_m):
        subprocess.run(ffmpeg_base + ['-i', src_v, '-i', src_m, '-codec', 'copy', output_file],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print(language[i][0])
    else:
        if src_m:
            print(language[i][1])
        subprocess.run(ffmpeg_base + ['-i', src_v, '-codec', 'copy', output_file],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print("OK")

    return _make_result('success', 'merged', output_file)


def P_File_Processing(path, filename, collection):
    '''
        ZH_CN:
                接收三个参数(地址，合成文件名，集合名称)，然后进行合成

        EN_US:
                Accept three parameters (address, composite filename, collection name),
                and then perform synthesis.
    '''
    out_PATH = os.path.join(BASE_DIR, 'D_bilibili')
    filename = _safe_output_basename(filename)
    if not collection:
        os.makedirs(out_PATH, exist_ok=True)
    else:
        out_PATH = os.path.join(out_PATH, collection)
        os.makedirs(out_PATH, exist_ok=True)

    output_file = os.path.join(out_PATH, filename + '.mp4')
    if os.path.exists(output_file):
        return _make_result('skipped', 'exists', output_file)

    video_file = os.path.join(path, 'video.m4s')
    audio_file = os.path.join(path, 'audio.m4s')

    if not os.path.exists(video_file):
        return _make_result('skipped', 'missing_video', output_file)

    if os.path.exists(audio_file):
        subprocess.run(ffmpeg_base + ['-i', video_file, '-i', audio_file, '-codec', 'copy', output_file],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print(language[i][0])
    else:
        print(language[i][1])
        subprocess.run(ffmpeg_base + ['-i', video_file, '-codec', 'copy', output_file],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print("OK")

    return _make_result('success', 'merged', output_file)
