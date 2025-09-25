import os
import threading
import time
import random
import ctypes
from ctypes import wintypes
from colorama import init, Fore, Style
import pyfiglet
import pygetwindow as gw
from PIL import ImageGrab
import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk
import sys
import pynput
import pyautogui

# Инициализация colorama для поддержки цвета в консоли Windows
init()

# Установка зависимостей, если необходимо
try:
    import pyautogui
    import keyboard 
    import colorama
    import pyfiglet
    import pygetwindow
    from PIL import ImageGrab
    import cv2
    import numpy as np
    import pynput
except ImportError:
    print(f"{Fore.YELLOW}[!] Установка необходимых библиотек...{Style.RESET_ALL}")
    os.system("pip install pyautogui keyboard colorama pyfiglet pygetwindow Pillow opencv-python numpy pynput")
    print(f"{Fore.GREEN}[+] Установка завершена. Пожалуйста, перезапустите скрипт.{Style.RESET_ALL}")
    exit()

# Константы Windows API
# Исправлены константы, чтобы соответствовать кнопкам 6 и 7
VK_6 = 0x36
VK_7 = 0x37

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
MAPVK_VK_TO_VSC = 0

user32 = ctypes.WinDLL('user32', use_last_error=True)
MapVirtualKeyW = user32.MapVirtualKeyW
PostMessageW = user32.PostMessageW

class AutoCP:
    def __init__(self):
        self.running = False
        self.worker_thread = None
        self.check_delay = 0.5 
        self.cp_key_1 = VK_6
        self.cp_key_2 = VK_7
        self.window_title = "TyPoRe3 - zMega.com [Mega x10]"
        self.l2_window = None
        self.status_text = "Бот выключен"
        
        self.cp_threshold_percent = 50
        
        # Область для считывания CP/HP, чтобы избежать повторных скриншотов
        self.status_bar_area = (40, 440, 200, 490)
        
        # Исправленные диапазоны цветов для более точного распознавания
        # Оранжевый (CP)
        self.lower_orange = np.array([10, 100, 100])
        self.upper_orange = np.array([30, 255, 255])
        
        # Красный (HP). Диапазон для красного цвета в HSV двойной
        self.lower_red1 = np.array([0, 100, 100])
        self.upper_red1 = np.array([10, 255, 255])
        self.lower_red2 = np.array([160, 100, 100])
        self.upper_red2 = np.array([179, 255, 255])
        
        self.cp_low_count = 0
        self.required_checks = 3

        self.root = None
        self.label = None
        self.progressbar = None
        self.cp_percent = 0
        self.hp_percent = 100
        
    def print_status_to_console(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        title = pyfiglet.figlet_format("Auto CP Bot", font="slant")
        print(f"{Fore.CYAN}{title}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Статус: {self.status_text}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}Нажмите F1 для старта, F2 для остановки, F4 для выхода.{Style.RESET_ALL}")

    def find_window(self):
        try:
            windows = gw.getWindowsWithTitle(self.window_title)
            if windows:
                self.l2_window = windows[0]
                return True
            else:
                return False
        except Exception as e:
            return False

    def get_bar_percentage(self, frame, color_mask):
        """
        Измеряет длину полосы по цвету на уже захваченном кадре
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        if color_mask[0] is self.lower_red1:
            mask1 = cv2.inRange(hsv, color_mask[0], color_mask[1])
            mask2 = cv2.inRange(hsv, color_mask[2], color_mask[3])
            mask = mask1 | mask2
        else:
            mask = cv2.inRange(hsv, color_mask[0], color_mask[1])
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return 0

        max_contour = max(contours, key=cv2.contourArea)
        _, _, filled_width, _ = cv2.boundingRect(max_contour)

        # Общая ширина полосы (серый фон)
        gray_mask = cv2.inRange(hsv, np.array([0, 0, 70]), np.array([179, 50, 200]))
        gray_contours, _ = cv2.findContours(gray_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        total_width = 0
        if gray_contours:
            max_gray_contour = max(gray_contours, key=cv2.contourArea)
            _, _, total_width, _ = cv2.boundingRect(max_gray_contour)
        
        if total_width == 0:
            return 100
        
        percent = (filled_width / total_width) * 100
        return percent

    def send_key_to_window(self, key_code):
        if not self.l2_window: return
        try:
            hwnd = self.l2_window._hWnd
            scan_code = MapVirtualKeyW(key_code, MAPVK_VK_TO_VSC)
            PostMessageW(hwnd, WM_KEYDOWN, key_code, scan_code)
            time.sleep(random.uniform(0.05, 0.08))
            PostMessageW(hwnd, WM_KEYUP, key_code, scan_code | 0x80)
        except Exception as e:
            self.status_text = f"Ошибка отправки: {e}"
            self.print_status_to_console()

    def perform_cp(self):
        self.send_key_to_window(self.cp_key_1)
        time.sleep(random.uniform(0.01, 0.03))
        self.send_key_to_window(self.cp_key_2)

    def auto_cp_loop(self):
        self.status_text = f"Бот запущен. Порог: {self.cp_threshold_percent}%"
        self.print_status_to_console()
        
        while self.running:
            try:
                # Делаем один скриншот и используем его для обоих полос
                x, y, w, h = self.l2_window.left, self.l2_window.top, self.l2_window.width, self.l2_window.height
                screenshot = ImageGrab.grab(bbox=(x + self.status_bar_area[0], y + self.status_bar_area[1], 
                                                  x + self.status_bar_area[2], y + self.status_bar_area[3]))
                screenshot_np = np.array(screenshot)
                frame = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)

                self.cp_percent = self.get_bar_percentage(frame, [self.lower_orange, self.upper_orange])
                self.hp_percent = self.get_bar_percentage(frame, [self.lower_red1, self.upper_red1, self.lower_red2, self.upper_red2])

            except Exception as e:
                self.status_text = f"Ошибка анализа: {e}"
                self.print_status_to_console()
                self.running = False
                break
                
            if self.cp_percent < self.cp_threshold_percent and self.hp_percent > 0:
                self.cp_low_count += 1
                if self.cp_low_count >= self.required_checks:
                    self.perform_cp()
                    self.cp_low_count = 0
            else:
                self.cp_low_count = 0

            self.status_text = f"CP: {self.cp_percent:.2f}% | HP: {self.hp_percent:.2f}%"
            self.print_status_to_console()
            
            delay = random.uniform(self.check_delay, self.check_delay + 0.5)
            time.sleep(delay)

    def start_worker(self):
        if self.running: return
        if not self.find_window():
            self.status_text = f"Окно '{self.window_title}' не найдено. Проверьте название."
            self.print_status_to_console()
            return

        self.running = True
        self.worker_thread = threading.Thread(target=self.auto_cp_loop)
        self.worker_thread.daemon = True
        self.worker_thread.start()

    def stop_worker(self):
        if self.running:
            self.running = False
            if self.worker_thread and self.worker_thread.is_alive():
                self.worker_thread.join(timeout=2)
            self.status_text = "Бот остановлен"
            self.print_status_to_console()

    def create_overlay(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True) 
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.9)
        self.root.geometry("300x70+10+10")
        self.root.config(bg="black")
        
        self.label = tk.Label(self.root, text=self.status_text, font=("Arial", 10), fg="white", bg="black")
        self.label.pack(pady=5)
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("green.Horizontal.TProgressbar", troughcolor='gray', background='lime green')
        
        self.progressbar = ttk.Progressbar(self.root, orient="horizontal", length=250, mode="determinate", style="green.Horizontal.TProgressbar")
        self.progressbar.pack(pady=2)

        self.update_overlay()
        
    def update_overlay(self):
        self.label.config(text=self.status_text)
        self.progressbar['value'] = self.cp_percent
        self.root.after(200, self.update_overlay)

    def on_press(self, key):
        try:
            if key == pynput.keyboard.Key.f1:
                self.start_worker()
            elif key == pynput.keyboard.Key.f2:
                self.stop_worker()
            elif key == pynput.keyboard.Key.f4:
                print(f"{Fore.RED}[!] Выход из программы...{Style.RESET_ALL}")
                if self.root:
                    self.root.destroy()
                os._exit(0)
        except AttributeError:
            pass

    def run(self):
        self.print_status_to_console()
        listener = pynput.keyboard.Listener(on_press=self.on_press)
        listener.daemon = True
        listener.start()
        
        self.create_overlay()
        self.root.mainloop()

if __name__ == "__main__":
    autocp = AutoCP()
    autocp.run()