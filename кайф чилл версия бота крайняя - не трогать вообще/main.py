import os
import threading
import time
import random
import ctypes
from ctypes import wintypes
import pygetwindow as gw
from PIL import ImageGrab
import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox
from pynput import keyboard
import json
import re
try:
    from interception import interception, Stroke, KeyState, FilterKeyState
except ImportError:
    print("Библиотека interception не установлена. Перехват клавиш работать не будет.")

# Инициализация для Windows API
user32 = ctypes.WinDLL('user32', use_last_error=True)
MapVirtualKeyW = user32.MapVirtualKeyW
PostMessageW = user32.PostMessageW

# Константы Windows API
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
MAPVK_VK_TO_VSC = 0

class AutoCP:
    def __init__(self, root):
        self.root = root
        self.running = False
        self.worker_thread = None
        self.interception_thread = None
        self.check_delay = 0.5

        self.config_file = "config.json"

        self.cp_cooldown_time = 3.0
        self.last_cp_use_time = 0

        self.load_config()

        self.window_title = ""
        self.l2_window = None
        self.status_text = "Бот выключен"
        self.cp_bar_area = (48, 58, 135, 9)
        self.lower_yellow = np.array([20, 100, 100])
        self.upper_yellow = np.array([35, 255, 255])
        self.cp_low_count = 0
        self.required_checks = 2

        self.screenshot_folder = "images"

        self.threshold_value_label = None
        self.cp_percent_value = 0
        self.status_label = None
        self.window_label = None
        self.progressbar = None
        self.start_button = None
        self.stop_button = None
        self.cp_percent_label = None
        self.nickname_entry = None

        self.cp_key1_entry = None
        self.cp_key2_entry = None

        self.overlay_window = None
        self.overlay_label = None
        self.keyboard_listener = None

        self.interception_context = None
        self.interception_device = 0
        self.filter = FilterKeyState()
        self.filter.key = KeyState.UP | KeyState.DOWN | KeyState.E0 | KeyState.E1
        self.setup_interception()

        self.setup_gui()

    def setup_interception(self):
        try:
            self.interception_context = interception.create_context()
            interception.set_filter(self.interception_context, interception.is_keyboard, self.filter)
            self.interception_device = interception.wait(self.interception_context)
            print("Interception инициализирован.")
        except Exception as e:
            print(f"Ошибка инициализации interception: {e}")
            self.interception_context = None

    def process_intercepted_key(self, stroke):
        cp1_key = self.get_virtual_key_code(self.cp_key1_entry.get().strip())
        cp2_key = self.get_virtual_key_code(self.cp_key2_entry.get().strip())
        if cp1_key and stroke.code == cp1_key:
            print(f"Блокируем клавишу CP1: {hex(stroke.code)}")
            return True
        if cp2_key and stroke.code == cp2_key:
            print(f"Блокируем клавишу CP2: {hex(stroke.code)}")
            return True
        return False

    def interception_loop(self):
        while self.running and self.interception_context:
            device = interception.wait(self.interception_context)
            stroke = Stroke()
            if interception.receive(self.interception_context, device, stroke, 1):
                if interception.is_keyboard(device):
                    if self.process_intercepted_key(stroke):
                        continue
                interception.send(self.interception_context, device, stroke, 1)

    def setup_gui(self):
        self.root.title("Auto CP Bot (@kalistov521)")
        self.root.geometry("400x420")
        self.root.resizable(False, False)

        try:
            self.root.iconbitmap("icon.ico")
        except tk.TclError:
            pass
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Green.TLabel", foreground="green")
        style.configure("Red.TLabel", foreground="red")
        style.configure("yellow.Horizontal.TProgressbar", troughcolor='gray20', background='gold')
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        title_label = ttk.Label(main_frame, text="Auto CP Bot (@kalistov521)", font=("Helvetica", 16, "bold"))
        title_label.pack(pady=(0, 20))

        nickname_frame = ttk.Frame(main_frame)
        nickname_frame.pack(fill="x", pady=5)
        ttk.Label(nickname_frame, text="Никнейм персонажа:", font=("Arial", 10)).pack(side="left")
        self.nickname_entry = ttk.Entry(nickname_frame, width=30)
        self.nickname_entry.insert(0, self.default_nickname)
        self.nickname_entry.pack(side="left", padx=(5, 0))
        self.status_label = ttk.Label(main_frame, text=f"Статус: {self.status_text}", font=("Arial", 12))
        self.status_label.pack(anchor="w", pady=(10, 5))

        self.window_label = ttk.Label(main_frame, text="Окно игры: Не найдено", font=("Arial", 12))
        self.window_label.pack(anchor="w", pady=(0, 20))

        settings_frame = ttk.LabelFrame(main_frame, text="Настройки", padding="10")
        settings_frame.pack(fill="x", pady=(0, 20))

        threshold_frame = ttk.Frame(settings_frame)
        threshold_frame.pack(fill="x", pady=5)
        ttk.Label(threshold_frame, text="Порог CP (%):", font=("Arial", 10)).pack(side="left")
        self.threshold_scale = ttk.Scale(threshold_frame, from_=10, to=90, orient="horizontal", command=self.update_threshold)
        self.threshold_scale.set(self.cp_threshold_percent)
        self.threshold_scale.pack(side="left", fill="x", expand=True)
        self.threshold_value_label = ttk.Label(threshold_frame, text=f"{self.cp_threshold_percent}%", font=("Arial", 10))
        self.threshold_value_label.pack(side="left")

        keys_frame = ttk.Frame(settings_frame)
        keys_frame.pack(fill="x", pady=5)
        ttk.Label(keys_frame, text="Клавиша CP1:", font=("Arial", 10)).pack(side="left", padx=(0, 5))
        self.cp_key1_entry = ttk.Entry(keys_frame, width=5)
        self.cp_key1_entry.insert(0, self.default_cp_key1)
        self.cp_key1_entry.pack(side="left")
        ttk.Label(keys_frame, text="Клавиша CP2:", font=("Arial", 10)).pack(side="left", padx=(15, 5))
        self.cp_key2_entry = ttk.Entry(keys_frame, width=5)
        self.cp_key2_entry.insert(0, self.default_cp_key2)
        self.cp_key2_entry.pack(side="left")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        self.start_button = ttk.Button(button_frame, text="▶️ Запустить", command=self.start_worker)
        self.start_button.pack(side="left", padx=5)

        self.stop_button = ttk.Button(button_frame, text="⏹️ Остановить", command=self.stop_worker, state="disabled")
        self.stop_button.pack(side="left", padx=5)

        ttk.Button(button_frame, text="🚪 Выйти", command=self.on_close).pack(side="left", padx=5)

        progress_frame = ttk.LabelFrame(main_frame, text="Текущий CP", padding="10")
        progress_frame.pack(fill="x")

        self.cp_percent_label = ttk.Label(progress_frame, text="0.0%", font=("Arial", 12))
        self.cp_percent_label.pack(pady=(0, 5))

        self.progressbar = ttk.Progressbar(progress_frame, orient="horizontal", length=300, mode="determinate", style="yellow.Horizontal.TProgressbar")
        self.progressbar.pack(fill="x")
        self.update_gui()

        self.keyboard_listener = keyboard.Listener(on_press=self.on_press)
        self.keyboard_listener.daemon = True
        self.keyboard_listener.start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_config(self):
        default_config = {
            "default_nickname": "TyPoRe3",
            "cp_threshold_percent": 50,
            "cp_key1": "6",
            "cp_key2": "7"
        }
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.default_nickname = config.get("default_nickname", default_config["default_nickname"])
                self.cp_threshold_percent = config.get("cp_threshold_percent", default_config["cp_threshold_percent"])
                self.default_cp_key1 = config.get("cp_key1", default_config["cp_key1"])
                self.default_cp_key2 = config.get("cp_key2", default_config["cp_key2"])
        except (FileNotFoundError, json.JSONDecodeError):
            print("Файл конфигурации не найден или поврежден. Используются значения по умолчанию.")
            self.default_nickname = default_config["default_nickname"]
            self.cp_threshold_percent = default_config["cp_threshold_percent"]
            self.default_cp_key1 = default_config["cp_key1"]
            self.default_cp_key2 = default_config["cp_key2"]

    def save_config(self):
        config = {
            "default_nickname": self.nickname_entry.get().strip(),
            "cp_threshold_percent": self.cp_threshold_percent,
            "cp_key1": self.cp_key1_entry.get().strip(),
            "cp_key2": self.cp_key2_entry.get().strip()
        }
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Ошибка при сохранении файла конфигурации: {e}")

    def create_overlay_window(self):
        self.overlay_window = tk.Toplevel(self.root)
        self.overlay_window.overrideredirect(True)
        self.overlay_window.wm_attributes("-topmost", True)
        self.overlay_window.wm_attributes("-transparentcolor", "black")
        self.overlay_window.wm_attributes("-alpha", 0.7)
        self.overlay_label = tk.Label(
            self.overlay_window,
            text="",
            font=("Arial", 16, "bold"),
            bg="black",
            fg="white"
        )
        self.overlay_label.pack(padx=10, pady=5)

    def destroy_overlay_window(self):
        if self.overlay_window:
            self.overlay_window.destroy()
            self.overlay_window = None

    def update_threshold(self, value):
        self.cp_threshold_percent = int(float(value))
        if self.threshold_value_label:
            self.threshold_value_label.config(text=f"{self.cp_threshold_percent}%")

    def get_window_title(self):
        nickname = self.nickname_entry.get().strip()
        if not nickname:
            return None
        return f"{nickname} - zMega.com [Mega x10]"

    def find_window(self):
        try:
            self.window_title = self.get_window_title()
            if not self.window_title:
                return False

            windows = gw.getWindowsWithTitle(self.window_title)
            if windows:
                self.l2_window = windows[0]
                return True
            else:
                self.l2_window = None
                return False
        except Exception:
            self.l2_window = None
            return False

    def get_cp_percentage(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower_yellow, self.upper_yellow)
        coords = cv2.findNonZero(mask)

        if coords is None:
            return 0

        max_x = np.max(coords[:, :, 0])
        full_width = self.cp_bar_area[2]

        return (max_x / full_width) * 100

    def get_virtual_key_code(self, key_char):
        try:
            if re.match(r'^[0-9A-Za-z]$', key_char):
                return ord(key_char.upper())
        except:
            pass
        return None

    def send_key_to_window(self, key_char):
        if not self.l2_window or not self.l2_window.isActive:
            self.status_text = "Окно игры неактивно!"
            return

        key_code = self.get_virtual_key_code(key_char)
        if key_code is None:
            self.status_text = f"Неизвестная клавиша: {key_char}"
            return
        try:
            hwnd = self.l2_window._hWnd
            scan_code = MapVirtualKeyW(key_code, MAPVK_VK_TO_VSC)
            l_param_down = (scan_code << 16) | 1
            l_param_up = (scan_code << 16) | 0xC0000001

            PostMessageW(hwnd, WM_KEYDOWN, key_code, l_param_down)
            time.sleep(random.uniform(0.05, 0.08))
            PostMessageW(hwnd, WM_KEYUP, key_code, l_param_up)
        except Exception as e:
            self.status_text = f"Ошибка отправки: {e}"

    def perform_cp_action(self):
        self.status_text = "CP низкий! Использую банки..."

        key1_char = self.cp_key1_entry.get().strip()
        key2_char = self.cp_key2_entry.get().strip()
        if key1_char:
            self.send_key_to_window(key1_char)
            time.sleep(random.uniform(0.1, 0.2))
        if key2_char:
            self.send_key_to_window(key2_char)

        self.last_cp_use_time = time.time()

    def auto_cp_loop(self):
        while self.running:
            if not self.find_window():
                self.status_text = f"Окно '{self.get_window_title()}' потеряно..."
                self.root.after(0, self.destroy_overlay_window)
                self.root.after(0, self.update_gui)
                time.sleep(2)
                continue

            if not self.overlay_window:
                self.root.after(0, self.create_overlay_window)

            try:
                win_left, win_top, win_width, win_height = self.l2_window.left, self.l2_window.top, self.l2_window.width, self.l2_window.height
                x, y, w, h = self.cp_bar_area
                bbox = (win_left + x, win_top + y, win_left + x + w, win_top + y + h)
                screenshot = ImageGrab.grab(bbox=bbox)
                frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

                if not os.path.exists(self.screenshot_folder):
                    os.makedirs(self.screenshot_folder)

                screenshot_path = os.path.join(self.screenshot_folder, "cp_bar_capture.png")
                cv2.imwrite(screenshot_path, frame)

                self.cp_percent_value = self.get_cp_percentage(frame)

                time_since_last_use = time.time() - self.last_cp_use_time
                cooldown_remaining = max(0, self.cp_cooldown_time - time_since_last_use)
                if cooldown_remaining > 0:
                    self.status_text = f"CP: {self.cp_percent_value:.1f}% (откат: {cooldown_remaining:.1f}с)"
                else:
                    self.status_text = f"CP: {self.cp_percent_value:.1f}%"

                if self.overlay_window:
                    overlay_text = f"CP: {self.cp_percent_value:.1f}%"
                    if cooldown_remaining > 0:
                        overlay_text += f" (откат: {cooldown_remaining:.1f}с)"

                    self.root.after(0, lambda: self.overlay_label.config(text=overlay_text))

                    overlay_width = self.overlay_label.winfo_reqwidth()
                    overlay_height = self.overlay_label.winfo_reqheight()

                    overlay_x = win_left + win_width - overlay_width - 10
                    overlay_y = win_top + 10
                    self.root.after(0, lambda: self.overlay_window.geometry(f"{overlay_width}x{overlay_height}+{overlay_x}+{overlay_y}"))

                if self.cp_percent_value < self.cp_threshold_percent and time_since_last_use > self.cp_cooldown_time:
                    self.cp_low_count += 1
                    if self.cp_low_count >= self.required_checks:
                        self.perform_cp_action()
                        self.cp_low_count = 0
                else:
                    self.cp_low_count = 0

            except Exception as e:
                self.status_text = f"Ошибка в цикле: {e}"

            self.root.after(0, self.update_gui)
            time.sleep(self.check_delay)

        self.status_text = "Бот выключен"
        self.cp_percent_value = 0
        self.root.after(0, self.update_gui)

    def start_worker(self):
        if self.running: return

        self.save_config()
        self.window_title = self.get_window_title()
        if not self.window_title:
            messagebox.showerror("Ошибка", "Пожалуйста, введите никнейм.")
            return
        if not self.find_window():
            messagebox.showerror("Ошибка", f"Окно с названием '{self.window_title}' не найдено.")
            return

        self.running = True
        self.worker_thread = threading.Thread(target=self.auto_cp_loop, daemon=True)
        self.worker_thread.start()

        if self.interception_context:
            self.interception_thread = threading.Thread(target=self.interception_loop, daemon=True)
            self.interception_thread.start()

        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status_text = f"Бот запущен. Порог: {self.cp_threshold_percent}%"
        self.update_gui()

    def stop_worker(self):
        if self.running:
            self.running = False
            if self.worker_thread and self.worker_thread.is_alive():
                self.worker_thread.join(timeout=1)
            if hasattr(self, 'interception_thread') and self.interception_thread and self.interception_thread.is_alive():
                self.interception_thread.join(timeout=1)
            self.start_button.config(state="normal")
            self.stop_button.config(state="disabled")
            self.status_text = "Бот остановлен"
            self.update_gui()
            self.destroy_overlay_window()

    def update_gui(self):
        if self.status_label:
            self.status_label.config(text=f"Статус: {self.status_text}")
        if self.cp_percent_label:
            self.cp_percent_label.config(text=f"{self.cp_percent_value:.1f}%")
        if self.progressbar:
            self.progressbar['value'] = self.cp_percent_value

        if self.find_window():
            self.window_label.config(text=f"Окно игры ({self.nickname_entry.get()}): Найдено ✅", style="Green.TLabel")
        else:
            self.window_label.config(text="Окно игры: Не найдено ❌", style="Red.TLabel")

    def on_press(self, key):
        if key == keyboard.Key.f1:
            self.root.after(0, self.start_worker)
        elif key == keyboard.Key.f2:
            self.root.after(0, self.stop_worker)
        elif key == keyboard.Key.f4:
            self.root.after(0, self.on_close)

    def on_close(self):
        self.stop_worker()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = AutoCP(root)
    root.mainloop()
