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

from core import BOUNDS, FocusEngine

from themes import COLOR_MODES, THEMES, get_palette

COLORS = get_palette()
FONT_FAMILY = "Cantarell"


def f(size: int, weight: str = "normal"):
    return (FONT_FAMILY, size, weight)


def label(parent, text, size=11, fg=None, bg=None, weight="normal", **kwargs):
    return tk.Label(parent, text=text, font=f(size, weight), fg=fg if fg is not None else COLORS["TEXT"],
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
    def __init__(self, parent, color=None, radius=22, pad=12, **kwargs):
        color = COLORS["PANEL"] if color is None else color
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
                 bg=None, fg=None, hover=None, font_size=11,
                 outline=None, weight="bold", corner=17):
        super().__init__(parent, width=width, height=height, bg=parent.cget("bg"),
                         bd=0, highlightthickness=0, cursor="hand2", takefocus=1)
        bg = COLORS["ACCENT"] if bg is None else bg
        fg = COLORS["BUTTON_TEXT"] if fg is None else fg
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
        self.bind("<FocusIn>", lambda event: self._paint())
        self.bind("<FocusOut>", lambda event: self._paint())
        self.bind("<Return>", lambda event: self._click())
        self.bind("<space>", lambda event: self._click())
        self._paint()

    def _paint(self):
        self.delete("all")
        w, h = max(1,self.winfo_width()), max(1,self.winfo_height())
        border = COLORS["TEXT"] if self.focus_get() is self else self.outline_color
        if border:
            rounded(self, 1, 1, w-1, h-1, self.radius, border)
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
        return "break"


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
        rounded(self, 1, 1, 50, 28, 14, COLORS["SECONDARY"] if value else COLORS["BORDER"])
        x = 36 if value else 15
        self.create_oval(x-10, 5, x+10, 25, fill=COLORS["BUTTON_TEXT"] if value else COLORS["MUTED"], outline="")

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
        accent=COLORS["ACCENT"] if self.mode=="focus" else COLORS["SECONDARY"]
        self.create_oval(cx-r+20,cy-r+20,cx+r-20,cy+r-20,
                         fill=COLORS["FOCUS_SURFACE"] if self.mode=="focus" else COLORS["BREAK_SURFACE"],outline="")
        self.create_oval(cx-r,cy-r,cx+r,cy+r,outline=COLORS["BORDER"],width=13)
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
                         font=f(49,"bold"),fill=COLORS["TEXT"])
        titles={"focus":"TIME TO FOCUS","short_break":"TAKE IT EASY","long_break":"A LITTLE RESET"}
        self.create_text(cx,cy+38,text=titles[self.mode],
                         font=f(10,"bold"),fill=accent)
        self.create_text(cx,cy+61,text="In the flow" if self.active else "Ready when you are",
                         font=f(10),fill=COLORS["MUTED"])


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
            color=COLORS["ACCENT"] if i==6 else (COLORS["SECONDARY"] if value else COLORS["BORDER"])
            rounded(self, x-bar_width/2,bottom-height,x+bar_width/2,bottom,
                    min(7,bar_width/2),color)
            self.create_text(x,h-10,text=d["label"],font=f(9,"bold"),
                             fill=COLORS["TEXT"] if i==6 else COLORS["MUTED"])
            if self.large and value:
                self.create_text(x,bottom-height-14,text=str(value),font=f(10,"bold"),fill=COLORS["TEXT"])


class FocusfieldApp:
    def __init__(self, root: tk.Tk):
        self.root=root
        self.engine=FocusEngine()
        COLORS.update(get_palette(self.engine.settings["color_mode"], self.engine.settings["theme"]))
        self.task_draft=""
        self.preference_draft={}
        self.page="today"
        self.tick_id=None
        self.last_render_key=None
        self.toast_id=None
        self.root.title("Focusfield — find your flow")
        self.root.geometry("1180x812")
        self.root.minsize(980,700)
        self.root.configure(bg=COLORS["BG"])
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
        self.sidebar=tk.Frame(self.root,bg=COLORS["SIDEBAR"],width=218)
        self.sidebar.pack(side="left",fill="y")
        self.sidebar.pack_propagate(False)
        self.main=tk.Frame(self.root,bg=COLORS["BG"])
        self.main.pack(side="left",fill="both",expand=True)

        brand=tk.Frame(self.sidebar,bg=COLORS["SIDEBAR"])
        brand.pack(fill="x",padx=25,pady=(34,0))
        mark=tk.Canvas(brand,width=38,height=38,bg=COLORS["SIDEBAR"],highlightthickness=0)
        mark.pack(side="left")
        rounded(mark,2,2,36,36,12,COLORS["ACCENT"])
        mark.create_oval(11,11,27,27,fill=COLORS["BUTTON_TEXT"],outline="")
        mark.create_oval(17,10,28,21,fill=COLORS["ACCENT"],outline="")
        label(brand,"focusfield",size=16,weight="bold",bg=COLORS["SIDEBAR"]).pack(side="left",padx=(10,0))
        label(self.sidebar,"SPACE TO DO ONE THING WELL",size=8,fg=COLORS["DIM"],bg=COLORS["SIDEBAR"]).pack(anchor="w",padx=26,pady=(13,40))

        label(self.sidebar,"YOUR SPACE",8,COLORS["DIM"],COLORS["SIDEBAR"],"bold").pack(anchor="w",padx=26,pady=(0,12))
        self.nav_buttons={}
        for key,icon,text in [("today","◷","Focus timer"),("insights","▥","Your insights"),("settings","⚙","Preferences"),("appearance","◐","Appearance")]:
            container=tk.Frame(self.sidebar,bg=COLORS["SIDEBAR"],height=46,cursor="hand2")
            container.pack(fill="x",padx=15,pady=4)
            container.pack_propagate(False)
            marker=tk.Frame(container,width=3,bg=COLORS["SIDEBAR"])
            marker.pack(side="left",fill="y")
            icon_label=label(container,icon,16,COLORS["MUTED"],COLORS["SIDEBAR"])
            icon_label.pack(side="left",padx=(16,12))
            text_label=label(container,text,11,COLORS["MUTED"],COLORS["SIDEBAR"])
            text_label.pack(side="left")
            for item in (container,marker,icon_label,text_label):
                item.bind("<Button-1>",lambda event,k=key:self.change_page(k))
            self.nav_buttons[key]=(container,marker,icon_label,text_label)

        tk.Frame(self.sidebar,bg=COLORS["SIDEBAR"]).pack(fill="both",expand=True)
        mode_text="Switch to light" if self.engine.settings["color_mode"]=="dark" else "Switch to dark"
        self.mode_toggle=PillButton(self.sidebar,mode_text,self.toggle_color_mode,
                                    width=182,height=38,bg=COLORS["SIDEBAR_ACTIVE"],
                                    fg=COLORS["TEXT"],hover=COLORS["PANEL_INNER"],font_size=10)
        self.mode_toggle.pack(padx=18,pady=(6,2))
        quote=Card(self.sidebar,color=COLORS["QUOTE"],radius=16,pad=11,height=155)
        quote.pack(fill="x",padx=18,pady=(10,18))
        label(quote.inner,"✦",24,COLORS["ACCENT"],quote.color).pack(anchor="w",padx=10,pady=(4,0))
        label(quote.inner,"Small steps.",12,COLORS["TEXT"],quote.color,"bold").pack(anchor="w",padx=10,pady=(3,0))
        label(quote.inner,"Steady progress.",12,COLORS["TEXT"],quote.color,"bold").pack(anchor="w",padx=10)
        label(quote.inner,"Good work begins small.",8,COLORS["MUTED"],quote.color,
              wraplength=166,justify="left").pack(anchor="w",padx=10,pady=(4,0))
        label(self.sidebar,"FOCUSFIELD  ·  v1.1",8,COLORS["DIM"],COLORS["SIDEBAR"]).pack(anchor="w",padx=26,pady=(0,22))

    def _set_nav_active(self):
        for key,(container,marker,icon_label,text_label) in self.nav_buttons.items():
            active=key==self.page
            color=COLORS["SIDEBAR_ACTIVE"] if active else COLORS["SIDEBAR"]
            for widget in (container,marker,icon_label,text_label):
                widget.configure(bg=color)
            marker.configure(bg=COLORS["ACCENT"] if active else color)
            icon_label.configure(fg=COLORS["ACCENT"] if active else COLORS["MUTED"])
            text_label.configure(fg=COLORS["TEXT"] if active else COLORS["MUTED"])

    def _remember_page_inputs(self):
        if self.page=="today" and hasattr(self,"task_entry") and self.task_entry.winfo_exists():
            self.task_draft="" if self.placeholder else self.task_entry.get()
            self._task_mousewheel(False)
        if self.page=="settings" and hasattr(self,"save_btn") and self.save_btn.winfo_exists():
            self.preference_draft={key:var.get() for key,var in self.setting_vars.items()}

    def toggle_color_mode(self):
        mode="light" if self.engine.settings["color_mode"]=="dark" else "dark"
        self.set_appearance(color_mode=mode)

    def set_appearance(self,color_mode=None,theme=None):
        changes={}
        if color_mode is not None: changes["color_mode"]=color_mode
        if theme is not None: changes["theme"]=theme
        previous=(self.engine.settings["color_mode"],self.engine.settings["theme"])
        self.engine.apply_settings(changes)
        current=(self.engine.settings["color_mode"],self.engine.settings["theme"])
        if current==previous:return
        task_focused=self.page=="today" and self.root.focus_get() is getattr(self,"task_entry",None)
        self._remember_page_inputs()
        if self.toast_id is not None:
            self.root.after_cancel(self.toast_id)
            self.toast_id=None
        COLORS.update(get_palette(*current))
        self.sidebar.destroy()
        self.main.destroy()
        self.root.configure(bg=COLORS["BG"])
        self._build_shell()
        self.change_page(self.page)
        if task_focused:
            self.task_entry.focus_set()
            self.task_entry.icursor("end")

    def change_page(self,page):
        if page not in ("today","insights","settings","appearance"):return
        self._remember_page_inputs()
        self.page=page
        self._set_nav_active()
        for child in self.main.winfo_children():
            child.destroy()
        self.last_render_key=None
        if page=="today":self._build_today()
        elif page=="insights":self._build_insights()
        elif page=="settings":self._build_settings()
        else:self._build_appearance()
        self.refresh(force=True)

    def _header(self,title,subtitle):
        head=tk.Frame(self.main,bg=COLORS["BG"])
        head.pack(fill="x",padx=31,pady=(26,26))
        left=tk.Frame(head,bg=COLORS["BG"])
        left.pack(side="left",fill="x",expand=True)
        label(left,title,25,COLORS["TEXT"],COLORS["BG"],"bold").pack(anchor="w")
        label(left,subtitle,10,COLORS["MUTED"],COLORS["BG"]).pack(anchor="w",pady=(6,0))
        date_str=date.today().strftime("%a, %b %-d")
        date_box=tk.Frame(head,bg=COLORS["PANEL"])
        date_box.pack(side="right",anchor="center",pady=7)
        label(date_box,"◌  "+date_str,10,COLORS["MUTED"],COLORS["PANEL"]).pack(padx=17,pady=10)
        return head

    def _build_today(self):
        self._header("Make room for focus.","A calmer way to get things done, one session at a time.")
        body=tk.Frame(self.main,bg=COLORS["BG"])
        body.pack(fill="both",expand=True,padx=31,pady=(0,20))
        body.grid_columnconfigure(0,weight=3,minsize=415)
        body.grid_columnconfigure(1,weight=2,minsize=300)
        body.grid_rowconfigure(0,weight=1)

        self.timer_card=Card(body,color=COLORS["PANEL"],radius=24,pad=23)
        self.timer_card.grid(row=0,column=0,sticky="nsew",padx=(0,17))
        self._build_timer(self.timer_card.inner)
        right=tk.Frame(body,bg=COLORS["BG"])
        right.grid(row=0,column=1,sticky="nsew")
        self.tasks_card=Card(right,color=COLORS["PANEL"],radius=22,pad=18)
        self.tasks_card.pack(fill="both",expand=True,pady=(0,17))
        self._build_tasks(self.tasks_card.inner)
        self.stats_card=Card(right,color=COLORS["PANEL"],radius=22,pad=16,height=258)
        self.stats_card.pack(fill="x")
        self._build_stats(self.stats_card.inner)

    def _build_timer(self,parent):
        top=tk.Frame(parent,bg=COLORS["PANEL"])
        top.pack(fill="x",padx=5,pady=(1,12))
        label(top,"YOUR FOCUS SPACE",9,COLORS["MUTED"],COLORS["PANEL"],"bold").pack(side="left")
        self.cycle_label=label(top,"SESSION 01",9,COLORS["DIM"],COLORS["PANEL"],"bold")
        self.cycle_label.pack(side="right")

        segments=tk.Frame(parent,bg=COLORS["PANEL_DARK"])
        segments.pack(pady=(7,0))
        self.mode_buttons={}
        for mode,text in [("focus","Focus"),("short_break","Short break"),("long_break","Long break")]:
            btn=PillButton(segments,text,command=lambda m=mode:self.select_mode(m),
                           width=110 if mode=="focus" else 114,height=38,bg=COLORS["PANEL_DARK"],
                           hover=COLORS["PANEL_INNER"],fg=COLORS["MUTED"],weight="normal",font_size=10,corner=12)
            btn.pack(side="left",padx=3,pady=4)
            self.mode_buttons[mode]=btn

        dial_wrap=tk.Frame(parent,bg=COLORS["PANEL"])
        dial_wrap.pack(fill="both",expand=True)
        self.dial=TimerDial(dial_wrap)
        self.dial.pack(anchor="center",expand=True,pady=(3,0))

        self.now_heading=label(parent,"NOW WORKING ON",8,COLORS["DIM"],COLORS["PANEL"],"bold")
        self.now_heading.pack(pady=(2,6))
        self.task_context=label(parent,"Choose a task to get started",12,COLORS["TEXT"],COLORS["PANEL"],"bold")
        self.task_context.pack(pady=(0,21))

        controls=tk.Frame(parent,bg=COLORS["PANEL"])
        controls.pack(pady=(0,22))
        self.reset_btn=PillButton(controls,"↺",self.reset_timer,width=53,height=50,
                                  bg=COLORS["PANEL_INNER"],fg=COLORS["TEXT"],hover=COLORS["BORDER"],font_size=20,corner=16,weight="normal")
        self.reset_btn.pack(side="left",padx=(0,9))
        self.play_btn=PillButton(controls,"▶   Start focusing",self.toggle_timer,
                                 width=200,height=50,bg=COLORS["ACCENT"],fg=COLORS["BUTTON_TEXT"],hover=COLORS["ACCENT_HOVER"],
                                 font_size=11,corner=17)
        self.play_btn.pack(side="left",padx=(0,9))
        self.skip_btn=PillButton(controls,"⇥",self.skip_timer,width=53,height=50,
                                 bg=COLORS["PANEL_INNER"],fg=COLORS["TEXT"],hover=COLORS["BORDER"],font_size=19,corner=16,weight="normal")
        self.skip_btn.pack(side="left")

        line=tk.Frame(parent,height=1,bg=COLORS["BORDER"])
        line.pack(fill="x",padx=10)
        foot=tk.Frame(parent,bg=COLORS["PANEL"])
        foot.pack(fill="x",padx=9,pady=(17,2))
        label(foot,"✦  One thing at a time. The rest can wait.",9,COLORS["MUTED"],COLORS["PANEL"]).pack(side="left")
        label(foot,"SPACE  pause / play",8,COLORS["DIM"],COLORS["PANEL"]).pack(side="right")

    def _build_tasks(self,parent):
        parent.grid_columnconfigure(0,weight=1)
        parent.grid_rowconfigure(2,weight=1)
        head=tk.Frame(parent,bg=COLORS["PANEL"])
        head.grid(row=0,column=0,sticky="ew",pady=(3,5),padx=4)
        label(head,"Today's tasks",15,COLORS["TEXT"],COLORS["PANEL"],"bold").pack(side="left")
        self.task_count_label=label(head,"0 OPEN",8,COLORS["MUTED"],COLORS["PANEL"],"bold")
        self.task_count_label.pack(side="right")
        label(parent,"Clear the clutter. Pick your next step.",9,COLORS["MUTED"],COLORS["PANEL"]).grid(row=1,column=0,sticky="w",padx=4,pady=(0,15))

        list_wrap=tk.Frame(parent,bg=COLORS["PANEL"])
        list_wrap.grid(row=2,column=0,sticky="nsew")
        self.task_canvas=tk.Canvas(list_wrap,bg=COLORS["PANEL"],highlightthickness=0,bd=0)
        self.task_canvas.pack(side="left",fill="both",expand=True)
        self.task_list_frame=tk.Frame(self.task_canvas,bg=COLORS["PANEL"])
        self.task_window=self.task_canvas.create_window((0,0),window=self.task_list_frame,anchor="nw")
        self.task_list_frame.bind("<Configure>",lambda event:self.task_canvas.configure(scrollregion=self.task_canvas.bbox("all")))
        self.task_canvas.bind("<Configure>",lambda event:self.task_canvas.itemconfigure(self.task_window,width=event.width))
        self.task_canvas.bind("<Enter>",lambda event:self._task_mousewheel(True))
        self.task_canvas.bind("<Leave>",lambda event:self._task_mousewheel(False))

        add_wrap=tk.Frame(parent,bg=COLORS["PANEL_INNER"])
        add_wrap.grid(row=3,column=0,sticky="ew",pady=(13,2),padx=1)
        self.task_entry=tk.Entry(add_wrap,bg=COLORS["PANEL_INNER"],fg=COLORS["MUTED"],insertbackground=COLORS["TEXT"],
                                 font=f(10),bd=0,highlightthickness=0,relief="flat")
        self.task_entry.insert(0,self.task_draft or "Add a task...")
        self.placeholder=not bool(self.task_draft)
        self.task_entry.configure(fg=COLORS["MUTED"] if self.placeholder else COLORS["TEXT"])
        self.task_entry.pack(side="left",fill="x",expand=True,padx=(13,4),pady=13)
        self.task_entry.bind("<FocusIn>",self._entry_focus_in)
        self.task_entry.bind("<FocusOut>",self._entry_focus_out)
        self.task_entry.bind("<Return>",lambda event:self.add_task())
        add_btn=tk.Label(add_wrap,text="+",font=f(19,"bold"),bg=COLORS["PANEL_INNER"],fg=COLORS["ACCENT"],cursor="hand2")
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
            self.task_entry.configure(fg=COLORS["TEXT"])
            self.placeholder=False

    def _entry_focus_out(self,event):
        if not self.task_entry.get().strip():
            self.task_entry.delete(0,"end")
            self.task_entry.insert(0,"Add a task...")
            self.task_entry.configure(fg=COLORS["MUTED"])
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
            label(self.task_list_frame,"✦",30,COLORS["DIM"],COLORS["PANEL"]).pack(pady=(27,4))
            label(self.task_list_frame,"A clear mind starts here.",11,COLORS["TEXT"],COLORS["PANEL"],"bold").pack()
            label(self.task_list_frame,"Add one small thing to work on.",9,COLORS["MUTED"],COLORS["PANEL"]).pack(pady=(6,0))
            return
        sorted_tasks=sorted(self.engine.tasks,key=lambda t:t["done"])
        for t in sorted_tasks:
            task_id=t["id"]
            selected=task_id==self.engine.selected_task_id and not t["done"]
            row_bg=COLORS["PANEL_INNER"] if selected else COLORS["PANEL_DARK"]
            row=tk.Frame(self.task_list_frame,bg=row_bg,height=52,cursor="hand2")
            row.pack(fill="x",pady=(0,6),padx=(1,3))
            row.pack_propagate(False)
            active_bar=tk.Frame(row,bg=COLORS["ACCENT"] if selected else row_bg,width=3)
            active_bar.pack(side="left",fill="y")
            check=tk.Label(row,text="✓" if t["done"] else "○",font=f(16),bg=row_bg,
                           fg=COLORS["SECONDARY"] if t["done"] else COLORS["MUTED"],cursor="hand2")
            check.pack(side="left",padx=(12,10))
            check.bind("<Button-1>",lambda event,tid=task_id:self.toggle_task(tid))
            title=t["title"] if len(t["title"])<=34 else t["title"][:31]+"…"
            title_lbl=tk.Label(row,text=title,anchor="w",font=f(10,"bold" if selected else "normal"),
                               fg=COLORS["DIM"] if t["done"] else COLORS["TEXT"],bg=row_bg,cursor="hand2")
            title_lbl.pack(side="left",fill="x",expand=True)
            delete=tk.Label(row,text="×",font=f(14),bg=row_bg,fg=COLORS["DIM"],cursor="hand2")
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
        head=tk.Frame(parent,bg=COLORS["PANEL"])
        head.pack(fill="x",padx=4,pady=(0,12))
        label(head,"Today's rhythm",14,COLORS["TEXT"],COLORS["PANEL"],"bold").pack(side="left")
        label(head,"LAST 7 DAYS",8,COLORS["DIM"],COLORS["PANEL"],"bold").pack(side="right")
        metric=tk.Frame(parent,bg=COLORS["PANEL"])
        metric.pack(fill="x",padx=5)
        left=tk.Frame(metric,bg=COLORS["PANEL"])
        left.pack(side="left",fill="x",expand=True)
        self.minutes_stat=label(left,"0m",22,COLORS["TEXT"],COLORS["PANEL"],"bold")
        self.minutes_stat.pack(anchor="w")
        label(left,"Focus time",9,COLORS["MUTED"],COLORS["PANEL"]).pack(anchor="w")
        right=tk.Frame(metric,bg=COLORS["PANEL"])
        right.pack(side="right",anchor="e")
        self.sessions_stat=label(right,"0 / 4",20,COLORS["ACCENT"],COLORS["PANEL"],"bold")
        self.sessions_stat.pack(anchor="e")
        label(right,"Daily goal",9,COLORS["MUTED"],COLORS["PANEL"]).pack(anchor="e")
        self.week_chart=WeekChart(parent,height=84)
        self.week_chart.pack(fill="x",pady=(12,1),padx=2)

    def _build_insights(self):
        self._header("Your momentum.","The little wins count. Here's how your focus is growing.")
        container=tk.Frame(self.main,bg=COLORS["BG"])
        container.pack(fill="both",expand=True,padx=31,pady=(0,22))
        stats=tk.Frame(container,bg=COLORS["BG"])
        stats.pack(fill="x",pady=(0,18))
        for col in range(3):
            stats.grid_columnconfigure(col,weight=1,uniform="metrics")
        total=sum(int(s.get("minutes",0)) for s in self.engine.sessions)
        today=self.engine.focus_stats()
        recent=self.engine.week_stats()
        self._metric_card(stats,"TODAY'S FOCUS",f"{today['minutes']} min","Every minute counts",0)
        self._metric_card(stats,"COMPLETED SESSIONS",str(len(self.engine.sessions)),"All-time total",1)
        self._metric_card(stats,"ALL-TIME FOCUS",f"{total//60}h {total%60}m","Time invested in you",2)
        lower=tk.Frame(container,bg=COLORS["BG"])
        lower.pack(fill="both",expand=True)
        lower.grid_columnconfigure(0,weight=3)
        lower.grid_columnconfigure(1,weight=2)
        lower.grid_rowconfigure(0,weight=1)
        graph=Card(lower,color=COLORS["PANEL"],pad=22)
        graph.grid(row=0,column=0,sticky="nsew",padx=(0,17))
        label(graph.inner,"This week's focus",17,COLORS["TEXT"],COLORS["PANEL"],"bold").pack(anchor="w",pady=(4,4))
        label(graph.inner,"Finished focus sessions over the last seven days",9,COLORS["MUTED"],COLORS["PANEL"]).pack(anchor="w")
        chart=WeekChart(graph.inner,height=250,large=True)
        chart.pack(fill="both",expand=True,padx=10,pady=(17,15))
        chart.update_days(recent)
        label(graph.inner,"Keep going, at your own pace.",11,COLORS["ACCENT"],COLORS["PANEL"],"bold").pack(anchor="w",pady=(2,7))
        history=Card(lower,color=COLORS["PANEL"],pad=21)
        history.grid(row=0,column=1,sticky="nsew")
        label(history.inner,"Recent sessions",16,COLORS["TEXT"],COLORS["PANEL"],"bold").pack(anchor="w",pady=(4,7))
        label(history.inner,"A record of the work you've done",9,COLORS["MUTED"],COLORS["PANEL"]).pack(anchor="w",pady=(0,13))
        if not self.engine.sessions:
            label(history.inner,"No completed sessions yet.",11,COLORS["TEXT"],COLORS["PANEL"]).pack(anchor="w",pady=(19,5))
            label(history.inner,"Finish your first focus timer to start a history.",9,COLORS["MUTED"],COLORS["PANEL"],
                  wraplength=250,justify="left").pack(anchor="w")
        else:
            for s in reversed(self.engine.sessions[-8:]):
                line=tk.Frame(history.inner,bg=COLORS["PANEL_DARK"])
                line.pack(fill="x",pady=4)
                left=tk.Frame(line,bg=COLORS["PANEL_DARK"])
                left.pack(side="left",fill="x",expand=True,padx=12,pady=9)
                title=s.get("task_title","Focus session")
                if len(title)>22:title=title[:20]+"…"
                label(left,title,10,COLORS["TEXT"],COLORS["PANEL_DARK"],"bold").pack(anchor="w")
                label(left,s.get("date",""),8,COLORS["MUTED"],COLORS["PANEL_DARK"]).pack(anchor="w",pady=(3,0))
                label(line,f"{s.get('minutes',25)}m",11,COLORS["ACCENT"],COLORS["PANEL_DARK"],"bold").pack(side="right",padx=10)

    def _metric_card(self,parent,title,value,description,index):
        card=Card(parent,color=COLORS["PANEL"],radius=19,pad=18,height=150)
        card.grid(row=0,column=index,sticky="ew",padx=(0,13 if index<2 else 0))
        label(card.inner,title,9,COLORS["MUTED"],COLORS["PANEL"],"bold").pack(anchor="w",pady=(5,8))
        label(card.inner,value,25,COLORS["ACCENT"] if index==1 else COLORS["TEXT"],COLORS["PANEL"],"bold").pack(anchor="w")
        label(card.inner,description,9,COLORS["DIM"],COLORS["PANEL"]).pack(anchor="w",pady=(5,0))

    def _build_settings(self):
        self._header("Set your own pace.","Shape your sessions around how you work best.")
        wrapper=tk.Frame(self.main,bg=COLORS["BG"])
        wrapper.pack(fill="both",expand=True,padx=31,pady=(0,24))
        columns=tk.Frame(wrapper,bg=COLORS["BG"])
        columns.pack(fill="both",expand=True)
        columns.grid_columnconfigure(0,weight=1)
        columns.grid_columnconfigure(1,weight=1)
        columns.grid_rowconfigure(0,weight=1)
        left=Card(columns,color=COLORS["PANEL"],pad=22)
        left.grid(row=0,column=0,sticky="nsew",padx=(0,17))
        right=Card(columns,color=COLORS["PANEL"],pad=22)
        right.grid(row=0,column=1,sticky="nsew")
        label(left.inner,"Timer lengths",17,COLORS["TEXT"],COLORS["PANEL"],"bold").pack(anchor="w",pady=(5,6))
        label(left.inner,"Find your most productive rhythm.",9,COLORS["MUTED"],COLORS["PANEL"]).pack(anchor="w",pady=(0,20))
        self.setting_vars={}
        for key,title,sub in [
            ("focus_minutes","Focus duration","Minutes per focus session"),
            ("short_break_minutes","Short break","A moment to reset"),
            ("long_break_minutes","Long break","A well-earned longer pause"),
            ("long_break_every","Long break interval","After this many focus sessions"),
            ("daily_goal","Daily session goal","A target, not a rule"),
        ]:
            row=tk.Frame(left.inner,bg=COLORS["PANEL"])
            row.pack(fill="x",pady=(0,22))
            info=tk.Frame(row,bg=COLORS["PANEL"])
            info.pack(side="left",fill="x",expand=True)
            label(info,title,11,COLORS["TEXT"],COLORS["PANEL"],"bold").pack(anchor="w")
            label(info,sub,9,COLORS["MUTED"],COLORS["PANEL"]).pack(anchor="w",pady=(4,0))
            var=tk.StringVar(value=self.preference_draft.get(key,self.engine.settings[key]))
            self.setting_vars[key]=var
            spin=tk.Spinbox(row,from_=BOUNDS[key][0],to=BOUNDS[key][1],textvariable=var,
                             width=4,font=f(12,"bold"),bg=COLORS["PANEL_INNER"],fg=COLORS["TEXT"],
                             buttonbackground=COLORS["PANEL_INNER"],insertbackground=COLORS["TEXT"],
                             highlightthickness=1,highlightbackground=COLORS["BORDER"],
                             highlightcolor=COLORS["ACCENT"],relief="flat",bd=0,justify="center")
            spin.pack(side="right",ipady=9,padx=(9,2))
            # Tk normalizes an empty draft when constructing a Spinbox.
            if key in self.preference_draft: var.set(self.preference_draft[key])
        label(right.inner,"Flow preferences",17,COLORS["TEXT"],COLORS["PANEL"],"bold").pack(anchor="w",pady=(5,6))
        label(right.inner,"Fewer interruptions, more intention.",9,COLORS["MUTED"],COLORS["PANEL"]).pack(anchor="w",pady=(0,20))
        for key,title,sub in [
            ("auto_start_breaks","Auto-start breaks","Switch to rest without another click"),
            ("auto_start_focus","Auto-start focus","Resume work when breaks end"),
            ("desktop_notifications","Desktop notifications","A reminder when each session finishes"),
            ("sound","Timer sound","A gentle system bell at completion"),
            ("always_on_top","Keep on top","Pin the window above others"),
        ]:
            row=tk.Frame(right.inner,bg=COLORS["PANEL"])
            row.pack(fill="x",pady=(0,23))
            info=tk.Frame(row,bg=COLORS["PANEL"])
            info.pack(side="left",fill="x",expand=True)
            label(info,title,11,COLORS["TEXT"],COLORS["PANEL"],"bold").pack(anchor="w")
            label(info,sub,9,COLORS["MUTED"],COLORS["PANEL"]).pack(anchor="w",pady=(4,0))
            var=tk.BooleanVar(value=self.preference_draft.get(key,self.engine.settings[key]))
            self.setting_vars[key]=var
            Toggle(row,var).pack(side="right",padx=(10,1))

        footer=tk.Frame(wrapper,bg=COLORS["BG"])
        footer.pack(fill="x",pady=(18,0))
        self.save_btn=PillButton(footer,"Save preferences",self.save_settings,width=195,height=47,
                                 bg=COLORS["ACCENT"],fg=COLORS["BUTTON_TEXT"],hover=COLORS["ACCENT_HOVER"])
        self.save_btn.pack(side="right")
        label(footer,"Shortcuts: Space  play/pause   ·   Ctrl+N  new task   ·   Ctrl+R  reset",9,COLORS["MUTED"],COLORS["BG"]).pack(side="left",pady=14)

    def _build_appearance(self):
        self._header("Make it feel like you.","Choose your light, then find your color.")
        body=tk.Frame(self.main,bg=COLORS["BG"])
        body.pack(fill="both",expand=True,padx=31,pady=(0,22))
        modes=tk.Frame(body,bg=COLORS["BG"])
        modes.pack(fill="x",pady=(0,18))
        label(modes,"Color mode",13,weight="bold").pack(side="left",padx=(0,24))
        self.appearance_mode_buttons={}
        for mode in COLOR_MODES:
            selected=mode==self.engine.settings["color_mode"]
            button=PillButton(modes,("✓  " if selected else "")+mode.title(),
                              lambda m=mode:self.set_appearance(color_mode=m),
                              width=130,height=40,bg=COLORS["PANEL_INNER"],
                              fg=COLORS["ACCENT"] if selected else COLORS["TEXT"],
                              hover=COLORS["PANEL"],outline=COLORS["ACCENT"] if selected else COLORS["BORDER"])
            button.pack(side="left",padx=(0,10))
            self.appearance_mode_buttons[mode]=button
        grid=tk.Frame(body,bg=COLORS["BG"])
        grid.pack(fill="both",expand=True)
        for index in range(2):
            grid.grid_columnconfigure(index,weight=1,uniform="themes")
            grid.grid_rowconfigure(index,weight=1,uniform="themes")
        self.theme_buttons={}
        for index,(key,theme) in enumerate(THEMES.items()):
            selected=key==self.engine.settings["theme"]
            palette=get_palette(self.engine.settings["color_mode"],key)
            card=Card(grid,pad=18,height=182)
            card.grid(row=index//2,column=index%2,sticky="nsew",
                      padx=(0,16 if index%2==0 else 0),pady=(0,14))
            label(card.inner,theme["name"],15,weight="bold").pack(anchor="w",pady=(1,4))
            label(card.inner,theme["description"],10,fg=COLORS["MUTED"],
                  wraplength=270,justify="left").pack(anchor="w")
            swatches=tk.Canvas(card.inner,width=240,height=32,bg=COLORS["PANEL"],highlightthickness=0)
            swatches.pack(anchor="w",pady=10)
            for pos,token in enumerate(("BG","PANEL_INNER","ACCENT","SECONDARY")):
                rounded(swatches,1+pos*60,1,55+pos*60,31,9,palette[token])
            button=PillButton(card.inner,"✓  Selected" if selected else "Use "+theme["name"],
                              lambda t=key:self.set_appearance(theme=t),width=172,height=36,
                              bg=palette["ACCENT"],fg=palette["BUTTON_TEXT"],hover=palette["ACCENT_HOVER"])
            button.pack(anchor="w")
            self.theme_buttons[key]=button
        label(body,"Appearance saves automatically. Your timer keeps running.",10,
              fg=COLORS["MUTED"]).pack(anchor="w",pady=(0,2))

    def save_settings(self):
        changes={}
        try:
            for key,var in self.setting_vars.items():
                changes[key]=int(var.get()) if key in BOUNDS else var.get()
        except (tk.TclError, ValueError):
            self.toast("Use valid numbers for timer lengths")
            return
        self.engine.apply_settings(changes)
        self.preference_draft={}
        for key,var in self.setting_vars.items(): var.set(self.engine.settings[key])
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
            btn.configure_button(bg=COLORS["PANEL_INNER"] if active else COLORS["PANEL_DARK"],
                                 fg=(COLORS["ACCENT"] if mode=="focus" else COLORS["SECONDARY"]) if active else COLORS["MUTED"],
                                 hover=COLORS["PANEL_INNER"])
        self.cycle_label.configure(text=f"SESSION {self.engine.cycle_count % self.engine.settings['long_break_every']+1:02d}")
        task_title=self.engine.active_task_title()
        mode=self.engine.mode
        if mode=="focus":
            self.now_heading.configure(text="NOW WORKING ON")
            self.task_context.configure(text=task_title or "Choose a task to get started",fg=COLORS["TEXT"])
        else:
            self.now_heading.configure(text="YOUR BREAK")
            self.task_context.configure(text="Relax. You've earned this moment.",fg=COLORS["SECONDARY"])
        if self.engine.running:
            self.play_btn.configure_button(text="Ⅱ   Pause timer",bg=COLORS["ACCENT"] if mode=="focus" else COLORS["SECONDARY"],
                                           hover=COLORS["ACCENT_HOVER"] if mode=="focus" else COLORS["SECONDARY_HOVER"])
        else:
            btn_text="▶   Start focusing" if mode=="focus" else "▶   Start break"
            self.play_btn.configure_button(text=btn_text,bg=COLORS["ACCENT"] if mode=="focus" else COLORS["SECONDARY"],
                                           hover=COLORS["ACCENT_HOVER"] if mode=="focus" else COLORS["SECONDARY_HOVER"])
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
        outer=tk.Frame(self.main,bg=COLORS["SECONDARY"],highlightthickness=0)
        outer.place(relx=.5,rely=.96,anchor="s")
        label(outer,"✦   "+message,10,COLORS["BUTTON_TEXT"],COLORS["SECONDARY"],"bold").pack(padx=20,pady=11)
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
        if self.toast_id is not None:
            self.root.after_cancel(self.toast_id)
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
