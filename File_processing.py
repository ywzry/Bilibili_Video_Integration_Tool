'''
    ZH_CN:
            这个脚本将解密视频并整理出视频合集

    EN_US:
            This script will decrypt the video and organize it into a video collection.
'''
import os
import json
import hashlib
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import Filepr as fv
language = [['全部处理完成', '\n-------------------------------------\n文件跳过\n------------------------------------\n',
             '正在准备合并下一个文件.......', '无法找到标题文件,自动退出'],
            ['All processing completed',
             '\n-------------------------------------\nfile skip\n------------------------------------\n',
             'Preparing to merge next file...', 'Unable to find title file, exit automatically']]
i = 0

def init_lang(is_zh):
    global i
    i = 0 if is_zh else 1
    fv.init_lang(is_zh)

def _sanitize_filename(name):
    name = str(name or '')
    for char in '<>:"/\\|?*':
        name = name.replace(char, '_')
    return name


def _is_blank_name(name):
    return not str(name or '').strip(' ._')


def _fallback_project_name(path, child=''):
    parent = os.path.basename(os.path.normpath(path))
    parts = [item for item in (parent, child) if item]
    return _sanitize_filename('_'.join(parts) or 'unnamed_video')


def _ensure_output_name(name, path, child=''):
    name = _sanitize_filename(name)
    return _fallback_project_name(path, child) if _is_blank_name(name) else name


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _page_data_dict(data):
    return _as_dict(_as_dict(data).get('page_data'))


def _load_json_object(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError('metadata root is not a JSON object')
    return data


def _stable_cache_name(prefix, path, suffix):
    digest = hashlib.md5(os.path.abspath(path).encode('utf-8')).hexdigest()
    return f'{prefix}_{digest}{suffix}'


def _title_with_bvid(title, bvid):
    title = str(title or '').strip()
    bvid = str(bvid or '').strip()
    if title and bvid:
        return f'{title}_{bvid}'
    return title or bvid


def _video_id(data):
    data = _as_dict(data)
    bvid = str(data.get('bvid') or '')
    if bvid:
        return bvid
    aid = data.get('avid')
    return f'AV{aid}' if aid else ''


def _collection_from_download_subtitle(download_subtitle, part):
    download_subtitle = str(download_subtitle or '').strip()
    part = str(part or '').strip()
    if not download_subtitle or not part or not download_subtitle.endswith(part):
        return None

    collection = download_subtitle[:-len(part)].strip()
    collection = collection.rstrip(' _-｜|').strip()
    return _sanitize_filename(collection) if collection else None


def _owner_key(data):
    data = _as_dict(data)
    return str(data.get('owner_id') or data.get('owner_name') or '')


def _series_tokens(*values):
    text = ' '.join(str(value or '') for value in values).lower()
    tokens = re.findall(r'(?=[a-z0-9]*[a-z])(?=[a-z0-9]*\d)[a-z0-9]{4,}', text)
    return set(tokens)


def _apply_inferred_collections(projects):
    """用明确合集名中的系列 token，在同作者下补齐旧安卓单集合集。"""
    explicit_rules = {}
    ambiguous = set()

    for project in projects:
        if project.get('type') != 'phone' or not project.get('collection'):
            continue
        owner = project.get('owner_key') or project.get('owner_id') or project.get('owner_name') or ''
        if not owner:
            continue
        for token in _series_tokens(project.get('collection_title') or project.get('collection')):
            key = (str(owner), token)
            collection = project.get('collection')
            if key in explicit_rules and explicit_rules[key] != collection:
                ambiguous.add(key)
            else:
                explicit_rules[key] = collection

    for key in ambiguous:
        explicit_rules.pop(key, None)

    if not explicit_rules:
        return

    for project in projects:
        if project.get('type') != 'phone' or project.get('collection'):
            continue
        owner = project.get('owner_key') or project.get('owner_id') or project.get('owner_name') or ''
        if not owner:
            continue
        matches = {
            explicit_rules[(str(owner), token)]
            for token in _series_tokens(project.get('title'), project.get('part'))
            if (str(owner), token) in explicit_rules
        }
        if len(matches) != 1:
            continue
        collection = _sanitize_filename(matches.pop())
        project['collection'] = collection
        project['collection_key'] = collection
        project['collection_title'] = collection


def _phone_title_and_collection(title, part, sibling_count, download_subtitle='', owner_name=''):
    title = str(title or '')
    part = str(part or '')
    download_subtitle = str(download_subtitle or '')
    owner_name = str(owner_name or '')

    if not title or not part:
        return title or part, None

    old_android_collection = _collection_from_download_subtitle(download_subtitle, part)
    if old_android_collection:
        return part, old_android_collection

    if sibling_count > 1:
        return part, _sanitize_filename(title)

    for sep in ('|', '｜'):
        if sep in part:
            collection = part.rsplit(sep, 1)[-1].strip()
            if collection:
                return title, _sanitize_filename(collection)

    if title in part:
        return title, None

    return title, None


def _episode_order(title, part):
    for text in (str(title or ''), str(part or '')):
        match = re.search(r'(?:^|第)\s*(\d+)\s*(?:[【\[]|[集课期])', text)
        if match:
            return int(match.group(1))
    return None


def _process_result(status, reason, path, title='', output='', error=''):
    """统一处理结果结构，供 Win_File / Phone_File 返回。"""
    return {
        'status': status,   # success | skipped | failed
        'reason': reason,   # merged | exists | missing_video | missing_metadata | ffmpeg_error
        'path': path,
        'title': title,
        'output': output,
        'error': error,
    }


def _select_quality_dir(c_path):
    """在 c_xxx 目录下选择画质最高的数字子目录（有 video.m4s 的）。"""
    try:
        with os.scandir(c_path) as entries:
            num_dirs = sorted(
                [e.name for e in entries if e.is_dir() and e.name.isdigit()],
                key=int, reverse=True
            )
    except OSError:
        return None

    for d in num_dirs:
        if os.path.exists(os.path.join(c_path, d, 'video.m4s')):
            return d
    return None


def Get_Filepath(get_path):
    if not get_path or not os.path.isdir(get_path):
        print('目录不存在，请检查路径。' if i == 0 else 'Directory does not exist. Check the path.')
        return

    projects = scan_projects(get_path)
    total = len(projects)
    if total == 0:
        print('未找到任何 Bilibili 视频项目，请检查目录路径。' if i == 0 else 'No Bilibili video projects found. Check the directory path.')
        return

    succeeded = 0
    skipped = 0
    failed = 0
    max_workers = min(4, (os.cpu_count() or 2))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for project in projects:
            if project['type'] == 'win':
                futures.append(executor.submit(Win_File, project['path']))
            else:
                c_dir = project['c_dir']
                futures.append(executor.submit(
                    Phone_File,
                    project['path'],
                    [c_dir],
                    collection_overrides={c_dir: project.get('collection')},
                    file_name_overrides={c_dir: project.get('title')}
                ))
        for future in as_completed(futures):
            try:
                results = future.result()
                for r in results:
                    if r['status'] == 'success':
                        succeeded += 1
                    elif r['status'] == 'skipped':
                        skipped += 1
                    else:
                        failed += 1
            except Exception as e:
                print(('任务失败: ' if i == 0 else 'Task failed: ') + str(e))
                failed += 1

    print(language[i][0] + f' (成功 {succeeded}, 跳过 {skipped}, 失败 {failed}, 总计 {succeeded + skipped + failed})')
            

def Judgment_File(get_path, c_num):
    if not get_path:
        return []
    try:
        with os.scandir(get_path) as entries:
            if c_num:
                return [e.name for e in entries if e.is_dir()]
            else:
                return [e.name for e in entries if e.is_file()]
    except OSError:
        return []


def Win_File(path):
    '''
        ZH_CN:
                接收一个参数(目录地址)，这个方法用于查询、生成文件或者合集是否存在，并将文件解密，最后将结果交给filepr.py进行合成处理。

                GUI 和 CLI 都通过返回值判断处理结果。

        EN_US:
                Accept one parameter (directory address).
                This method is used to query whether the file or collection exists and generate it,
                decrypt the file, and finally pass the result to filepr.py for synthesis processing.

                Both GUI and CLI use the return value to determine the processing result.
    '''
    tmp_flist = Judgment_File(path, False)

    if '.videoInfo' not in tmp_flist:
        print(language[i][3])
        return [_process_result('skipped', 'missing_metadata', path)]

    try:
        data = _load_json_object(os.path.join(path, '.videoInfo'))
    except (OSError, json.JSONDecodeError, ValueError) as e:
        print(('读取 .videoInfo 失败，跳过: ' if i == 0 else 'Failed to read .videoInfo, skipping: ') + path)
        return [_process_result('skipped', 'missing_metadata', path, error=str(e))]

    page_data       = str(data.get('tabName') or '')
    win_part        = str(data.get('p') or '1')
    bvid            = str(data.get('groupId') or '')
    collection      = str(data.get('groupTitle') or '')

    Valid_File_Name = sorted([item for item in tmp_flist if item and item[0].isdigit()])
    if not Valid_File_Name:
        print('未找到有效视频文件，跳过: ' + path if i == 0 else 'No valid video files found, skipping: ' + path)
        return [_process_result('skipped', 'missing_video', path, title=page_data)]

    file_name = page_data + '_' + bvid

    if not collection or collection == page_data:
        collection = None
        file_name = _ensure_output_name(file_name, path)
    else:
        collection = _sanitize_filename(collection)
        file_name = _ensure_output_name('P' + win_part + '_' + page_data + '_' + bvid, path)

    Xfile_name = []
    try:
        Xfile_name = File_Decryption(path, Valid_File_Name)
        result = fv.Win_File_Processing(path, Xfile_name, file_name, collection)
        return [_process_result(
            result['status'],
            result['reason'],
            path,
            title=file_name,
            output=result.get('output', '')
        )]
    except Exception as e:
        reason = 'decrypt_error' if not Xfile_name else 'ffmpeg_error'
        return [_process_result('failed', reason, path, title=file_name, error=str(e))]
    finally:
        for file_i in Xfile_name:
            d_file = os.path.join(path, file_i)
            if os.path.exists(d_file):
                try:
                    os.remove(d_file)
                except OSError:
                    pass

def File_Decryption(file_path,file_name):
    '''
        ZH_CN:
                接收两个参数(文件地址,文件名)这个方法用于解密被加密的视频

        EN_US:
                Accept two parameters (file address, filename). This method is used to decrypt encrypted videos.
    '''
    created = []
    try:
        for idx, file_name_tmp in enumerate(file_name):
            src_path = os.path.join(file_path, file_name_tmp)
            file_name_tmp = 'X' + file_name_tmp
            dst_path = os.path.join(file_path, file_name_tmp)
            with open(src_path, 'rb') as src, open(dst_path, 'wb') as dst:
                head = src.read(9)
                if head != b'\x30\x30\x30\x30\x30\x30\x30\x30\x30':
                    dst.write(head)
                while True:
                    chunk = src.read(8 * 1024 * 1024)
                    if not chunk:
                        break
                    dst.write(chunk)
            created.append(dst_path)
            file_name[idx] = file_name_tmp
        return file_name
    except Exception:
        for item in created:
            if os.path.exists(item):
                try:
                    os.remove(item)
                except OSError:
                    pass
        raise

def Phone_File(p_path, c_list, collection_overrides=None, file_name_overrides=None):
    """
        ZH_CN:
                接收两个参数(目录地址，目录下以'c_'开头的目录列表)，这个方法用于查询、生成文件或者合集是否存在，
                并将结果交给filepr.py进行合成处理。

                GUI 和 CLI 都通过返回值判断处理结果。

        EN_US:
                Accept two parameters (directory address, directory list starting with 'c_').
                This method is used to query whether the file or collection exists and generate it,
                and then pass the result to filepr.py for synthesis processing.

                Both GUI and CLI use the return value to determine the processing result.
    """
    collection_overrides = collection_overrides or {}
    file_name_overrides = file_name_overrides or {}
    results = []

    for c in c_list:
        R_num_folder = os.path.join(p_path, c)
        try:
            data = _load_json_object(os.path.join(R_num_folder, 'entry.json'))
        except (OSError, json.JSONDecodeError, ValueError) as e:
            print(('读取 entry.json 失败，跳过: ' if i == 0 else 'Failed to read entry.json, skipping: ') + R_num_folder)
            results.append(_process_result('skipped', 'missing_metadata', R_num_folder, error=str(e)))
            continue

        page_data           = _page_data_dict(data)
        title               = data.get('title', '')
        part                = page_data.get('part', '')
        download_subtitle   = page_data.get('download_subtitle', '')
        owner_name          = data.get('owner_name', '')
        video_id            = _video_id(data)

        item_title, collection = _phone_title_and_collection(
            title, part, len(c_list), download_subtitle, owner_name
        )
        file_name = _sanitize_filename(_title_with_bvid(item_title, video_id))
        if c in collection_overrides:
            override = collection_overrides[c]
            collection = _sanitize_filename(override) if override else None
        if c in file_name_overrides and file_name_overrides[c]:
            file_name = _sanitize_filename(file_name_overrides[c])
        file_name = _ensure_output_name(file_name, p_path, c)

        quality_dir = _select_quality_dir(R_num_folder)
        if not quality_dir:
            results.append(_process_result('skipped', 'missing_video', R_num_folder, title=file_name))
            continue
        folder_path = os.path.join(R_num_folder, quality_dir)

        try:
            merge_result = fv.P_File_Processing(folder_path, file_name, collection)
            results.append(_process_result(
                merge_result['status'],
                merge_result['reason'],
                R_num_folder,
                title=file_name,
                output=merge_result.get('output', '')
            ))
        except Exception as e:
            results.append(_process_result('failed', 'ffmpeg_error', R_num_folder, title=file_name, error=str(e)))

    return results


def scan_projects(root_path):
    """扫描目录，返回视频项目元数据列表（不执行解密和合成）。"""
    if not root_path or not os.path.isdir(root_path):
        return []

    projects = []
    root_depth = root_path.rstrip(os.sep).count(os.sep)

    for dirpath, dirnames, filenames in os.walk(root_path):
        depth = dirpath.rstrip(os.sep).count(os.sep) - root_depth
        if depth > 5:
            dirnames.clear()
            continue

        if '.videoInfo' in filenames:
            try:
                data = _load_json_object(os.path.join(dirpath, '.videoInfo'))
            except (OSError, json.JSONDecodeError, ValueError):
                dirnames.clear()
                continue

            page_data = str(data.get('tabName') or '')
            part = str(data.get('p') or '1')
            bvid = str(data.get('groupId') or '')
            collection_title = str(data.get('groupTitle') or '')

            title = page_data
            if collection_title and collection_title != page_data:
                title = 'P' + part + '_' + page_data + '_' + bvid
                collection = _sanitize_filename(collection_title)
            else:
                collection = None
            title = _ensure_output_name(title, dirpath)

            # 获取第一个视频文件用于提取时长
            video_files = sorted([item for item in filenames if item and item[0].isdigit()])
            sample_file = os.path.join(dirpath, video_files[0]) if video_files else ''

            projects.append({
                'type': 'win',
                'path': dirpath,
                'title': title,
                'part': part,
                'bvid': bvid,
                'video_id': bvid,
                'collection': collection,
                'collection_key': collection,
                'collection_title': collection,
                'sample_file': sample_file,
                'thumbnail_file': '',
                'duration': None,
                'c_dir': None,
            })
            dirnames.clear()
            continue

        c_dirs = [d for d in dirnames if d.startswith('c_')]
        if c_dirs:
            for c_dir in c_dirs:
                entry_path = os.path.join(dirpath, c_dir, 'entry.json')
                try:
                    data = _load_json_object(entry_path)
                except (OSError, json.JSONDecodeError, ValueError):
                    continue

                page_data = _page_data_dict(data)
                title = data.get('title', '')
                part = page_data.get('part', '')
                download_subtitle = page_data.get('download_subtitle', '')
                owner_name = data.get('owner_name', '')
                owner_id = data.get('owner_id', '')
                aid_value = data.get('avid')
                aid = str(aid_value) if aid_value else ''
                bvid = str(data.get('bvid') or '')
                video_id = bvid or (f'AV{aid}' if aid else '')

                episode_order = _episode_order(title, part)
                item_title, collection = _phone_title_and_collection(
                    title, part, len(c_dirs), download_subtitle, owner_name
                )
                display_title = _title_with_bvid(item_title, video_id)
                display_title = _ensure_output_name(display_title, dirpath, c_dir)

                # 获取视频文件用于提取时长（选最高画质）
                c_path = os.path.join(dirpath, c_dir)
                quality_dir = _select_quality_dir(c_path)
                sample_file = os.path.join(c_path, quality_dir, 'video.m4s') if quality_dir else ''
                cover_file = os.path.join(c_path, 'cover.jpg')

                projects.append({
                    'type': 'phone',
                    'path': dirpath,
                    'c_dir': c_dir,
                    'avid': aid,
                    'title': _sanitize_filename(display_title),
                    'part': part,
                    'bvid': bvid,
                    'video_id': video_id,
                    'owner_id': str(owner_id or ''),
                    'owner_name': str(owner_name or ''),
                    'owner_key': _owner_key(data),
                    'collection': collection,
                    'collection_key': collection,
                    'collection_title': collection,
                    'episode_order': episode_order,
                    'sample_file': sample_file,
                    'thumbnail_file': cover_file if os.path.exists(cover_file) else '',
                    'duration': None,
                })
            dirnames.clear()
            continue

    _apply_inferred_collections(projects)
    return projects


def get_video_duration(video_path, max_copy_bytes=16 * 1024 * 1024):
    """用 ffprobe 获取视频时长（秒），自动处理 PC 端加密，失败返回 None。"""
    import subprocess as _sp
    import tempfile

    src = video_path

    try:
        with open(video_path, 'rb') as f:
            head = f.read(9)
    except OSError:
        return None

    if head == b'\x30\x30\x30\x30\x30\x30\x30\x30\x30':
        tmp = os.path.join(tempfile.gettempdir(), _stable_cache_name('bili_dur', video_path, '.mp4'))
        try:
            expected_size = max(0, os.path.getsize(video_path) - 9)
        except OSError:
            return None
        target_size = min(expected_size, max_copy_bytes) if max_copy_bytes else expected_size
        try:
            tmp_ready = os.path.exists(tmp) and os.path.getsize(tmp) == target_size
        except OSError:
            tmp_ready = False
        if not tmp_ready:
            try:
                with open(video_path, 'rb') as fsrc, open(tmp, 'wb') as fdst:
                    fsrc.seek(9)
                    copied = 0
                    while True:
                        if max_copy_bytes and copied >= max_copy_bytes:
                            break
                        chunk = fsrc.read(1024 * 1024)
                        if not chunk:
                            break
                        if max_copy_bytes and copied + len(chunk) > max_copy_bytes:
                            chunk = chunk[:max_copy_bytes - copied]
                        fdst.write(chunk)
                        copied += len(chunk)
            except OSError:
                return None
        src = tmp

    try:
        result = _sp.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'csv=p=0', src],
            stdout=_sp.PIPE, stderr=_sp.PIPE, text=True, timeout=4
        )
        return float(result.stdout.strip()) if result.stdout.strip() else None
    except Exception:
        return None


def extract_thumbnail(video_path, output_path, size=160, should_continue=None,
                      timeout=3, max_copy_bytes=16 * 1024 * 1024):
    """用 ffmpeg 从视频中提取缩略图，自动处理 PC 端加密，返回是否成功。"""
    import subprocess as _sp
    import tempfile

    def keep_going():
        return should_continue is None or should_continue()

    src = video_path
    tmp = None

    if not keep_going():
        return False

    # 检测并处理 PC 端 9 字节混淆头
    try:
        with open(video_path, 'rb') as f:
            head = f.read(9)
    except OSError:
        return False

    if head == b'\x30\x30\x30\x30\x30\x30\x30\x30\x30':
        tmp = os.path.join(tempfile.gettempdir(), _stable_cache_name('bili_thumb_src', video_path, '.mp4'))
        try:
            expected_size = max(0, os.path.getsize(video_path) - 9)
        except OSError:
            return False
        target_size = min(expected_size, max_copy_bytes) if max_copy_bytes else expected_size
        try:
            tmp_ready = os.path.exists(tmp) and os.path.getsize(tmp) == target_size
        except OSError:
            tmp_ready = False
        if not tmp_ready:
            try:
                with open(video_path, 'rb') as fsrc, open(tmp, 'wb') as fdst:
                    fsrc.seek(9)
                    copied = 0
                    while True:
                        if not keep_going():
                            return False
                        if max_copy_bytes and copied >= max_copy_bytes:
                            break
                        chunk = fsrc.read(8 * 1024 * 1024)
                        if not chunk:
                            break
                        if max_copy_bytes and copied + len(chunk) > max_copy_bytes:
                            chunk = chunk[:max_copy_bytes - copied]
                        fdst.write(chunk)
                        copied += len(chunk)
            except OSError:
                return False
        src = tmp

    if not keep_going():
        return False

    try:
        _sp.run(
            ['ffmpeg', '-y', '-i', src, '-vframes', '1',
             '-vf', f'scale={size}:-1', output_path],
            stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, check=True, timeout=timeout
        )
        return True
    except Exception:
        return False
