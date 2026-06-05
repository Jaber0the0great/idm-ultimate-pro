import sys
import os
import subprocess
import requests
import yt_dlp
import time
import av
import re
import urllib.parse
import traceback
import mimetypes
import threading
from PyQt6.QtCore import QThread, pyqtSignal, QWaitCondition, QMutex
from config import clean_ansi

class UpdateWorker(QThread):
    finished = pyqtSignal(bool, str)
    def run(self):
        try:
            import urllib.request
            import zipfile
            import io
            import shutil
            
            # AppData updates path
            from config import CONFIG_DIR
            updates_dir = os.path.join(CONFIG_DIR, "updates")
            os.makedirs(updates_dir, exist_ok=True)
            
            url = "https://github.com/yt-dlp/yt-dlp/archive/refs/heads/master.zip"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as response:
                zip_data = response.read()
                
            # Create a temporary directory or directly clean/extract
            temp_extract_dir = os.path.join(updates_dir, "temp_yt_dlp")
            if os.path.exists(temp_extract_dir):
                shutil.rmtree(temp_extract_dir, ignore_errors=True)
            os.makedirs(temp_extract_dir, exist_ok=True)
            
            z = zipfile.ZipFile(io.BytesIO(zip_data))
            for member in z.namelist():
                if "yt_dlp/" in member:
                    parts = member.split("yt_dlp/", 1)
                    relative_path = parts[1]
                    if relative_path:
                        target_file = os.path.join(temp_extract_dir, relative_path)
                        os.makedirs(os.path.dirname(target_file), exist_ok=True)
                        if not member.endswith('/'):
                            with z.open(member) as source, open(target_file, 'wb') as dest:
                                shutil.copyfileobj(source, dest)
                                
            # If extraction succeeded, move to final target directory
            final_yt_dlp_dir = os.path.join(updates_dir, "yt_dlp")
            if os.path.exists(final_yt_dlp_dir):
                shutil.rmtree(final_yt_dlp_dir, ignore_errors=True)
                
            # Move temp folder to final folder
            shutil.move(temp_extract_dir, final_yt_dlp_dir)
            
            # Prepend to path if not already there
            if updates_dir not in sys.path:
                sys.path.insert(0, updates_dir)
                
            # Unload any previously loaded yt_dlp modules so that they are reloaded fresh
            for mod in list(sys.modules.keys()):
                if mod.startswith("yt_dlp"):
                    del sys.modules[mod]
                    
            self.finished.emit(True, "YouTube engine synchronized successfully!")
        except Exception as e:
            self.finished.emit(False, f"Update failed: {str(e)}")

class UniversalWorker(QThread):
    progress_changed = pyqtSignal(int)
    status_changed = pyqtSignal(str)
    size_info_changed = pyqtSignal(str, str, str)
    stats_updated = pyqtSignal(str)
    finished = pyqtSignal(bool, str, str, int, str)

    def __init__(self, task_id, url, save_path, mode="Direct", yt_opts=None, speed_limit=0, max_connections=8, proxy=None):
        super().__init__()
        self.task_id = task_id; self.url = url; self.save_path = save_path; self.mode = mode
        self.yt_opts = yt_opts or {}; self._is_cancelled = False; self._is_paused = False
        self.mutex = QMutex(); self.pause_cond = QWaitCondition(); self.start_time = 0
        self.speed_limit = speed_limit
        self.max_connections = max_connections
        self.num_threads = max_connections
        self.proxy = proxy
        self.temp_dir = os.path.join(self.save_path, ".temp", self.task_id)
        self.total_active_time = 0
        self.last_active_start = 0

    def finalize_active_time(self):
        if not self._is_paused and self.last_active_start > 0:
            self.total_active_time += time.time() - self.last_active_start
            self._is_paused = True

    def get_avg_speed(self, bytes_downloaded):
        duration = self.total_active_time
        if duration <= 0:
            duration = 0.1
        avg_speed_val = bytes_downloaded / duration
        if avg_speed_val > 1e6:
            return f"{avg_speed_val/1e6:.2f} MB/s"
        elif avg_speed_val > 1e3:
            return f"{avg_speed_val/1e3:.2f} KB/s"
        else:
            return f"{avg_speed_val:.2f} B/s"

    def pause(self):
        self._is_paused = True
        if self.last_active_start > 0:
            self.total_active_time += time.time() - self.last_active_start
            
    def resume(self):
        self._is_paused = False; self.last_active_start = time.time(); self.pause_cond.wakeAll()
        
    def cancel(self): self._is_cancelled = True; self.resume()

    def get_safe_path(self, path):
        if not os.path.exists(path): return path
        base, ext = os.path.splitext(path); c = 1
        while os.path.exists(f"{base} ({c}){ext}"): c += 1
        return f"{base} ({c}){ext}"

    def run(self):
        self.start_time = time.time()
        self.last_active_start = time.time()
        self.total_active_time = 0
        temp_parent = os.path.join(self.save_path, ".temp")
        os.makedirs(temp_parent, exist_ok=True)
        if os.name == 'nt':
            import ctypes
            try: ctypes.windll.kernel32.SetFileAttributesW(temp_parent, 2)
            except: pass
        os.makedirs(self.temp_dir, exist_ok=True)
        if self.mode == "YouTube": self.run_youtube()
        else: self.run_direct()

    def run_direct(self):
        response = None
        try:
            url = self.url; session = requests.Session()
            session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
            if self.proxy:
                session.proxies = {'http': self.proxy, 'https': self.proxy}
            
            # Google Drive specialized handling
            final_url = url
            if "drive.google.com" in url:
                file_id_match = re.search(r'[-\w]{25,}', url)
                if file_id_match:
                    fid = file_id_match.group()
                    res = session.get(f"https://drive.google.com/uc?export=download&id={fid}", stream=True)
                    if 'text/html' in res.headers.get('Content-Type', ''):
                        try:
                            action = re.search(r'action="([^"]+)"', res.text).group(1)
                            params = {n: v for n, v in re.findall(r'name="([^"]+)"\s+value="([^"]*)"', res.text)}
                            res2 = session.get(action, params=params, stream=True)
                            final_url = res2.url
                            response = res2
                        except Exception:
                            final_url = res.url
                            response = res
                    else:
                        final_url = res.url
                        response = res
            
            if response is None: 
                response = session.get(url, stream=True, timeout=25, allow_redirects=True)
                final_url = response.url
            response.raise_for_status()
            
            # --- Robust Filename Extraction ---
            filename = ""
            cd = response.headers.get('content-disposition')
            if cd:
                if 'filename*=' in cd:
                    m = re.search(r"filename\*\s*=\s*UTF-8''(.+)", cd, re.I)
                    if m: filename = urllib.parse.unquote(m.group(1))
                elif 'filename=' in cd:
                    m = re.findall('filename="?([^";]+)"?', cd)
                    if m: filename = m[0]
            
            if not filename:
                # Fallback to URL path
                parsed_url = urllib.parse.urlparse(response.url)
                filename = os.path.basename(parsed_url.path)
            
            if not filename or "." not in filename:
                base = filename if filename else "downloaded_file"
                # Try to guess extension from content-type
                ct = response.headers.get('content-type', '').split(';')[0].lower().strip()
                ext_map = {
                    'text/html': '.html', 'image/jpeg': '.jpg', 'image/png': '.png', 
                    'video/mp4': '.mp4', 'application/pdf': '.pdf', 'application/zip': '.zip',
                    'audio/mpeg': '.mp3', 'image/gif': '.gif', 'application/json': '.json'
                }
                ext = ext_map.get(ct, ".dat")
                filename = base + ext
            
            filename = urllib.parse.unquote(filename)
            filename = re.sub(r'[\\/*?:"<>|]', "", filename)
            
            path = self.get_safe_path(os.path.join(self.save_path, filename))
            total_size = int(response.headers.get('content-length', 0))
            
            # Probing and test range support
            range_supported = False
            self.num_threads = self.max_connections
            
            if total_size > 0 and self.max_connections > 1:
                test_threads = self.max_connections
                while test_threads >= 4:
                    success = False
                    for attempt in range(2):
                        if self._is_cancelled:
                            break
                        self.status_changed.emit(f"Status: Probing {test_threads} connections (Attempt {attempt+1}/2)...")
                        
                        probe_threads = []
                        probe_results = [False] * test_threads
                        
                        def probe_conn(idx):
                            try:
                                with session.get(final_url, headers={'Range': 'bytes=0-0'}, stream=True, timeout=8) as r:
                                    if r.status_code == 206:
                                        probe_results[idx] = True
                            except:
                                pass
                                
                        for j in range(test_threads):
                            t = threading.Thread(target=probe_conn, args=(j,))
                            t.daemon = True
                            probe_threads.append(t)
                            t.start()
                            
                        for t in probe_threads:
                            t.join()
                            
                        if all(probe_results):
                            success = True
                            break
                        else:
                            time.sleep(0.5)
                            
                    if success:
                        range_supported = True
                        self.num_threads = test_threads
                        break
                    else:
                        test_threads = test_threads // 2
                
                if not range_supported:
                    self.status_changed.emit("Status: Probing 1 connection...")
                    try:
                        probe = session.get(final_url, headers={'Range': 'bytes=0-0'}, stream=True, timeout=10)
                        if probe.status_code == 206:
                            range_supported = True
                            self.num_threads = 1
                        probe.close()
                    except:
                        pass
            elif total_size > 0:
                self.status_changed.emit("Status: Probing 1 connection...")
                try:
                    probe = session.get(final_url, headers={'Range': 'bytes=0-0'}, stream=True, timeout=10)
                    if probe.status_code == 206:
                        range_supported = True
                        self.num_threads = 1
                    probe.close()
                except:
                    pass

            if range_supported:
                # Close the original response to free resources since we will download using threads
                response.close()
                
                num_threads = self.num_threads
                segment_size = total_size // num_threads
                ranges = []
                for i in range(num_threads):
                    start = i * segment_size
                    end = (i + 1) * segment_size - 1 if i < num_threads - 1 else total_size - 1
                    ranges.append((start, end))
                
                self.seg_progress = [0] * num_threads
                self.thread_errors = [None] * num_threads
                
                # Pre-calculate already downloaded progress from existing files for resuming
                for i in range(num_threads):
                    part_path = os.path.join(self.temp_dir, f"part{i}")
                    if os.path.exists(part_path):
                        self.seg_progress[i] = os.path.getsize(part_path)
                
                def download_segment_thread(seg_idx, start, end):
                    part_path = os.path.join(self.temp_dir, f"part{seg_idx}")
                    expected_size = (end - start) + 1
                    
                    max_thread_retries = 3
                    thread_attempt = 0
                    
                    while thread_attempt < max_thread_retries:
                        if self._is_cancelled:
                            return
                            
                        downloaded = 0
                        if os.path.exists(part_path):
                            downloaded = os.path.getsize(part_path)
                            
                        if downloaded >= expected_size:
                            self.seg_progress[seg_idx] = downloaded
                            return
                            
                        actual_start = start + downloaded
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                            'Range': f'bytes={actual_start}-{end}'
                        }
                        try:
                            res = session.get(final_url, headers=headers, stream=True, timeout=15)
                            res.raise_for_status()
                            
                            mode = 'ab' if downloaded > 0 else 'wb'
                            with open(part_path, mode) as f:
                                for chunk in res.iter_content(chunk_size=1024*64):
                                    if self._is_cancelled:
                                        break
                                    
                                    self.mutex.lock()
                                    if self._is_paused:
                                        self.pause_cond.wait(self.mutex)
                                    self.mutex.unlock()
                                    
                                    if self._is_cancelled:
                                        break
                                    
                                    if chunk:
                                        chunk_start_t = time.time()
                                        f.write(chunk)
                                        downloaded += len(chunk)
                                        self.seg_progress[seg_idx] = downloaded
                                        
                                        # Speed Limiter
                                        if self.speed_limit > 0:
                                            thread_limit_bps = (self.speed_limit * 1024.0) / num_threads
                                            expected_time = len(chunk) / thread_limit_bps
                                            elapsed = time.time() - chunk_start_t
                                            if elapsed < expected_time:
                                                time.sleep(expected_time - elapsed)
                                                
                            if not self._is_cancelled and not self._is_paused:
                                current_size = os.path.getsize(part_path)
                                if current_size >= expected_size:
                                    return
                                else:
                                    thread_attempt += 1
                                    time.sleep(1.0)
                            else:
                                return
                        except Exception as e:
                            thread_attempt += 1
                            if thread_attempt >= max_thread_retries:
                                self.thread_errors[seg_idx] = str(e)
                                return
                            time.sleep(1.5)

                # Spawn threads
                threads = []
                for i in range(num_threads):
                    start, end = ranges[i]
                    t = threading.Thread(target=download_segment_thread, args=(i, start, end))
                    t.daemon = True
                    threads.append(t)
                    t.start()
                
                # Main thread monitoring loop
                last_t = time.time()
                last_d = sum(self.seg_progress)
                
                while any(t.is_alive() for t in threads):
                    if self._is_cancelled:
                        break
                    
                    if any(err is not None for err in self.thread_errors):
                        self._is_cancelled = True
                        break
                        
                    time.sleep(0.5)
                    
                    curr_t = time.time()
                    if curr_t - last_t >= 1.0:
                        down = sum(self.seg_progress)
                        speed = (down - last_d) / (curr_t - last_t)
                        self.stats_updated.emit(f"SPEED: {self.num_threads}x {speed/1e6:.2f} MB/s | ELAPSED: {int(curr_t - self.start_time)}s")
                        last_t, last_d = curr_t, down
                        
                        self.progress_changed.emit(int((down / total_size) * 100))
                        self.size_info_changed.emit(f"{down/1e6:.2f}MB", f"{total_size/1e6:.2f}MB", f"{(total_size-down)/1e6:.2f}MB")
                
                for t in threads:
                    t.join()
                
                if self._is_cancelled:
                    if any(err is not None for err in self.thread_errors):
                        error_msg = next(err for err in self.thread_errors if err is not None)
                        raise Exception(error_msg)
                    raise Exception("Cancelled")
                
                # Merge segments
                self.status_changed.emit("Status: Merging segments...")
                with open(path, 'wb') as final_f:
                    for i in range(num_threads):
                        part_path = os.path.join(self.temp_dir, f"part{i}")
                        with open(part_path, 'rb') as part_f:
                            while True:
                                chunk = part_f.read(1024*1024*4)
                                if not chunk:
                                    break
                                final_f.write(chunk)
                import shutil
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                
                self.finalize_active_time()
                self.finished.emit(True, path, f"SUCCESS: {total_size/1e6:.2f} MB", int(self.total_active_time), self.get_avg_speed(total_size))
            else:
                if self._is_cancelled:
                    raise Exception("Cancelled")
                # Fallback to single connection download using temp directory
                downloaded = 0
                part_path = os.path.join(self.temp_dir, "part")
                mode = 'wb'
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                
                if os.path.exists(part_path) and total_size > 0:
                    downloaded = os.path.getsize(part_path)
                    if downloaded < total_size:
                        headers['Range'] = f'bytes={downloaded}-'
                        mode = 'ab'
                    elif downloaded == total_size:
                        try:
                            if os.path.exists(path): os.remove(path)
                            os.rename(part_path, path)
                            import shutil
                            shutil.rmtree(self.temp_dir, ignore_errors=True)
                        except: pass
                        self.finalize_active_time()
                        self.finished.emit(True, path, f"SUCCESS: {downloaded/1e6:.2f} MB", int(self.total_active_time), self.get_avg_speed(downloaded))
                        return
                
                response = session.get(final_url, headers=headers, stream=True, timeout=25)
                response.raise_for_status()
                
                down = downloaded; last_t = self.start_time; last_d = downloaded
                cancelled = False
                with open(part_path, mode) as f:
                    for chunk in response.iter_content(chunk_size=1024*512):
                        if self._is_cancelled:
                            cancelled = True
                            break
                        
                        self.mutex.lock()
                        if self._is_paused:
                            self.pause_cond.wait(self.mutex)
                        self.mutex.unlock()
                        
                        if self._is_cancelled:
                            cancelled = True
                            break
                        
                        if chunk:
                            chunk_start_t = time.time()
                            f.write(chunk); down += len(chunk); curr_t = time.time()
                            if curr_t - last_t >= 1.0:
                                speed = (down - last_d)/(curr_t - last_t)
                                self.stats_updated.emit(f"SPEED: 1x {speed/1e6:.2f} MB/s | ELAPSED: {int(curr_t - self.start_time)}s")
                                last_t, last_d = curr_t, down
                            if total_size > 0:
                                self.progress_changed.emit(int((down/total_size)*100))
                                self.size_info_changed.emit(f"{down/1e6:.2f}MB", f"{total_size/1e6:.2f}MB", f"{(total_size-down)/1e6:.2f}MB")
                            
                            # Speed Limiter
                            if self.speed_limit > 0:
                                limit_bps = self.speed_limit * 1024.0
                                expected_time = len(chunk) / limit_bps
                                elapsed = time.time() - chunk_start_t
                                if elapsed < expected_time:
                                    time.sleep(expected_time - elapsed)
                
                if cancelled or self._is_cancelled:
                    raise Exception("Cancelled")
                
                try:
                    if os.path.exists(path): os.remove(path)
                    os.rename(part_path, path)
                    import shutil
                    shutil.rmtree(self.temp_dir, ignore_errors=True)
                except: pass
                self.finalize_active_time()
                self.finished.emit(True, path, f"SUCCESS: {down/1e6:.2f} MB", int(self.total_active_time), self.get_avg_speed(down))
        except Exception as e:
            self.finalize_active_time()
            err_msg = str(e)
            if self._is_cancelled or "Cancelled" in err_msg:
                self.finished.emit(False, "Cancelled", "Cancelled by user", int(self.total_active_time), "0.00 MB/s")
            else:
                traceback.print_exc()
                self.finished.emit(False, err_msg, "", int(self.total_active_time), "0.00 MB/s")

    def convert_standalone(self, input_path, target_ext, final_name):
        """Ultra-Stable Python Transcoder with Original Filename Support"""
        input_container = None; output_container = None
        target_ext = target_ext.lower()
        # Clean final name from illegal characters
        final_name = re.sub(r'[\\/*?:"<>|]', "", final_name)
        output_file = os.path.join(self.save_path, f"{final_name}.{target_ext}")
        output_file = self.get_safe_path(output_file)
        
        tmp_output = os.path.join(os.path.dirname(input_path), f"conv_{int(time.time())}.{target_ext}")
        
        try:
            self.status_changed.emit(f"Status: Converting to {target_ext.upper()}...")
            input_container = av.open(input_path)
            output_container = av.open(tmp_output, mode='w')
            
            v_codec = 'h264' if target_ext == 'mp4' else None
            a_codec = 'libmp3lame' if target_ext == 'mp3' else 'aac'
            
            streams = []
            for stream in input_container.streams:
                if stream.type == 'video' and v_codec:
                    out = output_container.add_stream(v_codec)
                    out.width, out.height, out.pix_fmt = stream.width, stream.height, 'yuv420p'
                    streams.append((stream, out))
                elif stream.type == 'audio':
                    out = output_container.add_stream(a_codec); out.rate = stream.rate
                    # Fix for layout/channels attribute error
                    try: out.layout = stream.layout
                    except: 
                        try: out.channels = stream.channels
                        except: pass
                    streams.append((stream, out))

            if not streams: raise Exception("No valid streams")

            for packet in input_container.demux([s[0] for s in streams]):
                if self._is_cancelled: break
                for frame in packet.decode():
                    idx = next(i for i, v in enumerate(streams) if v[0].index == packet.stream.index)
                    in_stream, out_stream = streams[idx]
                    if in_stream.type == 'video':
                        try: frame = frame.reformat(format='yuv420p')
                        except: pass
                    for out_packet in out_stream.encode(frame): output_container.mux(out_packet)

            for _, out_stream in streams:
                try:
                    for out_packet in out_stream.encode(): output_container.mux(out_packet)
                except: pass

            output_container.close(); input_container.close()
            os.rename(tmp_output, output_file)
            try: os.remove(input_path)
            except: pass
            return output_file
        except Exception as e:
            if output_container: output_container.close()
            if input_container: input_container.close()
            if os.path.exists(tmp_output): os.remove(tmp_output)
            self.status_changed.emit(f"Warning: Transcode failed ({str(e)[:10]})")
            # If conversion fails, just rename the original to the proper title
            fallback = os.path.join(self.save_path, f"{final_name}{os.path.splitext(input_path)[1]}")
            fallback = self.get_safe_path(fallback)
            os.rename(input_path, fallback)
            return fallback

    def run_youtube(self):
        try:
            def hook(d):
                if self._is_cancelled: raise Exception("STOP")
                # Add Pause Logic for YouTube
                self.mutex.lock()
                if self._is_paused: self.pause_cond.wait(self.mutex)
                self.mutex.unlock()
                
                if d['status'] == 'downloading':
                    p = clean_ansi(d.get('_percent_str', '0%')).replace('%','').strip()
                    try: self.progress_changed.emit(int(float(p)))
                    except: pass
                    down, total = d.get('downloaded_bytes', 0), d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    self.stats_updated.emit(f"SPEED: {clean_ansi(d.get('_speed_str', 'N/A'))} | ELAPSED: {int(time.time() - self.start_time)}s")
                    if total > 0: self.size_info_changed.emit(f"{down/1e6:.2f}MB", f"{total/1e6:.2f}MB", f"{(total-down)/1e6:.2f}MB")
                    self.status_changed.emit("Status: Downloading...")

            # Use stable task_id-based temp name so downloads can resume across restarts
            temp_dl_name = f"dl_temp_{self.task_id}"
            ydl_opts = {
                'progress_hooks': [hook], 'quiet': True, 'no_warnings': True,
                'outtmpl': os.path.join(self.temp_dir, f'{temp_dl_name}.%(ext)s'),
                'nocheckcertificate': True, 'retries': 3, 'overwrites': True, 'noplaylist': True,
            }
            if self.speed_limit > 0:
                ydl_opts['ratelimit'] = self.speed_limit * 1024
            if self.proxy:
                ydl_opts['proxy'] = self.proxy
            
            dt, target_ext, q = self.yt_opts.get('type', 'Video'), self.yt_opts.get('ext', 'mp4'), self.yt_opts.get('quality', '1080p')
            qv = q.replace('p', '').replace('4K', '2160')

            # Strategy: Request BEST pre-merged file first to avoid FFmpeg dependency
            if dt == 'Audio': ydl_opts['format'] = 'bestaudio/best'
            else: ydl_opts['format'] = f'best[height<={qv}][ext=mp4]/best[height<={qv}]/best'

            def attempt_download(use_cookies=False):
                opts = ydl_opts.copy()
                if use_cookies: opts['cookiesfrombrowser'] = ('chrome', None, None, None)
                self.status_changed.emit("Status: Authenticating...")
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(self.url, download=True)
                    title = info.get('title', 'video')
                    dl_path = ydl.prepare_filename(info)
                    if not os.path.exists(dl_path):
                        base = os.path.splitext(dl_path)[0]
                        for e in ['.mp4', '.webm', '.m4a', '.mp3', '.3gp']:
                            if os.path.exists(base + e): dl_path = base + e; break
                
                # TRANSCODE or RENAME based on user choice
                if target_ext == 'original' or dl_path.lower().endswith(f".{target_ext.lower()}"):
                    final_path = os.path.join(self.save_path, f"{re.sub(r'[\\\\/*?:"<>|]', '', title)}{os.path.splitext(dl_path)[1]}")
                    final_path = self.get_safe_path(final_path)
                    os.rename(dl_path, final_path); return final_path
                else:
                    return self.convert_standalone(dl_path, target_ext, title)

            try: final_path = attempt_download(False)
            except Exception: final_path = attempt_download(True)
            
            # Clean up YouTube temp files folder
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            
            size_bytes = os.path.getsize(final_path) if os.path.exists(final_path) else 0
            self.finalize_active_time()
            self.finished.emit(True, final_path, f"SUCCESS: {size_bytes/1e6:.2f} MB", int(self.total_active_time), self.get_avg_speed(size_bytes))
        except Exception as e:
            self.finalize_active_time()
            err_msg = str(e)
            if self._is_cancelled or "STOP" in err_msg or "Cancelled" in err_msg:
                self.finished.emit(False, "Cancelled", "Cancelled by user", int(self.total_active_time), "0.00 MB/s")
            else:
                traceback.print_exc()
                self.finished.emit(False, err_msg, "", int(self.total_active_time), "0.00 MB/s")

class FormatFetcher(QThread):
    formats_fetched = pyqtSignal(list, list)
    error_occurred = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            ydl_opts = {'quiet': True, 'nocheckcertificate': True, 'noplaylist': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                formats = info.get('formats', [])
                
                resolutions = set()
                for f in formats:
                    if f.get('vcodec') != 'none' and f.get('height'):
                        h = f.get('height')
                        resolutions.add(f"{h}p")
                
                sorted_res = sorted(list(resolutions), key=lambda x: int(x.replace('p', '')), reverse=True)
                if not sorted_res:
                    sorted_res = ["1080p", "720p", "480p", "360p"]
                
                audio_rates = set()
                for f in formats:
                    if f.get('acodec') != 'none' and f.get('abr'):
                        abr = int(f.get('abr'))
                        audio_rates.add(f"{abr}kbps")
                
                sorted_audio = sorted(list(audio_rates), key=lambda x: int(x.replace('kbps', '')), reverse=True)
                if not sorted_audio:
                    sorted_audio = ["320kbps", "192kbps", "128kbps"]
                
                self.formats_fetched.emit(sorted_res, sorted_audio)
        except Exception as e:
            self.error_occurred.emit(str(e))

class AppUpdateCheckWorker(QThread):
    # Emit (success, latest_version_tag, download_url, release_notes_or_error)
    finished = pyqtSignal(bool, str, str, str)

    def run(self):
        try:
            import urllib.request
            import json
            req = urllib.request.Request(
                "https://api.github.com/repos/Jaber0the0great/idm-ultimate-pro/releases/latest",
                headers={"User-Agent": "IDM-Ultimate-Pro-UpdateChecker"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                tag_name = str(data.get("tag_name") or "") # e.g. "v1.1" or "1.1"
                html_url = str(data.get("html_url") or "")
                body = str(data.get("body") or "") # Release notes
                # Find download url of the asset (.exe or setup.exe)
                download_url = html_url # Default fallback to release page
                assets = data.get("assets", [])
                for asset in assets:
                    name = str(asset.get("name") or "").lower()
                    if name.endswith(".exe"):
                        download_url = str(asset.get("browser_download_url") or html_url)
                        break
                self.finished.emit(True, tag_name, download_url, body)
        except Exception as e:
            self.finished.emit(False, "", "", str(e))

class AppUpdateDownloaderWorker(QThread):
    # Emit (progress_percentage, bytes_downloaded, total_bytes)
    progress = pyqtSignal(int, int, int)
    # Emit (success, file_path_or_error_msg)
    finished = pyqtSignal(bool, str)

    def __init__(self, download_url, save_path):
        super().__init__()
        self.download_url = download_url
        self.save_path = save_path
        self._is_cancelled = False

    def run(self):
        import urllib.request
        import time
        
        max_retries = 5
        retry_delay = 3 # seconds
        downloaded = 0
        total_size = 0
        
        headers = {"User-Agent": "IDM-Ultimate-Pro-Updater"}
        
        for attempt in range(max_retries):
            if self._is_cancelled:
                self.finished.emit(False, "Cancelled")
                return
                
            try:
                req = urllib.request.Request(self.download_url, headers=headers)
                
                # Resumable range request if file partially exists
                if downloaded > 0:
                    req.add_header("Range", f"bytes={downloaded}-")
                    mode = "ab"
                else:
                    mode = "wb"
                    
                with urllib.request.urlopen(req, timeout=15) as response:
                    cl = response.headers.get('content-length')
                    if cl:
                        if downloaded > 0:
                            total_size = downloaded + int(cl)
                        else:
                            total_size = int(cl)
                    
                    with open(self.save_path, mode) as f:
                        while not self._is_cancelled:
                            chunk = response.read(1024 * 64)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            percent = 0
                            if total_size > 0:
                                percent = int((downloaded / total_size) * 100)
                            self.progress.emit(percent, downloaded, total_size)
                            
                    if not self._is_cancelled:
                        self.finished.emit(True, self.save_path)
                        return
                        
            except Exception as e:
                # If we still have retries remaining, wait and retry
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    self.finished.emit(False, str(e))
                    return


