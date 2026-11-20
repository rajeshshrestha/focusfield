#!/usr/bin/env python3
"""Focusfield — a calm, modern Pomodoro desktop app for Linux (Tkinter)."""
from __future__ import annotations

import math
import shutil
import subprocess
import sys
import tkinter as tk
import tkinter.font as tkfont
from datetime import date, datetime
from pathlib import Path
from tkinter import messagebox

from core import BOUNDS, FocusEngine

# -- Design tokens -----------------------------------------------------------
BG = "#0E1622"
SIDEBAR = "#0B121D"
SIDEBAR_ACTIVE = "#1A2937"
PANEL = "#192534"
PANEL_DARK = "#152130"
PANEL_INNER = "#223145"
BORDER = "#2A3B4B"
TEXT = "#F5F4F0"
MUTED = "#98A9B8"
DIM = "#65798A"
CORAL = "#FFAB85"
CORAL_LIGHT = "#FFC3A8"
CORAL_DARK = "#BE765D"
MINT = "#83D5C3"
MINT_DARK = "#57B5A5"
YELLOW = "#EED8A0"
DARK_TEXT = "#14202C"
FONT_FAMILY = "Cantarell"


def f(size: int, weight: str = "normal"):
    return (FONT_FAMILY, size, weight)


def label(parent, text, size=11, fg=TEXT, bg=None, weight="normal", **kwargs):
    return tk.Label(parent, text=text, font=f(size, weight), fg=fg,
                    bg=bg or parent.cget("bg"), **kwargs)


def rounded(canvas, x1, y1, x2, y2, radius, color, tag=None):
    radius = max(1, min(radius, (x2-x1)/2, (y2-y1)/2))
    # A smoothed polygon is used for consistently rounded widgets on Tk/X11.
    coords = [x1+radius, y1, x2-radius, y1, x2, y1, x2, y1+radius,
              x2, y2-radius, x2, y2, x2-radius, y2, x1+radius, y2,
              x1, y2, x1, y2-radius, x1, y1+radius, x1, y1]
    return canvas.create_polygon(coords, smooth=True, splinesteps=20,
                                 fill=color, outline="", tags=tag)


class Card(tk.Canvas):
    """Canvas-backed rounded card containing a regular Tk frame."""
    def __init__(self, parent, color=PANEL, radius=22, pad=12, **kwargs):
        self.color = color
        self.radius = radius
        self.pad = pad
        super().__init__(parent, bg=parent.cget("bg"), highlightthickness=0,
                         bd=0, relief="flat", **kwargs)
        self.inner = tk.Frame(self, bg=color)
        self.win = self.create_window(pad, pad, window=self.inner, anchor="nw")
        self.bind("<Configure>", self._paint)

    def _paint(self, event):
        self.delete("cardbg")
        rounded(self, 1, 1, event.width-1, event.height-1, self.radius, self.color, "cardbg")
        self.tag_lower("cardbg")
        self.itemconfigure(self.win, width=max(1,event.width-2*self.pad),
                           height=max(1,event.height-2*self.pad))


class PillButton(tk.Canvas):
    def __init__(self, parent, text, command, *, width=145, height=46,
                 bg=CORAL, fg=DARK_TEXT, hover=None, font_size=11,
                 outline=None, weight="bold", corner=17):
        super().__init__(parent, width=width, height=height, bg=parent.cget("bg"),
                         bd=0, highlightthickness=0, cursor="hand2", takefocus=1)
        self.color = bg
        self.fg = fg
        self.hover = hover or bg
        self.text = text
        self.outline_color = outline
        self.radius = corner
        self.command = command
        self.size = font_size
        self.weight = weight
        self.hovering = False
        self.bind("<Configure>", lambda event: self._paint())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", lambda event: self._click())
        self.bind("<Return>", lambda event: self._click())
        self.bind("<space>", lambda event: self._click())
        self._paint()

    def _paint(self):
        self.delete("all")
        w, h = max(1,self.winfo_width()), max(1,self.winfo_height())
        if self.outline_color:
            rounded(self, 1, 1, w-1, h-1, self.radius, self.outline_color)
            rounded(self, 2, 2, w-2, h-2, self.radius-1, self.hover if self.hovering else self.color)
        else:
            rounded(self, 1, 1, w-1, h-1, self.radius, self.hover if self.hovering else self.color)
        self.create_text(w/2, h/2, text=self.text, fill=self.fg,
                         font=f(self.size, self.weight))

    def configure_button(self, text=None, bg=None, hover=None, fg=None):
        if text is not None: self.text = text
        if bg is not None: self.color = bg
        if hover is not None: self.hover = hover
        if fg is not None: self.fg = fg
        self._paint()

    def _enter(self, event):
        self.hovering = True
        self._paint()

    def _leave(self, event):
        self.hovering = False
        self._paint()

    def _click(self):
        if callable(self.command):
            self.command()


class Toggle(tk.Canvas):
    def __init__(self, parent, variable: tk.BooleanVar, **kwargs):
        super().__init__(parent, width=51, height=29, bg=parent.cget("bg"),
                         bd=0, highlightthickness=0, cursor="hand2", **kwargs)
        self.variable = variable
        self.bind("<Button-1>", self._click)
        variable.trace_add("write", lambda *args: self.paint())
        self.paint()

    def paint(self):
        self.delete("all")
        value=self.variable.get()
        rounded(self, 1, 1, 50, 28, 14, MINT if value else BORDER)
        x = 36 if value else 15
        self.create_oval(x-10, 5, x+10, 25, fill=TEXT if value else MUTED, outline="")

    def _click(self, event):
        self.variable.set(not self.variable.get())


class TimerDial(tk.Canvas):
    def __init__(self, parent):
        super().__init__(parent, width=290, height=290, bg=parent.cget("bg"),
                         highlightthickness=0, bd=0)
        self.secs=1500
        self.total=1500
        self.mode="focus"
        self.active=False
        self.bind("<Configure>", lambda event: self.paint())
        self.paint()

    def update_state(self, secs: float, total: float, mode: str, active: bool):
        rounded_secs = max(0, math.ceil(secs))
        if (rounded_secs, total, mode, active) != (math.ceil(self.secs), self.total, self.mode, self.active):
            self.secs = secs
            self.total = total
            self.mode = mode
            self.active = active
            self.paint()

    def paint(self):
        self.delete("all")
        w,h=self.winfo_width(),self.winfo_height()
        if w<20 or h<20:
            w,h=290,290
        center=(w/2,h/2)
        diameter=min(w,h)-33
        r=diameter/2
        cx,cy=center
        accent=CORAL if self.mode=="focus" else MINT
        self.create_oval(cx-r+20,cy-r+20,cx+r-20,cy+r-20,
                         fill="#1B2B3B" if self.mode=="focus" else "#173333",outline="")
        self.create_oval(cx-r,cy-r,cx+r,cy+r,outline="#334557",width=13)
        fraction=max(0.0,min(1.0,1-self.secs/max(1,self.total)))
        # Tk arcs grow anticlockwise with positive extent; negative = clockwise.
        if fraction>0.0005:
            self.create_arc(cx-r,cy-r,cx+r,cy+r,start=90,extent=-359.9*fraction,
                            style="arc",outline=accent,width=13)
        angle=math.radians(90-360*fraction)
        dx=cx+r*math.cos(angle)
        dy=cy-r*math.sin(angle)
        self.create_oval(dx-7,dy-7,dx+7,dy+7,fill=accent,outline="")
        mins, secs=divmod(max(0,math.ceil(self.secs)),60)
        self.create_text(cx,cy-16,text=f"{mins:02d}:{secs:02d}",
                         font=f(49,"bold"),fill=TEXT)
        titles={"focus":"TIME TO FOCUS","short_break":"TAKE IT EASY","long_break":"A LITTLE RESET"}
        self.create_text(cx,cy+38,text=titles[self.mode],
                         font=f(10,"bold"),fill=accent)
        self.create_text(cx,cy+61,text="In the flow" if self.active else "Ready when you are",
                         font=f(10),fill=MUTED)


class WeekChart(tk.Canvas):
    def __init__(self, parent, height=106, large=False, **kwargs):
        super().__init__(parent, height=height, bg=parent.cget("bg"),
                         highlightthickness=0, bd=0, **kwargs)
        self.days = []
        self.large = large
        self.bind("<Configure>", lambda event: self.paint())

    def update_days(self, days):
        self.days = days
        self.paint()

    def paint(self):
        self.delete("all")
        w=self.winfo_width()
        h=self.winfo_height()
        if w<40 or h<30 or not self.days: return
        max_value=max(4,max((d["sessions"] for d in self.days), default=0))
        bottom=h-(28 if self.large else 23)
        top=35 if self.large else 16
        gap=(w-30)/7
        bar_width=min(32 if self.large else 19,gap*0.5)
        for i,d in enumerate(self.days):
            x=15+gap*(i+.5)
            value=d["sessions"]
            height=max(7,(bottom-top-8)*value/max_value) if value else 6
            color=CORAL if i==6 else (MINT_DARK if value else "#33475A")
            rounded(self, x-bar_width/2,bottom-height,x+bar_width/2,bottom,
                    min(7,bar_width/2),color)
            self.create_text(x,h-10,text=d["label"],font=f(9,"bold"),
                             fill=TEXT if i==6 else MUTED)
            if self.large and value:
                self.create_text(x,bottom-height-14,text=str(value),font=f(10,"bold"),fill=TEXT)


class FocusfieldApp:
    def __init__(self, root: tk.Tk):
        self.root=root
        self.engine=FocusEngine()
        self.page="today"
        self.tick_id=None
        self.last_render_key=None
        self.toast_id=None
        self.root.title("Focusfield — find your flow")
        self.root.geometry("1180x812")
        self.root.minsize(980,700)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW",self.close)
        self.root.attributes("-topmost",self.engine.settings["always_on_top"])
        try:
            self.root.iconphoto(True,tk.PhotoImage(file=str(Path(__file__).parent/"assets"/"focusfield.png")))
        except tk.TclError:
            pass
        self._build_shell()
        self.change_page("today")
        self._bind_shortcuts()
        self._tick()

    def _build_shell(self):
        self.sidebar=tk.Frame(self.root,bg=SIDEBAR,width=218)
        self.sidebar.pack(side="left",fill="y")
        self.sidebar.pack_propagate(False)
        self.main=tk.Frame(self.root,bg=BG)
        self.main.pack(side="left",fill="both",expand=True)

        brand=tk.Frame(self.sidebar,bg=SIDEBAR)
        brand.pack(fill="x",padx=25,pady=(34,0))
        mark=tk.Canvas(brand,width=38,height=38,bg=SIDEBAR,highlightthickness=0)
        mark.pack(side="left")
        rounded(mark,2,2,36,36,12,CORAL)
        mark.create_oval(11,11,27,27,fill=DARK_TEXT,outline="")
        mark.create_oval(17,10,28,21,fill=CORAL,outline="")
        label(brand,"focusfield",size=16,weight="bold",bg=SIDEBAR).pack(side="left",padx=(10,0))
        label(self.sidebar,"SPACE TO DO ONE THING WELL",size=8,fg=DIM,bg=SIDEBAR).pack(anchor="w",padx=26,pady=(13,40))

        label(self.sidebar,"YOUR SPACE",8,DIM,SIDEBAR,"bold").pack(anchor="w",padx=26,pady=(0,12))
        self.nav_buttons={}
        for key,icon,text in [("today","◷","Focus timer"),("insights","▥","Your insights"),("settings","⚙","Preferences")]:
            container=tk.Frame(self.sidebar,bg=SIDEBAR,height=46,cursor="hand2")
            container.pack(fill="x",padx=15,pady=4)
            container.pack_propagate(False)
            marker=tk.Frame(container,width=3,bg=SIDEBAR)
            marker.pack(side="left",fill="y")
            icon_label=label(container,icon,16,MUTED,SIDEBAR)
            icon_label.pack(side="left",padx=(16,12))
            text_label=label(container,text,11,MUTED,SIDEBAR)
            text_label.pack(side="left")
            for item in (container,marker,icon_label,text_label):
                item.bind("<Button-1>",lambda event,k=key:self.change_page(k))
            self.nav_buttons[key]=(container,marker,icon_label,text_label)

        tk.Frame(self.sidebar,bg=SIDEBAR).pack(fill="both",expand=True)
        quote=Card(self.sidebar,color="#152334",radius=16,pad=11,height=155)
        quote.pack(fill="x",padx=18,pady=(10,18))
        label(quote.inner,"✦",24,CORAL,quote.color).pack(anchor="w",padx=10,pady=(4,0))
        label(quote.inner,"Small steps.",12,TEXT,quote.color,"bold").pack(anchor="w",padx=10,pady=(3,0))
        label(quote.inner,"Steady progress.",12,TEXT,quote.color,"bold").pack(anchor="w",padx=10)
        label(quote.inner,"Good work begins small.",8,MUTED,quote.color,
              wraplength=166,justify="left").pack(anchor="w",padx=10,pady=(4,0))
        label(self.sidebar,"FOCUSFIELD  ·  v1.0",8,DIM,SIDEBAR).pack(anchor="w",padx=26,pady=(0,22))

    def _set_nav_active(self):
        for key,(container,marker,icon_label,text_label) in self.nav_buttons.items():
            active=key==self.page
            color=SIDEBAR_ACTIVE if active else SIDEBAR
            for widget in (container,marker,icon_label,text_label):
                widget.configure(bg=color)
            marker.configure(bg=CORAL if active else color)
            icon_label.configure(fg=CORAL if active else MUTED)
            text_label.configure(fg=TEXT if active else MUTED)

    def change_page(self,page):
        if page not in ("today","insights","settings"):return
        self.page=page
        self._set_nav_active()
        for child in self.main.winfo_children():
            child.destroy()
        self.last_render_key=None
        if page=="today":self._build_today()
        elif page=="insights":self._build_insights()
        else:self._build_settings()
        self.refresh(force=True)

    def _header(self,title,subtitle):
        head=tk.Frame(self.main,bg=BG)
        head.pack(fill="x",padx=31,pady=(26,26))
        left=tk.Frame(head,bg=BG)
        left.pack(side="left",fill="x",expand=True)
        label(left,title,25,TEXT,BG,"bold").pack(anchor="w")
        label(left,subtitle,10,MUTED,BG).pack(anchor="w",pady=(6,0))
        date_str=date.today().strftime("%a, %b %-d")
        date_box=tk.Frame(head,bg=PANEL)
        date_box.pack(side="right",anchor="center",pady=7)
        label(date_box,"◌  "+date_str,10,MUTED,PANEL).pack(padx=17,pady=10)
        return head

    def _build_today(self):
        self._header("Make room for focus.","A calmer way to get things done, one session at a time.")
        body=tk.Frame(self.main,bg=BG)
        body.pack(fill="both",expand=True,padx=31,pady=(0,20))
        body.grid_columnconfigure(0,weight=3,minsize=415)
        body.grid_columnconfigure(1,weight=2,minsize=300)
        body.grid_rowconfigure(0,weight=1)

        self.timer_card=Card(body,color=PANEL,radius=24,pad=23)
        self.timer_card.grid(row=0,column=0,sticky="nsew",padx=(0,17))
        self._build_timer(self.timer_card.inner)
        right=tk.Frame(body,bg=BG)
        right.grid(row=0,column=1,sticky="nsew")
        self.tasks_card=Card(right,color=PANEL,radius=22,pad=18)
        self.tasks_card.pack(fill="both",expand=True,pady=(0,17))
        self._build_tasks(self.tasks_card.inner)
        self.stats_card=Card(right,color=PANEL,radius=22,pad=16,height=258)
        self.stats_card.pack(fill="x")
        self._build_stats(self.stats_card.inner)

    def _build_timer(self,parent):
        top=tk.Frame(parent,bg=PANEL)
        top.pack(fill="x",padx=5,pady=(1,12))
        label(top,"YOUR FOCUS SPACE",9,MUTED,PANEL,"bold").pack(side="left")
        self.cycle_label=label(top,"SESSION 01",9,DIM,PANEL,"bold")
        self.cycle_label.pack(side="right")

        segments=tk.Frame(parent,bg=PANEL_DARK)
        segments.pack(pady=(7,0))
        self.mode_buttons={}
        for mode,text in [("focus","Focus"),("short_break","Short break"),("long_break","Long break")]:
            btn=PillButton(segments,text,command=lambda m=mode:self.select_mode(m),
                           width=110 if mode=="focus" else 114,height=38,bg=PANEL_DARK,
                           hover=PANEL_INNER,fg=MUTED,weight="normal",font_size=10,corner=12)
            btn.pack(side="left",padx=3,pady=4)
            self.mode_buttons[mode]=btn

        dial_wrap=tk.Frame(parent,bg=PANEL)
        dial_wrap.pack(fill="both",expand=True)
        self.dial=TimerDial(dial_wrap)
        self.dial.pack(anchor="center",expand=True,pady=(3,0))

        self.now_heading=label(parent,"NOW WORKING ON",8,DIM,PANEL,"bold")
        self.now_heading.pack(pady=(2,6))
        self.task_context=label(parent,"Choose a task to get started",12,TEXT,PANEL,"bold")
        self.task_context.pack(pady=(0,21))

        controls=tk.Frame(parent,bg=PANEL)
        controls.pack(pady=(0,22))
        self.reset_btn=PillButton(controls,"↺",self.reset_timer,width=53,height=50,
                                  bg=PANEL_INNER,fg=TEXT,hover=BORDER,font_size=20,corner=16,weight="normal")
        self.reset_btn.pack(side="left",padx=(0,9))
        self.play_btn=PillButton(controls,"▶   Start focusing",self.toggle_timer,
                                 width=200,height=50,bg=CORAL,fg=DARK_TEXT,hover=CORAL_LIGHT,
                                 font_size=11,corner=17)
        self.play_btn.pack(side="left",padx=(0,9))
        self.skip_btn=PillButton(controls,"⇥",self.skip_timer,width=53,height=50,
                                 bg=PANEL_INNER,fg=TEXT,hover=BORDER,font_size=19,corner=16,weight="normal")
        self.skip_btn.pack(side="left")

        line=tk.Frame(parent,height=1,bg=BORDER)
        line.pack(fill="x",padx=10)
        foot=tk.Frame(parent,bg=PANEL)
        foot.pack(fill="x",padx=9,pady=(17,2))
        label(foot,"✦  One thing at a time. The rest can wait.",9,MUTED,PANEL).pack(side="left")
        label(foot,"SPACE  pause / play",8,DIM,PANEL).pack(side="right")

    def _build_tasks(self,parent):
        parent.grid_columnconfigure(0,weight=1)
        parent.grid_rowconfigure(2,weight=1)
        head=tk.Frame(parent,bg=PANEL)
        head.grid(row=0,column=0,sticky="ew",pady=(3,5),padx=4)
        label(head,"Today's tasks",15,TEXT,PANEL,"bold").pack(side="left")
        self.task_count_label=label(head,"0 OPEN",8,MUTED,PANEL,"bold")
        self.task_count_label.pack(side="right")
        label(parent,"Clear the clutter. Pick your next step.",9,MUTED,PANEL).grid(row=1,column=0,sticky="w",padx=4,pady=(0,15))

        list_wrap=tk.Frame(parent,bg=PANEL)
        list_wrap.grid(row=2,column=0,sticky="nsew")
        self.task_canvas=tk.Canvas(list_wrap,bg=PANEL,highlightthickness=0,bd=0)
        self.task_canvas.pack(side="left",fill="both",expand=True)
        self.task_list_frame=tk.Frame(self.task_canvas,bg=PANEL)
        self.task_window=self.task_canvas.create_window((0,0),window=self.task_list_frame,anchor="nw")
        self.task_list_frame.bind("<Configure>",lambda event:self.task_canvas.configure(scrollregion=self.task_canvas.bbox("all")))
        self.task_canvas.bind("<Configure>",lambda event:self.task_canvas.itemconfigure(self.task_window,width=event.width))
        self.task_canvas.bind("<Enter>",lambda event:self._task_mousewheel(True))
        self.task_canvas.bind("<Leave>",lambda event:self._task_mousewheel(False))

        add_wrap=tk.Frame(parent,bg=PANEL_INNER)
        add_wrap.grid(row=3,column=0,sticky="ew",pady=(13,2),padx=1)
        self.task_entry=tk.Entry(add_wrap,bg=PANEL_INNER,fg=MUTED,insertbackground=TEXT,
                                 font=f(10),bd=0,highlightthickness=0,relief="flat")
        self.task_entry.insert(0,"Add a task...")
        self.placeholder=True
        self.task_entry.pack(side="left",fill="x",expand=True,padx=(13,4),pady=13)
        self.task_entry.bind("<FocusIn>",self._entry_focus_in)
        self.task_entry.bind("<FocusOut>",self._entry_focus_out)
        self.task_entry.bind("<Return>",lambda event:self.add_task())
        add_btn=tk.Label(add_wrap,text="+",font=f(19,"bold"),bg=PANEL_INNER,fg=CORAL,cursor="hand2")
        add_btn.pack(side="right",padx=(2,15))
        add_btn.bind("<Button-1>",lambda event:self.add_task())
        self.refresh_tasks()

    def _task_mousewheel(self,inside):
        if inside:
            self.task_canvas.bind_all("<MouseWheel>",self._scroll_tasks)
            self.task_canvas.bind_all("<Button-4>",lambda e:self.task_canvas.yview_scroll(-1,"units"))
            self.task_canvas.bind_all("<Button-5>",lambda e:self.task_canvas.yview_scroll(1,"units"))
        else:
            self.task_canvas.unbind_all("<MouseWheel>")
            self.task_canvas.unbind_all("<Button-4>")
            self.task_canvas.unbind_all("<Button-5>")

    def _scroll_tasks(self,event):
        self.task_canvas.yview_scroll(-1 if event.delta>0 else 1,"units")

    def _entry_focus_in(self,event):
        if self.placeholder:
            self.task_entry.delete(0,"end")
            self.task_entry.configure(fg=TEXT)
            self.placeholder=False

    def _entry_focus_out(self,event):
        if not self.task_entry.get().strip():
            self.task_entry.delete(0,"end")
            self.task_entry.insert(0,"Add a task...")
            self.task_entry.configure(fg=MUTED)
            self.placeholder=True

    def add_task(self):
        if self.placeholder:return
        text=self.task_entry.get().strip()
        if not text:return
        self.engine.add_task(text)
        self.task_entry.delete(0,"end")
        self._entry_focus_out(None)
        self.refresh_tasks()
        self.refresh()
        self.toast("Task added to your focus list")

    def refresh_tasks(self):
        if not hasattr(self,"task_list_frame") or not self.task_list_frame.winfo_exists():return
        for child in self.task_list_frame.winfo_children(): child.destroy()
        open_count=sum(not t["done"] for t in self.engine.tasks)
        self.task_count_label.configure(text=f"{open_count} OPEN")
        if not self.engine.tasks:
            label(self.task_list_frame,"✦",30,DIM,PANEL).pack(pady=(27,4))
            label(self.task_list_frame,"A clear mind starts here.",11,TEXT,PANEL,"bold").pack()
            label(self.task_list_frame,"Add one small thing to work on.",9,MUTED,PANEL).pack(pady=(6,0))
            return
        sorted_tasks=sorted(self.engine.tasks,key=lambda t:t["done"])
        for t in sorted_tasks:
            task_id=t["id"]
            selected=task_id==self.engine.selected_task_id and not t["done"]
            row_bg=PANEL_INNER if selected else PANEL_DARK
            row=tk.Frame(self.task_list_frame,bg=row_bg,height=52,cursor="hand2")
            row.pack(fill="x",pady=(0,6),padx=(1,3))
            row.pack_propagate(False)
            active_bar=tk.Frame(row,bg=CORAL if selected else row_bg,width=3)
            active_bar.pack(side="left",fill="y")
            check=tk.Label(row,text="✓" if t["done"] else "○",font=f(16),bg=row_bg,
                           fg=MINT if t["done"] else MUTED,cursor="hand2")
            check.pack(side="left",padx=(12,10))
            check.bind("<Button-1>",lambda event,tid=task_id:self.toggle_task(tid))
            title=t["title"] if len(t["title"])<=34 else t["title"][:31]+"…"
            title_lbl=tk.Label(row,text=title,anchor="w",font=f(10,"bold" if selected else "normal"),
                               fg=DIM if t["done"] else TEXT,bg=row_bg,cursor="hand2")
            title_lbl.pack(side="left",fill="x",expand=True)
            delete=tk.Label(row,text="×",font=f(14),bg=row_bg,fg=DIM,cursor="hand2")
            delete.pack(side="right",padx=(4,11))
            delete.bind("<Button-1>",lambda event,tid=task_id:self.delete_task(tid))
            for item in (row,active_bar,title_lbl):
                item.bind("<Button-1>",lambda event,tid=task_id:self.select_task(tid))

    def select_task(self,task_id):
        self.engine.select_task(task_id)
        self.refresh_tasks()
        self.refresh(force=True)

    def toggle_task(self,task_id):
        self.engine.toggle_task(task_id)
        self.refresh_tasks()
        self.refresh(force=True)

    def delete_task(self,task_id):
        self.engine.delete_task(task_id)
        self.refresh_tasks()
        self.refresh(force=True)

    def _build_stats(self,parent):
        head=tk.Frame(parent,bg=PANEL)
        head.pack(fill="x",padx=4,pady=(0,12))
        label(head,"Today's rhythm",14,TEXT,PANEL,"bold").pack(side="left")
        label(head,"LAST 7 DAYS",8,DIM,PANEL,"bold").pack(side="right")
        metric=tk.Frame(parent,bg=PANEL)
        metric.pack(fill="x",padx=5)
        left=tk.Frame(metric,bg=PANEL)
        left.pack(side="left",fill="x",expand=True)
        self.minutes_stat=label(left,"0m",22,TEXT,PANEL,"bold")
        self.minutes_stat.pack(anchor="w")
        label(left,"Focus time",9,MUTED,PANEL).pack(anchor="w")
        right=tk.Frame(metric,bg=PANEL)
        right.pack(side="right",anchor="e")
        self.sessions_stat=label(right,"0 / 4",20,CORAL,PANEL,"bold")
        self.sessions_stat.pack(anchor="e")
        label(right,"Daily goal",9,MUTED,PANEL).pack(anchor="e")
        self.week_chart=WeekChart(parent,height=84)
        self.week_chart.pack(fill="x",pady=(12,1),padx=2)

    def _build_insights(self):
        self._header("Your momentum.","The little wins count. Here's how your focus is growing.")
        container=tk.Frame(self.main,bg=BG)
        container.pack(fill="both",expand=True,padx=31,pady=(0,22))
        stats=tk.Frame(container,bg=BG)
        stats.pack(fill="x",pady=(0,18))
        for col in range(3):
            stats.grid_columnconfigure(col,weight=1,uniform="metrics")
        total=sum(int(s.get("minutes",0)) for s in self.engine.sessions)
        today=self.engine.focus_stats()
        recent=self.engine.week_stats()
        self._metric_card(stats,"TODAY'S FOCUS",f"{today['minutes']} min","Every minute counts",0)
        self._metric_card(stats,"COMPLETED SESSIONS",str(len(self.engine.sessions)),"All-time total",1)
        self._metric_card(stats,"ALL-TIME FOCUS",f"{total//60}h {total%60}m","Time invested in you",2)
        lower=tk.Frame(container,bg=BG)
        lower.pack(fill="both",expand=True)
        lower.grid_columnconfigure(0,weight=3)
        lower.grid_columnconfigure(1,weight=2)
        lower.grid_rowconfigure(0,weight=1)
        graph=Card(lower,color=PANEL,pad=22)
        graph.grid(row=0,column=0,sticky="nsew",padx=(0,17))
        label(graph.inner,"This week's focus",17,TEXT,PANEL,"bold").pack(anchor="w",pady=(4,4))
        label(graph.inner,"Finished focus sessions over the last seven days",9,MUTED,PANEL).pack(anchor="w")
        chart=WeekChart(graph.inner,height=250,large=True)
        chart.pack(fill="both",expand=True,padx=10,pady=(17,15))
        chart.update_days(recent)
        label(graph.inner,"Keep going, at your own pace.",11,CORAL,PANEL,"bold").pack(anchor="w",pady=(2,7))
        history=Card(lower,color=PANEL,pad=21)
        history.grid(row=0,column=1,sticky="nsew")
        label(history.inner,"Recent sessions",16,TEXT,PANEL,"bold").pack(anchor="w",pady=(4,7))
        label(history.inner,"A record of the work you've done",9,MUTED,PANEL).pack(anchor="w",pady=(0,13))
        if not self.engine.sessions:
            label(history.inner,"No completed sessions yet.",11,TEXT,PANEL).pack(anchor="w",pady=(19,5))
            label(history.inner,"Finish your first focus timer to start a history.",9,MUTED,PANEL,
                  wraplength=250,justify="left").pack(anchor="w")
        else:
            for s in reversed(self.engine.sessions[-8:]):
                line=tk.Frame(history.inner,bg=PANEL_DARK)
                line.pack(fill="x",pady=4)
                left=tk.Frame(line,bg=PANEL_DARK)
                left.pack(side="left",fill="x",expand=True,padx=12,pady=9)
                title=s.get("task_title","Focus session")
                if len(title)>22:title=title[:20]+"…"
                label(left,title,10,TEXT,PANEL_DARK,"bold").pack(anchor="w")
                label(left,s.get("date",""),8,MUTED,PANEL_DARK).pack(anchor="w",pady=(3,0))
                label(line,f"{s.get('minutes',25)}m",11,CORAL,PANEL_DARK,"bold").pack(side="right",padx=10)

    def _metric_card(self,parent,title,value,description,index):
        card=Card(parent,color=PANEL,radius=19,pad=18,height=150)
        card.grid(row=0,column=index,sticky="ew",padx=(0,13 if index<2 else 0))
        label(card.inner,title,9,MUTED,PANEL,"bold").pack(anchor="w",pady=(5,8))
        label(card.inner,value,25,CORAL if index==1 else TEXT,PANEL,"bold").pack(anchor="w")
        label(card.inner,description,9,DIM,PANEL).pack(anchor="w",pady=(5,0))

    def _build_settings(self):
        self._header("Set your own pace.","Shape your sessions around how you work best.")
        wrapper=tk.Frame(self.main,bg=BG)
        wrapper.pack(fill="both",expand=True,padx=31,pady=(0,24))
        columns=tk.Frame(wrapper,bg=BG)
        columns.pack(fill="both",expand=True)
        columns.grid_columnconfigure(0,weight=1)
        columns.grid_columnconfigure(1,weight=1)
        columns.grid_rowconfigure(0,weight=1)
        left=Card(columns,color=PANEL,pad=22)
        left.grid(row=0,column=0,sticky="nsew",padx=(0,17))
        right=Card(columns,color=PANEL,pad=22)
        right.grid(row=0,column=1,sticky="nsew")
        label(left.inner,"Timer lengths",17,TEXT,PANEL,"bold").pack(anchor="w",pady=(5,6))
        label(left.inner,"Find your most productive rhythm.",9,MUTED,PANEL).pack(anchor="w",pady=(0,20))
        self.setting_vars={}
        for key,title,sub in [
            ("focus_minutes","Focus duration","Minutes per focus session"),
            ("short_break_minutes","Short break","A moment to reset"),
            ("long_break_minutes","Long break","A well-earned longer pause"),
            ("long_break_every","Long break interval","After this many focus sessions"),
            ("daily_goal","Daily session goal","A target, not a rule"),
        ]:
            row=tk.Frame(left.inner,bg=PANEL)
            row.pack(fill="x",pady=(0,22))
            info=tk.Frame(row,bg=PANEL)
            info.pack(side="left",fill="x",expand=True)
            label(info,title,11,TEXT,PANEL,"bold").pack(anchor="w")
            label(info,sub,9,MUTED,PANEL).pack(anchor="w",pady=(4,0))
            var=tk.IntVar(value=self.engine.settings[key])
            self.setting_vars[key]=var
            spin=tk.Spinbox(row,from_=BOUNDS[key][0],to=BOUNDS[key][1],textvariable=var,
                             width=4,font=f(12,"bold"),bg=PANEL_INNER,fg=TEXT,
                             buttonbackground=PANEL_INNER,insertbackground=TEXT,
                             highlightthickness=1,highlightbackground=BORDER,
                             highlightcolor=CORAL,relief="flat",bd=0,justify="center")
            spin.pack(side="right",ipady=9,padx=(9,2))
        label(right.inner,"Flow preferences",17,TEXT,PANEL,"bold").pack(anchor="w",pady=(5,6))
        label(right.inner,"Fewer interruptions, more intention.",9,MUTED,PANEL).pack(anchor="w",pady=(0,20))
        for key,title,sub in [
            ("auto_start_breaks","Auto-start breaks","Switch to rest without another click"),
            ("auto_start_focus","Auto-start focus","Resume work when breaks end"),
            ("desktop_notifications","Desktop notifications","A reminder when each session finishes"),
            ("sound","Timer sound","A gentle system bell at completion"),
            ("always_on_top","Keep on top","Pin the window above others"),
        ]:
            row=tk.Frame(right.inner,bg=PANEL)
            row.pack(fill="x",pady=(0,23))
            info=tk.Frame(row,bg=PANEL)
            info.pack(side="left",fill="x",expand=True)
            label(info,title,11,TEXT,PANEL,"bold").pack(anchor="w")
            label(info,sub,9,MUTED,PANEL).pack(anchor="w",pady=(4,0))
            var=tk.BooleanVar(value=self.engine.settings[key])
            self.setting_vars[key]=var
            Toggle(row,var).pack(side="right",padx=(10,1))

        footer=tk.Frame(wrapper,bg=BG)
        footer.pack(fill="x",pady=(18,0))
        self.save_btn=PillButton(footer,"Save preferences",self.save_settings,width=195,height=47,
                                 bg=CORAL,fg=DARK_TEXT,hover=CORAL_LIGHT)
        self.save_btn.pack(side="right")
        label(footer,"Shortcuts: Space  play/pause   ·   Ctrl+N  new task   ·   Ctrl+R  reset",9,MUTED,BG).pack(side="left",pady=14)

    def save_settings(self):
        changes={}
        try:
            for key,var in self.setting_vars.items(): changes[key]=var.get()
        except tk.TclError:
            self.toast("Use valid numbers for timer lengths")
            return
        self.engine.apply_settings(changes)
        self.root.attributes("-topmost",self.engine.settings["always_on_top"])
        self.toast("Preferences saved")

    def select_mode(self,mode):
        self.engine.set_mode(mode)
        self.engine.save()
        self.refresh(force=True)

    def toggle_timer(self):
        self.engine.toggle()
        self.engine.save()
        self.refresh(force=True)

    def reset_timer(self):
        self.engine.reset()
        self.engine.save()
        self.refresh(force=True)
        self.toast("Timer reset")

    def skip_timer(self):
        prev=self.engine.skip()
        self.engine.save()
        self.refresh(force=True)
        self.toast("Moved to your next " + ("break" if prev=="focus" else "focus session"))

    def _tick(self):
        finished=self.engine.check_finished()
        if finished is not None:
            self.engine.save()
            self._notify_finished(finished)
            if self.page=="today":self.refresh_tasks()
            elif self.page=="insights":self.change_page("insights")
        self.refresh()
        self.tick_id=self.root.after(230,self._tick)

    def refresh(self,force=False):
        if self.page!="today":return
        remaining=self.engine.seconds_remaining()
        key=(math.ceil(remaining),self.engine.mode,self.engine.running,
             self.engine.selected_task_id,len(self.engine.sessions),self.engine.cycle_count)
        if not force and key==self.last_render_key:return
        self.last_render_key=key
        self.dial.update_state(remaining,self.engine.duration(),self.engine.mode,self.engine.running)
        for mode,btn in self.mode_buttons.items():
            active=mode==self.engine.mode
            btn.configure_button(bg=PANEL_INNER if active else PANEL_DARK,
                                 fg=(CORAL if mode=="focus" else MINT) if active else MUTED,
                                 hover=PANEL_INNER)
        self.cycle_label.configure(text=f"SESSION {self.engine.cycle_count % self.engine.settings['long_break_every']+1:02d}")
        task_title=self.engine.active_task_title()
        mode=self.engine.mode
        if mode=="focus":
            self.now_heading.configure(text="NOW WORKING ON")
            self.task_context.configure(text=task_title or "Choose a task to get started",fg=TEXT)
        else:
            self.now_heading.configure(text="YOUR BREAK")
            self.task_context.configure(text="Relax. You've earned this moment.",fg=MINT)
        if self.engine.running:
            self.play_btn.configure_button(text="Ⅱ   Pause timer",bg=CORAL if mode=="focus" else MINT,
                                           hover=CORAL_LIGHT if mode=="focus" else "#A6E4D8")
        else:
            btn_text="▶   Start focusing" if mode=="focus" else "▶   Start break"
            self.play_btn.configure_button(text=btn_text,bg=CORAL if mode=="focus" else MINT,
                                           hover=CORAL_LIGHT if mode=="focus" else "#A6E4D8")
        stats=self.engine.focus_stats()
        self.minutes_stat.configure(text=f"{stats['minutes']}m")
        self.sessions_stat.configure(text=f"{stats['sessions']} / {self.engine.settings['daily_goal']}")
        self.week_chart.update_days(self.engine.week_stats())

    def _notify_finished(self,finished):
        if finished=="focus":
            title="Focus session complete ✦"
            msg="Wonderful work. Time for a gentle break."
        elif finished=="short_break":
            title="Break finished"
            msg="Ready to get back into your flow?"
        else:
            title="Long break finished"
            msg="Feeling refreshed? A new focus session is ready."
        if self.engine.settings["desktop_notifications"] and shutil.which("notify-send"):
            try:
                subprocess.Popen(["notify-send","-a","Focusfield","-i",
                    str(Path(__file__).parent/"assets"/"focusfield.png"),title,msg],
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            except OSError:
                pass
        if self.engine.settings["sound"]:
            try:self.root.bell()
            except tk.TclError:pass
        self.toast(msg)

    def toast(self,message):
        if self.toast_id is not None:
            try:self.root.after_cancel(self.toast_id)
            except tk.TclError:pass
        if hasattr(self,"toast_widget") and self.toast_widget.winfo_exists():
            self.toast_widget.destroy()
        outer=tk.Frame(self.main,bg=MINT,highlightthickness=0)
        outer.place(relx=.5,rely=.96,anchor="s")
        label(outer,"✦   "+message,10,DARK_TEXT,MINT,"bold").pack(padx=20,pady=11)
        self.toast_widget=outer
        self.toast_id=self.root.after(2900,self._hide_toast)

    def _hide_toast(self):
        if hasattr(self,"toast_widget") and self.toast_widget.winfo_exists():
            self.toast_widget.destroy()
        self.toast_id=None

    def _bind_shortcuts(self):
        self.root.bind_all("<space>",self._space_shortcut)
        self.root.bind_all("<Control-n>",self._new_task_shortcut)
        self.root.bind_all("<Control-r>",lambda event:self.reset_timer())

    def _space_shortcut(self,event):
        if isinstance(self.root.focus_get(),(tk.Entry,tk.Spinbox,tk.Text)):
            return
        if isinstance(self.root.focus_get(),PillButton):
            return
        self.toggle_timer()
        return "break"

    def _new_task_shortcut(self,event):
        if self.page!="today":self.change_page("today")
        self.task_entry.focus_set()
        return "break"

    def close(self):
        if self.tick_id is not None:
            self.root.after_cancel(self.tick_id)
        self.engine.save()
        self.root.destroy()


def main():
    try:
        root=tk.Tk()
    except tk.TclError as exc:
        print(f"Could not start Focusfield: {exc}. Make sure a graphical desktop is running.",file=sys.stderr)
        return 1
    FocusfieldApp(root)
    root.mainloop()
    return 0


if __name__=="__main__":
    raise SystemExit(main())
