#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
番茄钟桌面应用 - Pomodoro Timer
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import json
import os
import math
import winsound
from datetime import datetime, date
from collections import defaultdict

# ── 配置 ─────────────────────────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pomodoro_config.json")
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pomodoro_data.json")

DEFAULT_CONFIG = {
    "work_time": 25 * 60,
    "short_break": 5 * 60,
    "long_break": 15 * 60,
    "long_break_interval": 4,
    "always_on_top": True,
    "sound_enabled": True,
    "auto_start_break": False,
    "auto_start_work": False,
    "theme": "dark",
}

COLORS = {
    "dark": {
        "bg": "#1a1a2e",
        "fg": "#e0e0e0",
        "accent": "#e94560",
        "accent2": "#0f3460",
        "accent3": "#16213e",
        "success": "#4ecca3",
        "warning": "#ffc93c",
        "progress_fg": "#e94560",
        "progress_bg": "#16213e",
        "card": "#16213e",
        "card_border": "#0f3460",
        "button_bg": "#0f3460",
        "button_fg": "#e0e0e0",
        "button_active": "#e94560",
        "entry_bg": "#0f3460",
        "entry_fg": "#e0e0e0",
    },
    "light": {
        "bg": "#f5f5f5",
        "fg": "#333333",
        "accent": "#e94560",
        "accent2": "#4a90d9",
        "accent3": "#ffffff",
        "success": "#2ecc71",
        "warning": "#f39c12",
        "progress_fg": "#e94560",
        "progress_bg": "#e0e0e0",
        "card": "#ffffff",
        "card_border": "#dddddd",
        "button_bg": "#4a90d9",
        "button_fg": "#ffffff",
        "button_active": "#e94560",
        "entry_bg": "#ffffff",
        "entry_fg": "#333333",
    },
}


# ── 数据存储 ─────────────────────────────────────────────────────────
class DataStore:
    def __init__(self):
        self.config = self.load_config()
        self.data = self.load_data()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    return {**DEFAULT_CONFIG, **cfg}
            except Exception:
                return dict(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    def save_config(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {"sessions": [], "tasks": []}
        return {"sessions": [], "tasks": []}

    def save_data(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def add_session(self, session):
        self.data["sessions"].append(session)
        self.save_data()

    def add_task(self, task):
        self.data["tasks"].append(task)
        self.save_data()

    def update_task(self, index, task):
        if 0 <= index < len(self.data["tasks"]):
            self.data["tasks"][index] = task
            self.save_data()

    def delete_task(self, index):
        if 0 <= index < len(self.data["tasks"]):
            self.data["tasks"].pop(index)
            self.save_data()

    def get_today_sessions(self):
        today = str(date.today())
        return [s for s in self.data["sessions"] if s.get("date") == today]

    def get_week_sessions(self):
        from datetime import timedelta
        sessions = []
        for i in range(7):
            d = str(date.today() - timedelta(days=i))
            sessions.extend([s for s in self.data["sessions"] if s.get("date") == d])
        return sessions


# ── 圆形进度条 ───────────────────────────────────────────────────────
class CircularProgress(tk.Canvas):
    def __init__(self, master, size=280, **kwargs):
        self.size = size
        self.center = size // 2
        self.radius = size // 2 - 20
        self.line_width = 12
        kwargs.setdefault("bg", "#1a1a2e")
        super().__init__(master, width=size, height=size,
                         highlightthickness=0, **kwargs)
        self.colors = COLORS[DEFAULT_CONFIG["theme"]]

    def set_colors(self, colors):
        self.colors = colors
        self.configure(bg=colors["bg"])

    def draw(self, percentage, text="", subtitle="", phase=""):
        self.delete("all")
        c = self.colors
        # 背景圆环
        self.create_arc(
            20, 20, self.size - 20, self.size - 20,
            start=90, extent=360,
            outline=c["progress_bg"],
            width=self.line_width,
            style="arc",
        )
        # 进度圆环
        if percentage > 0:
            extent = 360 * (percentage / 100)
            self.create_arc(
                20, 20, self.size - 20, self.size - 20,
                start=90, extent=-extent,
                outline=c["progress_fg"],
                width=self.line_width,
                style="arc",
                capstyle="round",
            )
        # 中心文字 - 时间
        self.create_text(
            self.center, self.center - 15,
            text=text,
            fill=c["fg"],
            font=("Segoe UI", 48, "bold"),
        )
        # 阶段标签
        if phase:
            self.create_text(
                self.center, self.center + 35,
                text=phase,
                fill=c.get("success", "#4ecca3") if "休息" in phase else c["accent"],
                font=("Segoe UI", 14),
            )
        # 副标题
        if subtitle:
            self.create_text(
                self.center, self.center + 58,
                text=subtitle,
                fill=c["fg"],
                font=("Segoe UI", 11),
            )


# ── 主应用 ───────────────────────────────────────────────────────────
class PomodoroApp:
    def __init__(self):
        self.store = DataStore()

        self.window = tk.Tk()
        self.window.title("番茄钟")
        self.window.geometry("520x680")
        self.window.minsize(480, 620)

        # 图标设置（可用 unicode 替代）
        try:
            self.window.iconbitmap(default="")
        except Exception:
            pass

        self.apply_always_on_top()

        self.colors = COLORS[self.store.config.get("theme", "dark")]
        self.window.configure(bg=self.colors["bg"])

        # 计时状态
        self.remaining = self.store.config["work_time"]
        self.total_time = self.store.config["work_time"]
        self.is_running = False
        self.current_phase = "work"  # work, short_break, long_break
        self.completed_sessions = 0
        self.today_completed = 0
        self.session_count = 0  # 当前周期内的番茄数
        self.timer_thread = None
        self.running = True

        # 设置UI
        self.setup_ui()
        self.load_today_data()
        self.update_display()

        # 窗口关闭事件
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

    def apply_always_on_top(self):
        val = self.store.config.get("always_on_top", True)
        self.window.attributes("-topmost", val)

    # ── UI 搭建 ──────────────────────────────────────────────────────
    def setup_ui(self):
        c = self.colors
        self.window.configure(bg=c["bg"])

        # 自定义标题栏
        title_bar = tk.Frame(self.window, bg=c["accent3"], height=32)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)

        tk.Label(title_bar, text="  🍅 番茄钟", bg=c["accent3"],
                 fg=c["fg"], font=("Segoe UI", 11, "bold")).pack(side="left", padx=8)

        # 主容器
        main = tk.Frame(self.window, bg=c["bg"])
        main.pack(fill="both", expand=True, padx=16, pady=(8, 16))

        # ── 顶部：模式切换标签 ──
        self.tab_frame = tk.Frame(main, bg=c["bg"])
        self.tab_frame.pack(fill="x", pady=(0, 8))

        self.tabs = {}
        tab_names = [
            ("timer", "⏱  计时"),
            ("tasks", "📋  任务"),
            ("stats", "📊  统计"),
            ("settings", "⚙  设置"),
        ]
        for key, label in tab_names:
            btn = tk.Label(self.tab_frame, text=label,
                           bg=c["accent3"], fg=c["fg"],
                           font=("Segoe UI", 11),
                           padx=16, pady=6, cursor="hand2")
            btn.pack(side="left", padx=(0, 2))
            btn.bind("<Button-1>", lambda e, k=key: self.switch_tab(k))
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=c.get("accent2", c["accent3"])))
            btn.bind("<Leave>", lambda e, b=btn, k=key: b.configure(
                bg=c["accent3"] if k != self.current_tab else c["accent"]))
            self.tabs[key] = btn

        # 标记当前选中
        self.current_tab = "timer"
        self.tabs["timer"].configure(bg=c["accent"], fg="#ffffff")

        # ── 内容容器（卡片式） ──
        self.content = tk.Frame(main, bg=c["card"], bd=1,
                                highlightbackground=c["card_border"],
                                highlightthickness=1)
        self.content.pack(fill="both", expand=True)
        self.content.pack_propagate(False)

        # 构建各页面
        self.pages = {}
        self.build_timer_page()
        self.build_tasks_page()
        self.build_stats_page()
        self.build_settings_page()

        self.show_page("timer")

        # ── 底部状态栏 ──
        status_bar = tk.Frame(self.window, bg=c["accent3"], height=28)
        status_bar.pack(fill="x", side="bottom")
        status_bar.pack_propagate(False)

        self.status_label = tk.Label(status_bar, text="就绪  |  今日完成: 0 个番茄",
                                     bg=c["accent3"], fg=c["fg"],
                                     font=("Segoe UI", 9))
        self.status_label.pack(side="left", padx=10)

    def switch_tab(self, key):
        c = self.colors
        for k, btn in self.tabs.items():
            bg = c["accent3"]
            if k == key:
                bg = c["accent"]
                btn.configure(bg=bg, fg="#ffffff")
            else:
                btn.configure(bg=bg, fg=c["fg"])
        self.current_tab = key
        self.show_page(key)

    def show_page(self, key):
        for k, page in self.pages.items():
            page.pack_forget() if k != key else page.pack(fill="both", expand=True)

    # ── 计时页面 ────────────────────────────────────────────────────
    def build_timer_page(self):
        c = self.colors
        page = tk.Frame(self.content, bg=c["card"])
        self.pages["timer"] = page

        # 圆形进度
        self.progress = CircularProgress(page, size=300, bg=c["card"])
        self.progress.set_colors(c)
        self.progress.pack(pady=(30, 10))

        # 按钮组
        btn_frame = tk.Frame(page, bg=c["card"])
        btn_frame.pack(pady=10)

        btn_style = {"font": ("Segoe UI", 12, "bold"), "relief": "flat",
                      "cursor": "hand2", "bd": 0, "padx": 24, "pady": 8}

        self.start_btn = tk.Button(btn_frame, text="▶  开始", bg=c["success"],
                                    fg="#ffffff", **btn_style,
                                    command=self.toggle_timer)
        self.start_btn.pack(side="left", padx=4)

        self.reset_btn = tk.Button(btn_frame, text="⟳  重置", bg=c["button_bg"],
                                    fg=c["button_fg"], **btn_style,
                                    command=self.reset_timer)
        self.reset_btn.pack(side="left", padx=4)

        self.skip_btn = tk.Button(btn_frame, text="⏭  跳过", bg=c["button_bg"],
                                   fg=c["button_fg"], **btn_style,
                                   command=self.skip_phase)
        self.skip_btn.pack(side="left", padx=4)

        # 周期进度
        progress_info = tk.Frame(page, bg=c["card"])
        progress_info.pack(pady=10)

        tk.Label(progress_info, text="本周期进度:",
                 bg=c["card"], fg=c["fg"], font=("Segoe UI", 10)).pack(side="left")

        self.cycle_progress_label = tk.Label(progress_info,
            text="⬜⬜⬜⬜", bg=c["card"], fg=c["fg"], font=("Segoe UI", 12))
        self.cycle_progress_label.pack(side="left", padx=6)

        tk.Label(progress_info, text=f" (每 {self.store.config['long_break_interval']} 个长休息)",
                 bg=c["card"], fg=c["fg"], font=("Segoe UI", 9)).pack(side="left")

        # 会话统计
        stats_frame = tk.Frame(page, bg=c["card"])
        stats_frame.pack(pady=(10, 20))

        self.session_label = tk.Label(stats_frame,
            text="今日完成: 0 个番茄  |  总计: 0 个番茄",
            bg=c["card"], fg=c["fg"], font=("Segoe UI", 10))
        self.session_label.pack()

    def update_display(self):
        c = self.colors
        mins = self.remaining // 60
        secs = self.remaining % 60
        time_str = f"{mins:02d}:{secs:02d}"

        phase_names = {
            "work": "专注时间",
            "short_break": "短休息",
            "long_break": "长休息",
        }
        phase_name = phase_names.get(self.current_phase, "")

        # 进度百分比
        pct = ((self.total_time - self.remaining) / self.total_time) * 100

        # 今日会话数
        today_total = self.today_completed

        self.progress.set_colors(c)
        self.progress.draw(pct, time_str, f"今日: {today_total} 个番茄", phase_name)

        # 周期进度
        inv = self.store.config["long_break_interval"]
        done = self.session_count % inv
        blocks = ""
        for i in range(inv):
            if i < done:
                blocks += "🍅"
            else:
                blocks += "⬜"
        self.cycle_progress_label.configure(text=blocks)

        # 状态栏
        status_text = f"{phase_name}  |  今日完成: {today_total} 个番茄"
        if self.is_running:
            status_text = f"⏳ {phase_name} 剩余 {time_str}  |  今日: {today_total} 个番茄"
        self.status_label.configure(text=status_text)

        # 标签页统计
        if "timer" in self.tabs:
            self.session_label.configure(
                text=f"今日完成: {today_total} 个番茄  |  总计: {len(self.store.data['sessions'])} 个番茄")

    # ── 任务页面 ─────────────────────────────────────────────────────
    def build_tasks_page(self):
        c = self.colors
        page = tk.Frame(self.content, bg=c["card"])
        self.pages["tasks"] = page

        # 标题
        title_frame = tk.Frame(page, bg=c["card"])
        title_frame.pack(fill="x", padx=16, pady=(16, 8))

        tk.Label(title_frame, text="📋 任务列表",
                 bg=c["card"], fg=c["fg"],
                 font=("Segoe UI", 14, "bold")).pack(side="left")

        # 添加任务区
        add_frame = tk.Frame(page, bg=c["card"])
        add_frame.pack(fill="x", padx=16, pady=8)

        self.task_entry = tk.Entry(add_frame, bg=c["entry_bg"], fg=c["entry_fg"],
                                    insertbackground=c["fg"],
                                    font=("Segoe UI", 11), relief="flat", bd=0)
        self.task_entry.pack(side="left", fill="x", expand=True, ipady=6, ipadx=8)
        self.task_entry.bind("<Return>", lambda e: self.add_task())

        tk.Button(add_frame, text="添加", bg=c["accent"], fg="#ffffff",
                   font=("Segoe UI", 10, "bold"), relief="flat", bd=0,
                   padx=16, pady=6, cursor="hand2",
                   command=self.add_task).pack(side="left", padx=(6, 0))

        # 任务列表
        list_frame = tk.Frame(page, bg=c["card"])
        list_frame.pack(fill="both", expand=True, padx=16, pady=(8, 16))

        # 画布 + 滚动条
        canvas = tk.Canvas(list_frame, bg=c["card"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        self.tasks_container = tk.Frame(canvas, bg=c["card"])

        self.tasks_container.bind("<Configure>",
            lambda e: (canvas.configure(scrollregion=canvas.bbox("all")),
                       canvas.itemconfig(window_id, width=e.width)))
        window_id = canvas.create_window((0, 0), window=self.tasks_container,
                                          anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 绑定鼠标滚轮
        def on_mousewheel(event):
            canvas.yview_scroll(-1 * (event.delta // 120), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel, add="+")

        self.task_canvas = canvas
        self.refresh_tasks()

    def add_task(self):
        text = self.task_entry.get().strip()
        if not text:
            return
        task = {"text": text, "done": False, "pomodoros": 0, "created": str(datetime.now())}
        self.store.add_task(task)
        self.task_entry.delete(0, tk.END)
        self.refresh_tasks()

    def refresh_tasks(self):
        c = self.colors
        for w in self.tasks_container.winfo_children():
            w.destroy()

        tasks = self.store.data["tasks"]
        if not tasks:
            empty_frame = tk.Frame(self.tasks_container, bg=c["card"], height=60)
            empty_frame.pack(fill="x")
            tk.Label(empty_frame, text="还没有任务，输入任务开始吧 ✨",
                     bg=c["card"], fg=c["fg"], font=("Segoe UI", 10)).pack(pady=20)
            return

        for i, task in enumerate(tasks):
            self.create_task_row(i, task, c)

    def create_task_row(self, i, task, c):
        row = tk.Frame(self.tasks_container, bg=c["accent3"], bd=0,
                        highlightbackground=c["card_border"],
                        highlightthickness=1)
        row.pack(fill="x", pady=3)

        # 复选框
        var = tk.BooleanVar(value=task.get("done", False))
        cb = tk.Checkbutton(row, variable=var, bg=c["accent3"],
                             command=lambda i=i, v=var: self.toggle_task_done(i, v),
                             cursor="hand2")
        cb.pack(side="left", padx=(8, 4))

        # 任务文本
        text = task.get("text", "")
        lbl = tk.Label(row, text=text, bg=c["accent3"], fg=c["fg"],
                        font=("Segoe UI", 10),
                        wraplength=220, anchor="w", justify="left")
        lbl.pack(side="left", fill="x", expand=True, pady=6)

        if task.get("done"):
            lbl.configure(fg=c.get("success", "#4ecca3"),
                          font=("Segoe UI", 10, "overstrike"))

        # 番茄计数
        pomos = task.get("pomodoros", 0)
        tk.Label(row, text=f"🍅×{pomos}", bg=c["accent3"],
                  fg=c.get("warning", "#ffc93c"),
                  font=("Segoe UI", 9)).pack(side="left", padx=4)

        # 删除按钮
        del_btn = tk.Button(row, text="✕", bg=c["accent3"],
                             fg=c["fg"], bd=0, relief="flat",
                             font=("Segoe UI", 10), cursor="hand2",
                             command=lambda i=i: self.delete_task_confirm(i))
        del_btn.pack(side="right", padx=(2, 8))

    def toggle_task_done(self, i, var):
        tasks = self.store.data["tasks"]
        if 0 <= i < len(tasks):
            tasks[i]["done"] = var.get()
            self.store.save_data()
            self.refresh_tasks()

    def delete_task_confirm(self, i):
        if messagebox.askyesno("确认删除", "确定要删除这个任务吗？", parent=self.window):
            self.store.delete_task(i)
            self.refresh_tasks()

    # ── 统计页面 ────────────────────────────────────────────────────
    def build_stats_page(self):
        c = self.colors
        page = tk.Frame(self.content, bg=c["card"])
        self.pages["stats"] = page

        scroll_canvas = tk.Canvas(page, bg=c["card"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(page, orient="vertical", command=scroll_canvas.yview)
        stats_content = tk.Frame(scroll_canvas, bg=c["card"])

        stats_content.bind("<Configure>",
            lambda e: (scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all")),
                       scroll_canvas.itemconfig(stat_window_id, width=e.width)))
        stat_window_id = scroll_canvas.create_window((0, 0), window=stats_content,
                                                      anchor="nw")
        scroll_canvas.configure(yscrollcommand=scrollbar.set)

        scroll_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 头部
        tk.Label(stats_content, text="📊 数据统计",
                 bg=c["card"], fg=c["fg"],
                 font=("Segoe UI", 16, "bold")).pack(pady=(20, 16))

        # 统计卡片容器
        self.stats_content = stats_content

        def on_mousewheel(event):
            scroll_canvas.yview_scroll(-1 * (event.delta // 120), "units")
        scroll_canvas.bind_all("<MouseWheel>", on_mousewheel, add="+")

    def refresh_stats(self):
        c = self.colors
        content = self.stats_content
        for w in content.winfo_children():
            if w.winfo_class() != "Label" or w.cget("text") != "📊 数据统计":
                w.destroy()

        sessions = self.store.data["sessions"]

        # 今日统计
        today = str(date.today())
        today_sessions = [s for s in sessions if s.get("date") == today]
        today_count = len(today_sessions)
        today_focus = sum(s.get("duration", 0) for s in today_sessions)

        # 本周统计
        from datetime import timedelta
        week_sessions = []
        for i in range(7):
            d = str(date.today() - timedelta(days=i))
            week_sessions.extend([s for s in sessions if s.get("date") == d])
        week_count = len(week_sessions)
        week_focus = sum(s.get("duration", 0) for s in week_sessions)

        # 全部统计
        total_count = len(sessions)
        total_focus = sum(s.get("duration", 0) for s in sessions)

        # 日期分布
        daily = defaultdict(int)
        for s in sessions:
            daily[s.get("date", "")] += 1

        stats_cards = [
            ("今日", f"{today_count} 个", self.format_time(today_focus)),
            ("本周", f"{week_count} 个", self.format_time(week_focus)),
            ("总计", f"{total_count} 个", self.format_time(total_focus)),
        ]

        row_frame = tk.Frame(content, bg=c["card"])
        row_frame.pack(pady=8)

        for i, (title, count, time_str) in enumerate(stats_cards):
            card = tk.Frame(row_frame, bg=c["accent3"], bd=1,
                            highlightbackground=c["card_border"],
                            highlightthickness=1, width=130, height=100)
            card.pack(side="left", padx=6)
            card.pack_propagate(False)

            tk.Label(card, text=title, bg=c["accent3"],
                     fg=c["fg"], font=("Segoe UI", 10)).pack(pady=(12, 4))
            tk.Label(card, text=count, bg=c["accent3"],
                     fg=c["accent"], font=("Segoe UI", 20, "bold")).pack()
            tk.Label(card, text=time_str, bg=c["accent3"],
                     fg=c["fg"], font=("Segoe UI", 9)).pack()

        # 近7天分布
        tk.Label(content, text="\n近 7 天分布",
                 bg=c["card"], fg=c["fg"],
                 font=("Segoe UI", 12, "bold")).pack(pady=(16, 8))

        days_frame = tk.Frame(content, bg=c["card"])
        days_frame.pack(pady=8, padx=20)

        for i in range(7):
            d = str(date.today() - timedelta(days=6 - i))
            count = daily.get(d, 0)
            day_card = tk.Frame(days_frame, bg=c["accent3"], bd=1,
                                highlightbackground=c["card_border"],
                                highlightthickness=1,
                                width=50, height=100)
            day_card.pack(side="left", padx=3)
            day_card.pack_propagate(False)

            # 柱状图
            bar_h = max(10, count * 18)
            bar_frame = tk.Frame(day_card, bg=c["accent3"], height=70)
            bar_frame.pack(fill="x")
            bar_frame.pack_propagate(False)

            bar = tk.Frame(bar_frame, bg=c["accent"] if count > 0 else c["card_border"],
                           height=bar_h, width=30)
            bar.place(relx=0.5, rely=1.0, anchor="s")

            dt = datetime.strptime(d, "%Y-%m-%d")
            label = "今天" if i == 6 else ("昨天" if i == 5 else dt.strftime("%m/%d"))
            tk.Label(day_card, text=label, bg=c["accent3"],
                     fg=c["fg"], font=("Segoe UI", 8)).pack(side="bottom", pady=2)
            tk.Label(day_card, text=str(count), bg=c["accent3"],
                     fg=c["accent"], font=("Segoe UI", 10, "bold")).pack()

        # 任务完成情况
        tasks = self.store.data["tasks"]
        done_tasks = sum(1 for t in tasks if t.get("done"))
        total_tasks = len(tasks)

        tk.Label(content, text="\n任务状态",
                 bg=c["card"], fg=c["fg"],
                 font=("Segoe UI", 12, "bold")).pack(pady=(16, 8))

        task_frame = tk.Frame(content, bg=c["accent3"], bd=1,
                              highlightbackground=c["card_border"],
                              highlightthickness=1)
        task_frame.pack(pady=8, padx=20, fill="x")

        tk.Label(task_frame, text=f"总计: {total_tasks} 个任务  |  已完成: {done_tasks} 个  |  进行中: {total_tasks - done_tasks} 个",
                 bg=c["accent3"], fg=c["fg"],
                 font=("Segoe UI", 10)).pack(pady=12)

        self.stats_refreshed = True

    def format_time(self, seconds):
        h = seconds // 3600
        m = (seconds % 3600) // 60
        if h > 0:
            return f"{h}小时{m}分钟"
        return f"{m}分钟"

    # ── 设置页面 ────────────────────────────────────────────────────
    def build_settings_page(self):
        c = self.colors
        page = tk.Frame(self.content, bg=c["card"])
        self.pages["settings"] = page

        tk.Label(page, text="⚙ 设置",
                 bg=c["card"], fg=c["fg"],
                 font=("Segoe UI", 14, "bold")).pack(pady=(20, 16))

        config = self.store.config

        # 时间设置
        settings_frame = tk.Frame(page, bg=c["card"])
        settings_frame.pack(pady=8, padx=30, fill="x")

        time_settings = [
            ("专注时间（分钟）", "work_time", str(config["work_time"] // 60)),
            ("短休息（分钟）", "short_break", str(config["short_break"] // 60)),
            ("长休息（分钟）", "long_break", str(config["long_break"] // 60)),
            ("长休息间隔（番茄数）", "long_break_interval", str(config["long_break_interval"])),
        ]

        self.entries = {}
        for i, (label, key, default) in enumerate(time_settings):
            row = tk.Frame(settings_frame, bg=c["card"])
            row.pack(fill="x", pady=4)

            tk.Label(row, text=label, bg=c["card"], fg=c["fg"],
                     font=("Segoe UI", 10), width=22, anchor="w").pack(side="left")

            ent = tk.Entry(row, bg=c["entry_bg"], fg=c["entry_fg"],
                           insertbackground=c["fg"],
                           font=("Segoe UI", 11), width=8,
                           relief="flat", bd=0, justify="center")
            ent.insert(0, default)
            ent.pack(side="left", ipady=4, ipadx=6)
            self.entries[key] = ent

        # 选项设置
        tk.Label(page, text="\n选项",
                 bg=c["card"], fg=c["fg"],
                 font=("Segoe UI", 12, "bold")).pack(pady=(16, 8))

        options_frame = tk.Frame(page, bg=c["card"])
        options_frame.pack(pady=8, padx=30, fill="x")

        self.check_vars = {}

        bool_options = [
            ("always_on_top", "窗口置顶"),
            ("sound_enabled", "启用提示音"),
            ("auto_start_break", "休息自动开始"),
            ("auto_start_work", "专注自动开始"),
        ]

        for i, (key, label) in enumerate(bool_options):
            var = tk.BooleanVar(value=config.get(key, False))
            self.check_vars[key] = var

            row = tk.Frame(options_frame, bg=c["card"])
            row.pack(fill="x", pady=2)

            cb = tk.Checkbutton(row, variable=var, bg=c["card"],
                                 fg=c["fg"], selectcolor=c["card"],
                                 activebackground=c["card"],
                                 activeforeground=c["fg"],
                                 cursor="hand2")
            cb.pack(side="left")

            tk.Label(row, text=label, bg=c["card"], fg=c["fg"],
                     font=("Segoe UI", 10)).pack(side="left", padx=4)

        # 主题选择
        theme_row = tk.Frame(options_frame, bg=c["card"])
        theme_row.pack(fill="x", pady=8)

        tk.Label(theme_row, text="主题", bg=c["card"], fg=c["fg"],
                 font=("Segoe UI", 10), width=22, anchor="w").pack(side="left")

        self.theme_var = tk.StringVar(value=config.get("theme", "dark"))
        theme_menu = ttk.Combobox(theme_row, textvariable=self.theme_var,
                                    values=["dark", "light"], width=10, state="readonly")
        theme_menu.pack(side="left")

        # 保存按钮
        tk.Button(page, text="💾  保存设置", bg=c["accent"], fg="#ffffff",
                   font=("Segoe UI", 12, "bold"), relief="flat", bd=0,
                   padx=30, pady=10, cursor="hand2",
                   command=self.save_settings).pack(pady=30)

        # 数据管理
        tk.Label(page, text="数据管理",
                 bg=c["card"], fg=c["fg"],
                 font=("Segoe UI", 12, "bold")).pack(pady=(8, 4))

        tk.Button(page, text="🗑  清除所有数据", bg=c["card"],
                   fg=c["accent"], font=("Segoe UI", 10),
                   relief="flat", bd=1, highlightbackground=c["accent"],
                   padx=20, pady=6, cursor="hand2",
                   command=self.clear_all_data).pack(pady=6)

        tk.Label(page, text="数据文件保存在程序所在目录", bg=c["card"],
                 fg=c["fg"], font=("Segoe UI", 8)).pack()

        self.settings_saved_label = tk.Label(page, text="", bg=c["card"],
                                             fg=c.get("success", "#4ecca3"),
                                             font=("Segoe UI", 10))
        self.settings_saved_label.pack()

    def save_settings(self):
        try:
            for key, entry in self.entries.items():
                val = entry.get().strip()
                if key == "long_break_interval":
                    self.store.config[key] = int(val)
                else:
                    self.store.config[key] = int(val) * 60

            for key, var in self.check_vars.items():
                self.store.config[key] = var.get()

            self.store.config["theme"] = self.theme_var.get()

            self.store.save_config()

            # 应用设置
            self.apply_always_on_top()
            self.apply_theme()

            # 重置计时显示
            if self.current_phase == "work":
                self.total_time = self.store.config["work_time"]
                self.remaining = self.total_time
            self.update_display()

            self.settings_saved_label.configure(text="✅ 设置已保存！")
            self.window.after(3000, lambda: self.settings_saved_label.configure(text=""))
        except (ValueError, KeyError) as e:
            messagebox.showerror("错误", f"输入格式错误: {e}", parent=self.window)

    def apply_theme(self):
        new_theme = self.store.config.get("theme", "dark")
        self.colors = COLORS[new_theme]

        # 更新整个窗口
        self.window.configure(bg=self.colors["bg"])

        # 重建UI
        for widget in self.window.winfo_children():
            widget.destroy()
        self.setup_ui()

        # 恢复计时状态
        self.update_display()
        if self.current_phase == "timer":
            self.show_page("timer")

        self.load_today_data()
        self.refresh_tasks()

    def clear_all_data(self):
        if messagebox.askyesno("确认清除", "确定要清除所有数据吗？\n此操作不可撤销！", parent=self.window):
            self.store.data = {"sessions": [], "tasks": []}
            self.store.save_data()
            self.today_completed = 0
            self.load_today_data()
            self.refresh_tasks()
            self.update_display()
            messagebox.showinfo("完成", "数据已清除！", parent=self.window)

    # ── 计时逻辑 ────────────────────────────────────────────────────
    def toggle_timer(self):
        if not self.is_running:
            self.start_timer()
        else:
            self.pause_timer()

    def start_timer(self):
        self.is_running = True
        self.start_btn.configure(text="⏸  暂停")
        if self.timer_thread is None or not self.timer_thread.is_alive():
            self.timer_thread = threading.Thread(target=self.timer_loop, daemon=True)
            self.timer_thread.start()

    def pause_timer(self):
        self.is_running = False
        self.start_btn.configure(text="▶  继续")

    def timer_loop(self):
        while self.is_running and self.running and self.remaining > 0:
            time.sleep(1)
            self.remaining -= 1
            if self.remaining < 0:
                self.remaining = 0

            self.window.after(0, self.update_display)

        if self.remaining <= 0 and self.is_running and self.running:
            self.window.after(0, self.on_phase_complete)

    def on_phase_complete(self):
        self.is_running = False

        if self.current_phase == "work":
            # 记录完成的工作会话
            today = str(date.today())
            session = {
                "date": today,
                "duration": self.store.config["work_time"],
                "phase": "work",
                "time": str(datetime.now()),
            }
            self.store.add_session(session)
            self.today_completed += 1
            self.session_count += 1

            # 播放提示音
            if self.store.config.get("sound_enabled", True):
                self.play_sound()

            # 更新任务番茄计数
            tasks = self.store.data["tasks"]
            if tasks:
                # 给第一个未完成的任务加一个番茄
                for i, t in enumerate(tasks):
                    if not t.get("done"):
                        t["pomodoros"] = t.get("pomodoros", 0) + 1
                        self.store.save_data()
                        self.refresh_tasks()
                        break

            # 判断长休息还是短休息
            interval = self.store.config["long_break_interval"]
            if self.session_count % interval == 0:
                self.current_phase = "long_break"
                self.total_time = self.store.config["long_break"]
            else:
                self.current_phase = "short_break"
                self.total_time = self.store.config["short_break"]

            self.remaining = self.total_time
            self.update_display()

            # 检查是否自动开始
            if self.store.config.get("auto_start_break", False):
                self.start_timer()
            else:
                self.start_btn.configure(text="▶  开始休息")

        else:
            # 休息结束，回到工作
            if self.store.config.get("sound_enabled", True):
                self.play_sound()

            self.current_phase = "work"
            self.total_time = self.store.config["work_time"]
            self.remaining = self.total_time
            self.update_display()

            if self.store.config.get("auto_start_work", False):
                self.start_timer()
            else:
                self.start_btn.configure(text="▶  开始专注")

        self.refresh_stats()

    def reset_timer(self):
        self.is_running = False
        self.start_btn.configure(text="▶  开始")

        # 根据当前阶段重置时间
        if self.current_phase == "work":
            self.total_time = self.store.config["work_time"]
        elif self.current_phase == "short_break":
            self.total_time = self.store.config["short_break"]
        else:
            self.total_time = self.store.config["long_break"]

        self.remaining = self.total_time
        self.update_display()

    def skip_phase(self):
        self.is_running = False
        self.on_phase_complete()

    def play_sound(self):
        try:
            # Windows 系统提示音
            winsound.MessageBeep(winsound.MB_OK)
            # 额外播放一个音调
            for freq in [800, 1000, 1200]:
                winsound.Beep(freq, 150)
        except Exception:
            pass

    def load_today_data(self):
        today = str(date.today())
        today_sessions = [s for s in self.store.data["sessions"] if s.get("date") == today]
        self.today_completed = len(today_sessions)

        # 判断当前日周期
        if self.store.data["sessions"]:
            last_session = self.store.data["sessions"][-1]
            if last_session.get("date") == today:
                # 今天有记录，看最后一个是什么阶段
                count = len([s for s in self.store.data["sessions"]
                            if s.get("date") == today and s.get("phase") == "work"])
                self.session_count = count % self.store.config["long_break_interval"]
            else:
                self.session_count = 0
        else:
            self.session_count = 0

        self.refresh_stats()
        self.update_display()

    # ── 窗口事件 ────────────────────────────────────────────────────
    def on_close(self):
        if self.is_running:
            if not messagebox.askokcancel("退出", "计时器正在运行，确定要退出吗？", parent=self.window):
                return
        self.running = False
        self.is_running = False
        self.window.destroy()

    def run(self):
        self.window.mainloop()


# ── 入口 ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = PomodoroApp()
    app.run()
