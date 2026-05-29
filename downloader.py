import os
import time
import requests
from PyQt6.QtCore import QRunnable, QObject, pyqtSignal, QThreadPool

class DownloadSignals(QObject):
    # Signals for communicating worker status back to the main thread
    started = pyqtSignal(int)          # index
    progress = pyqtSignal(int, int, int) # index, downloaded_bytes, total_bytes
    completed = pyqtSignal(int, str, int) # index, filename, size_bytes
    failed = pyqtSignal(int, str, int) # index, error_message, status_code
    status_msg = pyqtSignal(int, str)  # index, status text

class ImageDownloadWorker(QRunnable):
    def __init__(self, index, url, save_path, headers, manager):
        super().__init__()
        self.index = index
        self.url = url
        self.save_path = save_path
        self.headers = headers
        self.manager = manager
        self.signals = DownloadSignals()
        
        # Track speed locally
        self.downloaded_bytes = 0
        self.total_bytes = 0

    def run(self):
        # 1. Check if cancelled before starting
        if self.manager.is_cancelled or self.index in self.manager.cancelled_indices:
            self.signals.failed.emit(self.index, "Cancelled", -99)
            return

        self.signals.started.emit(self.index)
        part_path = self.save_path + ".tmp"
        
        max_retries = 4
        retry_delay = 1.5
        
        for attempt in range(max_retries):
            # Check pause/cancel states
            while self.manager.is_paused and not self.manager.is_cancelled:
                time.sleep(0.2)
                
            if self.manager.is_cancelled or self.index in self.manager.cancelled_indices:
                self.signals.failed.emit(self.index, "Cancelled", -99)
                return

            if attempt > 0:
                self.signals.status_msg.emit(self.index, f"Retry {attempt}/{max_retries-1} in {retry_delay:.1f}s...")
                t_end = time.time() + retry_delay
                while time.time() < t_end:
                    if self.manager.is_cancelled or self.index in self.manager.cancelled_indices:
                        self.signals.failed.emit(self.index, "Cancelled", -99)
                        return
                    time.sleep(0.1)
                retry_delay *= 2.0
                
            response = None
            try:
                self.signals.status_msg.emit(self.index, "Connecting...")
                # Use manager's shared keep-alive session to avoid triggering SSL resets under high concurrency
                response = self.manager.session.get(self.url, headers=self.headers, stream=True, timeout=15)
                
                # Check status code
                if response.status_code == 404:
                    if self.manager.is_cancelled or self.index in self.manager.cancelled_indices:
                        self.signals.failed.emit(self.index, "Cancelled", -99)
                    else:
                        self.signals.failed.emit(self.index, "404 Not Found", 404)
                    return
                
                if response.status_code != 200:
                    response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                self.total_bytes = total_size
                
                self.signals.status_msg.emit(self.index, "Downloading...")
                downloaded = 0
                
                with open(part_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=16384):
                        while self.manager.is_paused and not self.manager.is_cancelled:
                            time.sleep(0.2)
                            
                        if self.manager.is_cancelled or self.index in self.manager.cancelled_indices:
                            response.close()
                            f.close()
                            if os.path.exists(part_path):
                                try:
                                    os.remove(part_path)
                                except Exception:
                                    pass
                            self.signals.failed.emit(self.index, "Cancelled", -99)
                            return
                            
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            self.downloaded_bytes = downloaded
                            self.signals.progress.emit(self.index, downloaded, total_size)
                
                # Successful completion: Rename to final filename
                if os.path.exists(part_path):
                    if os.path.exists(self.save_path):
                        try:
                            os.remove(self.save_path)
                        except Exception:
                            pass
                    os.rename(part_path, self.save_path)
                
                if self.manager.is_cancelled or self.index in self.manager.cancelled_indices:
                    self.signals.failed.emit(self.index, "Cancelled", -99)
                else:
                    self.signals.completed.emit(self.index, os.path.basename(self.save_path), downloaded)
                return # Exits thread after success
                
            except Exception as e:
                # Close streaming response safely
                if response is not None:
                    try:
                        response.close()
                    except Exception:
                        pass
                
                # Cleanup temp file on failure of this attempt
                if os.path.exists(part_path):
                    try:
                        os.remove(part_path)
                    except Exception:
                        pass
                
                # If this is the last attempt, emit failure signal
                if attempt == max_retries - 1:
                    if self.manager.is_cancelled or self.index in self.manager.cancelled_indices:
                        self.signals.failed.emit(self.index, "Cancelled", -99)
                    else:
                        err_type = "Network error" if isinstance(e, requests.exceptions.RequestException) else "Error"
                        status_code = getattr(e, 'response', None) and getattr(e.response, 'status_code', 0) or 0
                        self.signals.failed.emit(self.index, f"{err_type}: {str(e)}", status_code)
                    return


class DownloadManager(QObject):
    # Signals for overall progress communication to UI
    worker_started = pyqtSignal(int)
    worker_progress = pyqtSignal(int, int, int)
    worker_completed = pyqtSignal(int, str, int)
    worker_failed = pyqtSignal(int, str, int)
    worker_status = pyqtSignal(int, str)
    
    overall_progress = pyqtSignal(int, int, float, float) # completed_count, total_count, speed (KB/s), eta (seconds)
    queue_finished = pyqtSignal(bool) # completed_successfully (all items checked/downloaded)
    log_msg = pyqtSignal(str, str) # category, message

    def __init__(self):
        super().__init__()
        self.thread_pool = QThreadPool.globalInstance()
        self.is_paused = False
        self.is_cancelled = False
        self.cancelled_indices = set()
        
        # Create requests Session with connection pool settings (thread-safe reuse)
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20,
            pool_maxsize=120,
            max_retries=0
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # State tracking
        self.url_template = ""
        self.url_padding = 0
        self.start_idx = 0
        self.end_idx = 0
        self.auto_stop_404 = True
        self.save_dir = ""
        self.headers = {}
        
        # Active and pending queues
        self.total_count = 0
        self.completed_count = 0
        self.failed_count = 0
        
        # Speed measurement
        self.total_downloaded = 0
        self.speed_history = []
        self.start_time = 0.0
        self.last_calc_time = 0.0
        self.bytes_since_last_calc = 0
        self.active_workers_map = {} # index -> Worker instance
        
        # 404 Sequence tracking for auto-stop
        self.successful_indices = set()
        self.failed_404_indices = set()
        self.sequence_ended = False
        self.consecutive_404_count = 0
        self.max_consecutive_404 = 5
        self.running_indices = set()
        self.scheduled_indices = set()
        self.concurrency_limit = 10
        self.has_finished_triggered = False

    def configure(self, url_template, start_idx, end_idx, save_dir, headers, concurrency, auto_stop_404):
        self.url_template = url_template
        self.start_idx = start_idx
        self.end_idx = end_idx
        self.save_dir = save_dir
        self.headers = headers
        self.concurrency_limit = concurrency
        self.auto_stop_404 = auto_stop_404
        
        self.thread_pool.setMaxThreadCount(concurrency)
        
        self.is_paused = False
        self.is_cancelled = False
        self.cancelled_indices.clear()
        
        # Reset counters
        self.completed_count = 0
        self.failed_count = 0
        self.consecutive_404_count = 0
        self.successful_indices.clear()
        self.failed_404_indices.clear()
        self.sequence_ended = False
        self.running_indices.clear()
        self.scheduled_indices.clear()
        self.active_workers_map.clear()
        self.total_downloaded = 0
        self.bytes_since_last_calc = 0
        self.has_finished_triggered = False
        
        # Calculate total images to download (if fixed end_idx)
        if self.end_idx >= self.start_idx:
            self.total_count = self.end_idx - self.start_idx + 1
        else:
            self.total_count = 0 # unknown

    def set_concurrency(self, val):
        self.concurrency_limit = val
        self.thread_pool.setMaxThreadCount(val)

    def start_download(self):
        self.is_paused = False
        self.is_cancelled = False
        self.start_time = time.time()
        self.last_calc_time = self.start_time
        self.bytes_since_last_calc = 0
        
        self.log_msg.emit("System", f"Starting bulk download. Concurrency limit: {self.concurrency_limit}")
        self.log_msg.emit("System", f"Saving images into: {self.save_dir}")
        os.makedirs(self.save_dir, exist_ok=True)
        
        # Start scheduling workers
        self.schedule_next_workers()

    def pause_download(self):
        self.is_paused = True
        self.log_msg.emit("Action", "Downloads paused.")

    def resume_download(self):
        self.is_paused = False
        self.log_msg.emit("Action", "Downloads resumed.")
        self.schedule_next_workers()

    def cancel_download(self):
        self.is_cancelled = True
        # Cancel all pending threads in pool
        self.thread_pool.clear()
        self.log_msg.emit("Action", "Cancelling all active downloads...")

    def check_and_cancel_excess_workers(self):
        if not self.auto_stop_404:
            return False
            
        if self.sequence_ended:
            return True
            
        max_success = max(self.successful_indices) if self.successful_indices else self.start_idx - 1
        
        # We look for any s > max_success such that s to s + max_consecutive_404 - 1 are all in failed_404_indices
        has_ended = False
        detected_end_idx = None
        
        for s in sorted(self.failed_404_indices):
            if s <= max_success:
                continue
            if all((s + i) in self.failed_404_indices for i in range(self.max_consecutive_404)):
                has_ended = True
                detected_end_idx = s - 1
                break
                
        if has_ended:
            self.sequence_ended = True
            self.log_msg.emit("System", f"Sequence end detected at index {detected_end_idx} (consecutive 404s starting at {detected_end_idx + 1}).")
            # Cancel any running/scheduled indices strictly greater than detected_end_idx
            cancelled_any = False
            for idx in list(self.running_indices):
                if idx > detected_end_idx:
                    self.cancelled_indices.add(idx)
                    cancelled_any = True
            if cancelled_any:
                self.log_msg.emit("System", f"Cancelled scheduled indices beyond {detected_end_idx}.")
            return True
        return False

    def schedule_next_workers(self):
        if not self.is_cancelled and not self.is_paused and not self.sequence_ended:
            # Check if we've completed all scheduled and running tasks
            current_active = len(self.running_indices)
            
            # Determine the maximum sequence number we can schedule up to
            next_to_schedule = []
            curr_idx = self.start_idx
            
            while len(self.running_indices) + len(next_to_schedule) < self.concurrency_limit:
                # Find next index in sequence that hasn't been scheduled
                found_unscheduled = False
                while True:
                    # If we have a fixed end, don't go beyond it
                    if self.end_idx >= self.start_idx and curr_idx > self.end_idx:
                        break
                    
                    # Check if we should stop scheduling because sequence has ended
                    if self.sequence_ended:
                        break
    
                    if curr_idx not in self.scheduled_indices:
                        found_unscheduled = True
                        break
                    curr_idx += 1
                
                if not found_unscheduled:
                    break
                    
                next_to_schedule.append(curr_idx)
                self.scheduled_indices.add(curr_idx)
                curr_idx += 1
    
            # Spawn workers
            for index in next_to_schedule:
                # Generate URL
                if hasattr(self, 'url_padding') and self.url_padding > 0:
                    formatted_idx = f"{index:0{self.url_padding}d}"
                else:
                    formatted_idx = str(index)
                url = self.url_template.replace("{}", formatted_idx)
                
                # File name creation
                ext = ".jpg"
                if ".png" in url.lower(): ext = ".png"
                elif ".jpeg" in url.lower(): ext = ".jpeg"
                elif ".webp" in url.lower(): ext = ".webp"
                
                file_name = f"{index}{ext}"
                save_path = os.path.join(self.save_dir, file_name)
                
                worker = ImageDownloadWorker(index, url, save_path, self.headers, self)
                
                # Connect signals
                worker.signals.started.connect(self.on_worker_started)
                worker.signals.progress.connect(self.on_worker_progress)
                worker.signals.completed.connect(self.on_worker_completed)
                worker.signals.failed.connect(self.on_worker_failed)
                worker.signals.status_msg.connect(self.on_worker_status)
                
                self.running_indices.add(index)
                self.active_workers_map[index] = worker
                
                # Submit to thread pool
                self.thread_pool.start(worker)
    
        # Check if we're completely done
        self.check_queue_status()

    def check_queue_status(self):
        has_finished = False
        
        # Check if all active downloads have stopped
        if len(self.running_indices) == 0:
            if self.auto_stop_404 and self.sequence_ended:
                has_finished = True
            elif self.end_idx >= self.start_idx:
                # Fixed range mode: all expected items must be completed or failed
                total_expected = self.end_idx - self.start_idx + 1
                total_done = self.completed_count + self.failed_count
                if total_done >= total_expected:
                    has_finished = True
            else:
                # Dynamic range without sequence end yet (should not happen if running_indices is empty,
                # unless we are paused or cancelled, but let's check)
                if not self.is_paused and not self.is_cancelled:
                    has_finished = True

        if self.is_cancelled and len(self.running_indices) == 0:
            has_finished = True

        if has_finished and not self.has_finished_triggered:
            self.has_finished_triggered = True
            completed_successfully = not self.is_cancelled
            self.queue_finished.emit(completed_successfully)
            if self.is_cancelled:
                self.log_msg.emit("System", "Download queue cancelled.")
            else:
                self.log_msg.emit("System", f"All downloads finished. Completed: {self.completed_count}, Failed/Skipped: {self.failed_count}")

    # --- Worker Callbacks ---
    
    def on_worker_started(self, index):
        self.worker_started.emit(index)
        # Log occasionally to prevent spam
        if index % 20 == 0:
            self.log_msg.emit("Download", f"Started downloading image index: {index}")

    def on_worker_progress(self, index, downloaded, total):
        self.worker_progress.emit(index, downloaded, total)
        self.bytes_since_last_calc += 16384 # 16KB chunk size approximation
        
        current_time = time.time()
        time_diff = current_time - self.last_calc_time
        if time_diff >= 0.5:
            speed = (self.bytes_since_last_calc / 1024.0) / time_diff
            
            self.speed_history.append(speed)
            if len(self.speed_history) > 10:
                self.speed_history.pop(0)
            avg_speed = sum(self.speed_history) / len(self.speed_history)
            
            eta = 0.0
            if self.end_idx >= self.start_idx:
                remaining_count = (self.end_idx - self.start_idx + 1) - (self.completed_count + self.failed_count)
                if avg_speed > 0 and remaining_count > 0:
                    approx_remaining_bytes = remaining_count * 150 * 1024
                    eta = approx_remaining_bytes / (avg_speed * 1024.0)
            
            self.overall_progress.emit(self.completed_count, self.total_count or (self.completed_count + self.failed_count), avg_speed, eta)
            
            self.bytes_since_last_calc = 0
            self.last_calc_time = current_time

    def on_worker_completed(self, index, filename, size_bytes):
        self.completed_count += 1
        self.total_downloaded += size_bytes
        self.successful_indices.add(index)
        
        # Reset 404 sequence tracker on success
        self.consecutive_404_count = 0
        
        if index in self.running_indices:
            self.running_indices.remove(index)
        if index in self.active_workers_map:
            del self.active_workers_map[index]

        self.worker_completed.emit(index, filename, size_bytes)
        self.log_msg.emit("Success", f"Image {index} downloaded successfully ({filename} - {size_bytes / 1024:.1f} KB)")
        
        # Check sequence end
        self.check_and_cancel_excess_workers()
        
        # Process next
        self.schedule_next_workers()

    def on_worker_failed(self, index, error_msg, status_code):
        if status_code == -99:
            # Quietly clean up cancelled index
            if index in self.running_indices:
                self.running_indices.remove(index)
            if index in self.active_workers_map:
                del self.active_workers_map[index]
            self.worker_failed.emit(index, error_msg, status_code)
            self.check_queue_status()
            return

        self.failed_count += 1
        
        # If it's a 404, record and recalculate consecutive 404s
        if status_code == 404:
            self.failed_404_indices.add(index)
            
            # Find the longest contiguous block of 404s after max_success
            max_success = max(self.successful_indices) if self.successful_indices else self.start_idx - 1
            failed_above = sorted([x for x in self.failed_404_indices if x > max_success])
            max_len = 0
            if failed_above:
                curr_len = 1
                max_len = 1
                for i in range(1, len(failed_above)):
                    if failed_above[i] == failed_above[i-1] + 1:
                        curr_len += 1
                    else:
                        curr_len = 1
                    if curr_len > max_len:
                        max_len = curr_len
            
            contiguous_404_count = max_len
            self.consecutive_404_count = contiguous_404_count
            self.log_msg.emit("Warning", f"Image {index} returned 404 Not Found. Consecutive 404s: {contiguous_404_count}/{self.max_consecutive_404}")
        else:
            self.log_msg.emit("Error", f"Image {index} failed: {error_msg}")
            
        if index in self.running_indices:
            self.running_indices.remove(index)
        if index in self.active_workers_map:
            del self.active_workers_map[index]

        self.worker_failed.emit(index, error_msg, status_code)
        
        # Check sequence end
        self.check_and_cancel_excess_workers()
        
        # Process next
        self.schedule_next_workers()

    def on_worker_status(self, index, status_text):
        self.worker_status.emit(index, status_text)
