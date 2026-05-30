"""
    Bilibili Video Integration Tool — 图形界面
"""
import os
import locale
import hashlib
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from concurrent.futures import ThreadPoolExecutor, as_completed

import File_processing as fp


class App:
    """主应用。"""

    def __init__(self, root):
        self.root = root
        self.root.title('Bilibili Video Integration Tool')
        self.root.geometry('1020x700')
        self.root.minsize(800, 450)

        self._all_videos = []
        self.videos = []
        self._coll_map = {}
        self._last_folder_click = None
        self._scan_gen = 0
        self._duration_gen = 0
        self._thumb_gen = 0
        self._scanning = False
        self._processing = False
        self._closing = False
        self._thumb_enabled = False
        self._thumb_cache = {}
        self._thumb_pool = None
        self._duration_pool = None
        self._init_lang()
        self._check_pillow()
        self._setup_style()
        self._build()
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

    def _init_lang(self):
        language, _ = locale.getdefaultlocale()
        is_zh = language.startswith('zh') if language else False
        fp.init_lang(is_zh)

    def _check_pillow(self):
        try:
            from PIL import Image, ImageTk  # noqa: F401
            self._thumb_enabled = True
        except ImportError:
            pass

    def _safe_after(self, delay, callback, *args):
        if self._closing:
            return None
        try:
            return self.root.after(delay, callback, *args)
        except tk.TclError:
            return None

    def _setup_style(self):
        style = ttk.Style()
        style.configure('Treeview', rowheight=48, font=('Microsoft YaHei UI', 10))
        style.configure('Treeview.Heading', font=('Microsoft YaHei UI', 10, 'bold'))
        style.configure('TButton', font=('Microsoft YaHei UI', 10))
        style.configure('TLabel', font=('Microsoft YaHei UI', 10))
        style.configure('TEntry', font=('Microsoft YaHei UI', 10))

    # ── UI 构建 ──

    def _build(self):
        # 顶部：目录选择
        top = ttk.Frame(self.root, padding='10 10 10 5')
        top.pack(fill=tk.X)

        ttk.Label(top, text='下载目录:').pack(side=tk.LEFT)

        self.dir_var = tk.StringVar()
        dir_entry = ttk.Entry(top, textvariable=self.dir_var)
        dir_entry.pack(side=tk.LEFT, padx=(5, 5), fill=tk.X, expand=True)
        dir_entry.bind('<Return>', lambda _: self._scan())
        dir_entry.bind('<Button-3>', self._entry_context_menu)
        if os.name == 'nt':
            dir_entry.bind('<Control-v>', lambda e: dir_entry.event_generate('<<Paste>>'))
            dir_entry.bind('<Control-V>', lambda e: dir_entry.event_generate('<<Paste>>'))

        ttk.Button(top, text='浏览', command=self._browse).pack(side=tk.LEFT)
        ttk.Button(top, text='扫描', command=self._scan).pack(side=tk.LEFT, padx=(5, 0))

        search_bar = ttk.Frame(self.root, padding='10 0 10 5')
        search_bar.pack(fill=tk.X)

        ttk.Label(search_bar, text='搜索:').pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *_: self._apply_search())
        search_entry = ttk.Entry(search_bar, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, padx=(5, 5), fill=tk.X, expand=True)
        ttk.Button(search_bar, text='清空', command=lambda: self.search_var.set('')).pack(side=tk.LEFT)

        # 中间：Treeview 全宽
        mid = ttk.Frame(self.root, padding='10 5 10 5')
        mid.pack(fill=tk.BOTH, expand=True)
        mid.columnconfigure(0, weight=1)
        mid.rowconfigure(0, weight=1)

        columns = ('bvid', 'duration')
        self.tree = ttk.Treeview(
            mid, columns=columns, show='tree headings',
            selectmode='extended')
        self.tree.heading('#0', text='  标题')
        self.tree.heading('bvid', text='视频号')
        self.tree.heading('duration', text='时长')
        self.tree.column('#0', width=590, minwidth=350)
        self.tree.column('bvid', width=150, minwidth=100)
        self.tree.column('duration', width=100, minwidth=80, anchor=tk.CENTER)
        self.tree.grid(row=0, column=0, sticky='nsew')

        tree_scroll = ttk.Scrollbar(mid, orient=tk.VERTICAL,
                                     command=self._on_tree_scroll)
        tree_scroll.grid(row=0, column=1, sticky='ns')
        self._tree_scroll = tree_scroll
        # hook yscrollcommand：滚轮/键盘/拖滚动条均触发
        self.tree.configure(yscrollcommand=self._on_view_changed)

        self.tree.tag_configure('folder', font=('Microsoft YaHei UI', 10, 'bold'))

        self.tree.bind('<Button-1>', self._on_tree_click)
        self.tree.bind('<<TreeviewSelect>>', self._on_selection_changed)
        self.tree.bind('<<TreeviewOpen>>', self._on_scroll_debounce)
        self._scroll_after = None

        # 底部：选择操作 + 状态 + 进度 + 按钮
        bottom = ttk.Frame(self.root, padding='10 8 10 10')
        bottom.pack(fill=tk.X)

        ttk.Button(bottom, text='全选', command=self._select_all).pack(side=tk.LEFT)
        ttk.Button(bottom, text='取消选择', command=self._deselect_all).pack(side=tk.LEFT, padx=(5, 20))

        self.status_var = tk.StringVar(value='就绪')
        ttk.Label(bottom, textvariable=self.status_var).pack(side=tk.LEFT)

        self.progress = ttk.Progressbar(bottom, mode='determinate', length=200)
        self.progress.pack(side=tk.LEFT, padx=(20, 0))

        self.cancel_btn = ttk.Button(
            bottom, text='取消', command=self._cancel, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.RIGHT)

        self._process_btn_text = tk.StringVar(value='开始处理')
        self.process_btn = ttk.Button(
            bottom, textvariable=self._process_btn_text,
            command=self._start_processing, state=tk.DISABLED)
        self.process_btn.pack(side=tk.RIGHT, padx=(0, 5))

    def _entry_context_menu(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label='粘贴', command=self._paste_to_entry)
        menu.add_command(label='清空', command=lambda: self.dir_var.set(''))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.destroy()

    def _paste_to_entry(self):
        try:
            text = self.root.clipboard_get()
            self.dir_var.set(self.dir_var.get() + text)
        except tk.TclError:
            pass

    # ── 选择逻辑 ──

    def _video_iids(self):
        return [v['_iid'] for v in self.videos if '_iid' in v]

    def _selected_videos(self):
        """返回 Treeview 中当前被选中（蓝色高亮）的视频。"""
        sel = set(self.tree.selection())
        for folder_iid in list(sel):
            sel.update(self._coll_map.get(folder_iid, []))

        selected = []
        seen = set()
        for v in self.videos:
            iid = v.get('_iid')
            if iid in sel and iid not in seen:
                selected.append(v)
                seen.add(iid)
        return selected

    def _on_selection_changed(self, event):
        self._update_process_btn()

    def _on_tree_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return None
        if 'folder' not in self.tree.item(iid, 'tags'):
            self._last_folder_click = None
            return None

        should_toggle = iid == self._last_folder_click and iid in self.tree.selection()
        self.tree.selection_set(iid)
        self.tree.focus(iid)
        if should_toggle:
            self.tree.item(iid, open=not self.tree.item(iid, 'open'))
        self._last_folder_click = iid
        self._update_process_btn()
        self._on_scroll_debounce()
        return 'break'

    def _on_view_changed(self, *args):
        """Treeview 视口变化时触发（滚轮/键盘/滚动条均覆盖）。"""
        self._tree_scroll.set(*args)
        self._on_scroll_debounce()

    def _on_tree_scroll(self, *args):
        """滚动条拖动时触发。"""
        self.tree.yview(*args)

    def _on_scroll_debounce(self, _event=None):
        """滚动后延迟 200ms 再加载缩略图，避免快速滚动时频繁触发。"""
        if self._closing:
            return
        if self._scroll_after is not None:
            try:
                self.root.after_cancel(self._scroll_after)
            except (ValueError, tk.TclError):
                pass
        self._scroll_after = self._safe_after(200, self._on_scroll_loaded)

    def _select_all(self):
        all_rows = self._video_iids() + list(self._coll_map.keys())
        self.tree.selection_set(all_rows)
        self.tree.focus_set()

    def _deselect_all(self):
        self.tree.selection_set(())

    def _update_process_btn(self):
        n = len(self._selected_videos())
        total = len(self._video_iids())
        if n == 0:
            self._process_btn_text.set('开始处理')
            self.process_btn.configure(state=tk.DISABLED)
        elif n == total:
            self._process_btn_text.set(f'开始处理 (全部 {n} 个)')
            self.process_btn.configure(state=tk.NORMAL)
        else:
            self._process_btn_text.set(f'开始处理 (选中 {n} 个)')
            self.process_btn.configure(state=tk.NORMAL)

    # ── 目录选择 / 扫描 ──

    def _browse(self):
        path = filedialog.askdirectory(title='选择 Bilibili 下载目录')
        if path:
            self.dir_var.set(path)
            self._scan()

    def _scan(self):
        if self._closing or self._scanning:
            return
        path = self.dir_var.get().strip()
        if not path:
            return
        if not os.path.isdir(path):
            messagebox.showerror('错误', '目录不存在，请检查路径。')
            return

        self._scanning = True
        self._scan_gen += 1
        scan_gen = self._scan_gen
        if hasattr(self, 'search_var') and self.search_var.get():
            self.search_var.set('')
        self._clear()
        self.status_var.set('正在扫描...')

        def do_scan():
            videos = fp.scan_projects(path)
            if not self._closing:
                self._safe_after(0, lambda: self._populate(videos, scan_gen))

        threading.Thread(target=do_scan, daemon=True).start()

    def _clear(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._all_videos = []
        self.videos = []
        self._coll_map.clear()
        self._thumb_cache.clear()
        self._last_folder_click = None
        self._duration_gen += 1
        self._thumb_gen += 1
        self._shutdown_pool('_thumb_pool')
        self._shutdown_pool('_duration_pool')
        self._update_process_btn()
        self.progress.configure(value=0)

    def _shutdown_pool(self, attr):
        pool = getattr(self, attr, None)
        if pool is None:
            return
        try:
            pool.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            pool.shutdown(wait=False)
        setattr(self, attr, None)

    # ── 列表填充 ──

    def _populate(self, videos, scan_gen=None):
        if scan_gen is not None and scan_gen != self._scan_gen:
            return
        self._scanning = False
        self._all_videos = videos
        self._render_videos(self._filter_videos(), load_durations=True)

        if not videos:
            self.status_var.set('未找到视频')
            return

    def _filter_videos(self):
        keyword = self.search_var.get().strip().lower()
        if not keyword:
            return list(self._all_videos)

        result = []
        for v in self._all_videos:
            fields = [
                v.get('title', ''),
                v.get('bvid', ''),
                v.get('video_id', ''),
                v.get('avid', ''),
                v.get('collection_title', ''),
                v.get('collection_key', ''),
                v.get('path', ''),
            ]
            if any(keyword in str(field).lower() for field in fields):
                result.append(v)
        return result

    def _apply_search(self):
        if self._scanning:
            return
        self._render_videos(self._filter_videos(), load_durations=False)

    def _duration_text(self, v):
        if not v.get('sample_file'):
            return '缺文件'
        d = v.get('duration')
        if d is None:
            return '...'
        mins, secs = int(d // 60), int(d % 60)
        return f'{mins:02d}:{secs:02d}'

    def _render_videos(self, videos, load_durations=False):
        if not load_durations:
            self._duration_gen += 1
            self._shutdown_pool('_duration_pool')
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.videos = videos
        self._coll_map.clear()
        self._thumb_cache.clear()
        self._last_folder_click = None
        self._update_process_btn()

        if not videos:
            total = len(self._all_videos)
            self.status_var.set('没有匹配的视频' if total else '未找到视频')
            return

        collections = {}
        collection_titles = {}
        singles = []

        for v in videos:
            coll_key = v.get('collection_key') or v.get('collection')
            if coll_key:
                collections.setdefault(coll_key, []).append(v)
                collection_titles.setdefault(coll_key, v.get('collection_title') or v.get('collection') or coll_key)
            else:
                singles.append(v)

        for v in singles:
            iid = self.tree.insert('', 'end',
                                   text='  ' + v.get('title', ''),
                                   values=(v.get('video_id') or v.get('bvid', ''), self._duration_text(v)))
            v['_iid'] = iid

        for coll_key, items in collections.items():
            coll_name = collection_titles.get(coll_key, coll_key)
            coll_bvid = items[0].get('video_id') or items[0].get('bvid', '')
            items.sort(key=lambda item: (
                item.get('episode_order') is None,
                item.get('episode_order') or 0,
                item.get('title', '')
            ))
            coll_iid = self.tree.insert('', 'end',
                                        text=f'\U0001F4C1 {coll_name}  [{len(items)}]',
                                        values=(coll_bvid, ''),
                                        open=False, tags=('folder',))
            child_iids = []
            for v in items:
                child_bvid = v.get('video_id') or v.get('bvid', '') or coll_bvid
                iid = self.tree.insert(coll_iid, 'end',
                                       text=v.get('title', ''),
                                       values=(child_bvid, self._duration_text(v)))
                v['_iid'] = iid
                child_iids.append(iid)
            self._coll_map[coll_iid] = child_iids

        self.status_var.set(f'显示 {len(videos)} / {len(self._all_videos)} 个视频')
        self._update_process_btn()

        if load_durations:
            self.status_var.set(f'共找到 {len(videos)} 个视频，正在获取时长与预览...')
            threading.Thread(target=self._load_durations, daemon=True).start()
        self._on_scroll_debounce()

    # ── 后台加载时长 ──

    def _load_durations(self):
        self._duration_gen += 1
        duration_gen = self._duration_gen
        videos = [v for v in self.videos
                   if v.get('sample_file') and os.path.exists(v['sample_file'])]
        total = len(videos)
        completed = 0

        last_update = time.monotonic()
        pending = {}
        pending_lock = threading.Lock()

        def flush_updates():
            with pending_lock:
                snapshot = dict(pending)
                pending.clear()
            for iid, d in snapshot.items():
                if duration_gen != self._duration_gen:
                    return
                if iid and self.tree.exists(iid):
                    mins, secs = int(d // 60), int(d % 60)
                    vals = list(self.tree.item(iid, 'values'))
                    vals[1] = f'{mins:02d}:{secs:02d}'
                    self.tree.item(iid, values=vals)

        pool = ThreadPoolExecutor(max_workers=2)
        self._duration_pool = pool
        try:
            futures = {}
            for v in videos:
                futures[pool.submit(fp.get_video_duration, v['sample_file'])] = v

            for future in as_completed(futures):
                if self._closing or duration_gen != self._duration_gen:
                    return
                v = futures[future]
                try:
                    d = future.result()
                    if d is not None:
                        v['duration'] = d
                        iid = v.get('_iid')
                        with pending_lock:
                            pending[iid] = d
                except Exception:
                    pass

                completed += 1
                now = time.monotonic()
                if now - last_update >= 0.5 or completed == total:
                    self._safe_after(0, flush_updates)
                    last_update = now
                    if not self._closing:
                        self._safe_after(0, lambda c=completed, t=total: (
                            self.progress.configure(value=int(c / t * 100)),
                            self.status_var.set(f'正在获取时长... ({c}/{t})')
                        ))
        finally:
            if getattr(self, '_duration_pool', None) is pool:
                self._duration_pool = None
            try:
                pool.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                pool.shutdown(wait=False)

        if not self._closing and duration_gen == self._duration_gen:
            self._safe_after(0, lambda: (
                self.progress.configure(value=0),
                self.status_var.set(f'共找到 {len(self.videos)} 个视频')
            ))

    # ── 按视口优先并行加载缩略图 ──

    def _visible_display_iids(self):
        """按控件实际像素位置获取当前可见行，避免 yview 比例估算错位。"""
        self.tree.update_idletasks()
        height = max(self.tree.winfo_height(), 1)
        rowheight = int(ttk.Style().lookup('Treeview', 'rowheight') or 48)
        seen = []
        for y in range(0, height + rowheight, max(rowheight // 2, 1)):
            iid = self.tree.identify_row(y)
            if iid and iid not in seen:
                seen.append(iid)
        return seen

    def _on_scroll_loaded(self):
        """debounce 定时器回调：重置标记后加载。"""
        self._scroll_after = None
        self._load_visible_thumbnails()

    def _load_visible_thumbnails(self, _event=None):
        """只加载当前可见区域的缩略图，并行提取。"""
        if self._closing or not self._thumb_enabled or not self.videos:
            return

        # 取消上一批还在排队的任务
        self._shutdown_pool('_thumb_pool')
        self._thumb_gen += 1
        gen = self._thumb_gen

        visible_iids = self._visible_display_iids()
        if not visible_iids:
            return
        video_iids = set(self._video_iids())
        visible = {iid for iid in visible_iids if iid in video_iids}

        todo = []
        for v in self.videos:
            iid = v.get('_iid')
            if iid in visible and iid not in self._thumb_cache:
                sf = v.get('thumbnail_file') or v.get('sample_file', '')
                if sf and os.path.exists(sf):
                    self._thumb_cache[iid] = None
                    if os.path.basename(sf).lower() == 'cover.jpg':
                        self._set_thumb(v, sf)
                    else:
                        todo.append((v, sf))

        if not todo:
            return

        self._thumb_pool = ThreadPoolExecutor(max_workers=1)
        for v, sf in todo:
            self._thumb_pool.submit(self._extract_one_thumb, v, sf, gen)

    def _extract_one_thumb(self, v, sf, gen):
        if self._closing or gen != getattr(self, '_thumb_gen', 0):
            if not self._closing:
                self._safe_after(0, lambda v=v: self._thumb_cache.pop(v.get('_iid'), None))
            return
        try:
            import tempfile
            digest = hashlib.md5(os.path.abspath(sf).encode('utf-8')).hexdigest()
            tmp = os.path.join(tempfile.gettempdir(),
                               f'bili_thumb_{digest}.jpg')
            if not os.path.exists(tmp):
                if os.path.basename(sf).lower() == 'cover.jpg':
                    tmp = sf
                else:
                    fp.extract_thumbnail(
                        sf,
                        tmp,
                        size=96,
                        should_continue=lambda: gen == getattr(self, '_thumb_gen', 0)
                    )
            if self._closing or gen != getattr(self, '_thumb_gen', 0):
                if not self._closing:
                    self._safe_after(0, lambda v=v: self._thumb_cache.pop(v.get('_iid'), None))
                return
            if os.path.exists(tmp):
                if not self._closing:
                    self._safe_after(0, lambda: self._set_thumb(v, tmp))
            else:
                if not self._closing:
                    self._safe_after(0, lambda v=v: self._thumb_cache.pop(v.get('_iid'), None))
        except Exception:
            if not self._closing:
                self._safe_after(0, lambda v=v: self._thumb_cache.pop(v.get('_iid'), None))

    def _set_thumb(self, v, path):
        if self._closing:
            return
        try:
            from PIL import Image, ImageTk
            img = Image.open(path)
            img = img.resize((64, 36), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            iid = v.get('_iid')
            if iid and self.tree.exists(iid):
                self.tree.item(iid, image=photo)
            self._thumb_cache[v.get('_iid')] = photo
        except Exception:
            self._thumb_cache.pop(v.get('_iid'), None)

    # ── 处理 ──

    def _start_processing(self):
        if self._processing:
            return

        checked_videos = self._selected_videos()
        if not checked_videos:
            messagebox.showwarning('提示', '请先在列表中选择要处理的视频。')
            return

        self._processing = True
        self.process_btn.configure(state=tk.DISABLED)
        self.cancel_btn.configure(state=tk.NORMAL)
        self.progress.configure(mode='indeterminate')
        self.progress.start()
        self.status_var.set(f'正在处理 {len(checked_videos)} 个视频...')

        def do_process():
            total = len(checked_videos)
            succeeded = 0
            skipped = 0
            failed = 0
            processed = 0
            cancelled = False
            for idx, v in enumerate(checked_videos):
                if not self._processing:
                    cancelled = True
                    break
                try:
                    if v['type'] == 'win':
                        results = fp.Win_File(v['path'])
                    else:
                        c_dir = v['c_dir']
                        results = fp.Phone_File(
                            v['path'],
                            [c_dir],
                            collection_overrides={c_dir: v.get('collection')},
                            file_name_overrides={c_dir: v.get('title')}
                        )
                    for r in results:
                        processed += 1
                        if r['status'] == 'success':
                            succeeded += 1
                        elif r['status'] == 'skipped':
                            skipped += 1
                        else:
                            failed += 1
                except Exception as e:
                    failed += 1
                    self._safe_after(0, lambda e=e: (
                        self.status_var.set(f'处理出错: {e}')
                    ))
                if not self._processing:
                    cancelled = True
                self._safe_after(0, lambda i=idx+1, t=total: (
                    self.status_var.set(f'正在处理... ({i}/{t})')
                ))
            self._safe_after(0, lambda s=succeeded, k=skipped, f=failed, t=total, c=cancelled:
                             self._done(s, k, f, t, c))

        threading.Thread(target=do_process, daemon=True).start()

    def _cancel(self):
        self._processing = False
        self.cancel_btn.configure(state=tk.DISABLED)
        self.progress.stop()
        self.progress.configure(mode='determinate', value=0)
        self.status_var.set('正在取消...（当前任务完成后停止）')

    def _done(self, succeeded=0, skipped=0, failed=0, total=0, cancelled=False):
        self._processing = False
        self.progress.stop()
        self.progress.configure(mode='determinate', value=100)
        self.cancel_btn.configure(state=tk.DISABLED)
        self._update_process_btn()

        if cancelled:
            self.status_var.set(
                f'已取消：成功 {succeeded}，跳过 {skipped}，失败 {failed}'
            )
            messagebox.showinfo(
                '取消',
                f'处理已取消。\n成功 {succeeded} 个，跳过 {skipped} 个，失败 {failed} 个。'
            )
        elif failed > 0:
            self.status_var.set(f'部分失败：成功 {succeeded}，跳过 {skipped}，失败 {failed}')
            messagebox.showwarning(
                '部分失败',
                f'成功 {succeeded} 个，跳过 {skipped} 个，失败 {failed} 个。'
            )
        elif skipped > 0:
            self.status_var.set(f'处理完成：成功 {succeeded}，跳过 {skipped}')
            messagebox.showinfo('完成', f'成功 {succeeded} 个，跳过 {skipped} 个。')
        else:
            self.status_var.set(f'处理完成：成功 {succeeded}/{total}')
            messagebox.showinfo('完成', f'全部 {succeeded} 个视频处理完成。')

    def _on_close(self):
        self._closing = True
        self._processing = False
        self._scan_gen += 1
        self._duration_gen += 1
        self._thumb_gen += 1
        if self._scroll_after is not None:
            try:
                self.root.after_cancel(self._scroll_after)
            except (ValueError, tk.TclError):
                pass
            self._scroll_after = None
        self._shutdown_pool('_thumb_pool')
        self._shutdown_pool('_duration_pool')
        try:
            self.progress.stop()
        except tk.TclError:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
