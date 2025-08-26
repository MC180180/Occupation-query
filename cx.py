import sys
import time
from collections import deque

import numpy as np
import psutil
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtGui import QColor, QBrush
from PyQt5.QtCore import Qt, QTimer
import pyqtgraph as pg
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QIcon

import json

def export_mem_log(self):
    with open("mem_log.json", "w", encoding="utf-8") as f:
        json.dump(self.mem_log, f, indent=2, ensure_ascii=False)

def export_vms_log(self):
    with open("vms_log.json", "w", encoding="utf-8") as f:
        json.dump(self.vms_log, f, indent=2, ensure_ascii=False)


class NumericItem(QTableWidgetItem):
    def __init__(self, value, fmt="{:.2f}", suffix=""):
        super().__init__(fmt.format(value) + suffix)
        self.value = value

    def __lt__(self, other):
        if isinstance(other, NumericItem):
            return self.value < other.value
        return super().__lt__(other)

class MonitorUI(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowIcon(QIcon("icon.ico"))
        self.setWindowTitle("实时数据监控")
        self.resize(1200, 800)
        self.mem_log = []
        self.vms_log = []
        self.mem_saved = 0
        self.vms_saved = 0


        # ——— 定义 11 个区间阈值（字节） + 对应浅色刷子 ———
        self.breakpoints = [
                                                                        1 * 1024**2,    # 1 MB
                                                                        100 * 1024**2,  # 100 MB
                                                                        1 * 1024**3,    # 1 GB
                                                                        3 * 1024**3,    # 3 GB
                                                                        8 * 1024**3,    # 8 GB
                                                                        16 * 1024**3,   # 16 GB
                                                                        64 * 1024**3,   # 64 GB
                                                                        128 * 1024**3,  # 128 GB
                                                                        256 * 1024**3,  # 256 GB
                                                                        1024 * 1024**3  # 1024 GB
        ]
        color_hex = [
                                                                        "#ffffff",  # 0-1MB    白
                                                                        "#e6f0ff",  # 1-100MB  浅蓝1
                                                                        "#cce0ff",  # 100MB-1GB 浅蓝2
                                                                        "#b3d1ff",  # 1-3GB   浅蓝3
                                                                        "#d0ffd0",  # 3-8GB   浅绿1
                                                                        "#b0ffb0",  # 8-16GB  浅绿2
                                                                        "#ffffcc",  # 16-64GB 浅黄1
                                                                        "#ffff99",  # 64-128GB 浅黄2
                                                                        "#ffcccc",  # 128-256GB 浅红1
                                                                        "#ff9999",  # 256-1024GB 浅红2
                                                                        "#e6ccff",  # 1024GB以上 浅紫
        ]
        self.brushes = [QBrush(QColor(c)) for c in color_hex]

        # ——— 主布局 & legend ———
        main_lay = QVBoxLayout(self)
        main_lay.addWidget(self._make_legend())

        # ——— 左右两表：Top512 物理 / 虚拟 内存 ———
        tbl_lay = QHBoxLayout()
        self.tbl_rss = self._make_table(
            ["PID", "进程名", "物理内存 (MB)", "占用 (%)"])
        self.tbl_vms = self._make_table(
            ["PID", "进程名", "虚拟内存 (MB)", "占用 (%)"])
        tbl_lay.addWidget(self._labeled("物理内存", self.tbl_rss))
        tbl_lay.addWidget(self._labeled("虚拟内存", self.tbl_vms))
        main_lay.addLayout(tbl_lay)
        
        # ——— 导出按钮和计数标签区 ———
        btn_lay = QHBoxLayout()
        
        # 物理内存导出按钮和标签
        btn_mem = QPushButton("导出物理内存日志")
        btn_mem.clicked.connect(self.export_mem_log)
        self.lbl_mem_saved = QLabel("已保存 0 条")
        mem_box = QVBoxLayout()
        mem_box.addWidget(btn_mem)
        mem_box.addWidget(self.lbl_mem_saved)
        btn_lay.addLayout(mem_box)
        
        # 虚拟内存导出按钮和标签
        btn_vms = QPushButton("导出虚拟内存日志")
        btn_vms.clicked.connect(self.export_vms_log)
        self.lbl_vms_saved = QLabel("已保存 0 条")
        vms_box = QVBoxLayout()
        vms_box.addWidget(btn_vms)
        vms_box.addWidget(self.lbl_vms_saved)
        btn_lay.addLayout(vms_box)
        
        # 添加到主布局中（在图表之前）
        main_lay.addLayout(btn_lay)


        # ——— 实时曲线区 ———
        plot_lay = QHBoxLayout()
        self.plot_mem, self.mem_curve, self.mem_avg = self._make_plot(
            "物理内存占用", line_color=(0, 180, 0), avg_color=(180, 230, 180))
        self.plot_vms, self.vms_curve, self.vms_avg = self._make_plot(
            "虚拟内存占用", line_color=(0, 120, 200), avg_color=(180, 200, 250))
        plot_lay.addWidget(self.plot_mem)
        plot_lay.addWidget(self.plot_vms)
        main_lay.addLayout(plot_lay)

        # ——— 定时器：表格 1 s，曲线 0.05 s ———
        t1 = QTimer(self)
        t1.timeout.connect(self.update_tables)
        t1.start(1000)
        t2 = QTimer(self)
        t2.timeout.connect(self.update_plots)
        t2.start(50)

        # 数据缓冲
        self.start_time = time.time()
        self.maxlen     = 2048
        self.ts         = deque(maxlen=self.maxlen)
        self.mem_used   = deque(maxlen=self.maxlen)
        self.vms_used   = deque(maxlen=self.maxlen)

    def export_mem_log(self):
        self.mem_saved += 1
        self.lbl_mem_saved.setText(f"已保存 {self.mem_saved} 条")
        self.mem_log.append({
            "timestamp": time.time(),
            "value": self.mem_used[-1] if self.mem_used else 0
        })
        # 保存到文件
        with open("mem_log.json", "w", encoding="utf-8") as f:
            json.dump(self.mem_log, f, indent=2, ensure_ascii=False)

    def export_vms_log(self):
        self.vms_saved += 1
        self.lbl_vms_saved.setText(f"已保存 {self.vms_saved} 条")
        self.vms_log.append({
            "timestamp": time.time(),
            "value": self.vms_used[-1] if self.vms_used else 0
        })
        # 保存到文件
        with open("vms_log.json", "w", encoding="utf-8") as f:
            json.dump(self.vms_log, f, indent=2, ensure_ascii=False)


    def _make_legend(self):
        """顶部 legend：色块 + 区间文本"""
        ranges = [
            "0-1MB", "1-100MB", "100MB-1GB", "1-3GB", "3-8GB",
            "8-16GB", "16-64GB", "64-128GB", "128-256GB",
            "256-1024GB", "1024GB以上"
        ]
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(5, 5, 5, 5)
        lay.setSpacing(12)
        for text, brush in zip(ranges, self.brushes):
            block = QLabel()
            block.setFixedSize(20, 20)
            block.setStyleSheet(
                f"background-color:{brush.color().name()};"
                "border:1px solid #ccc;"
            )
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignVCenter)
            lay.addWidget(block)
            lay.addWidget(lbl)
        lay.addStretch()
        return w

    def _make_table(self, headers):
        tbl = QTableWidget()
        tbl.setColumnCount(len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.setSortingEnabled(True)
        return tbl

    def _labeled(self, title, widget):
        lay = QVBoxLayout()
        lbl = QLabel(title)
        lbl.setStyleSheet("font-weight:bold;")
        lay.addWidget(lbl)
        lay.addWidget(widget)
        w = QWidget()
        w.setLayout(lay)
        return w

    def _make_plot(self, title, line_color, avg_color):
        p = pg.PlotWidget(title=title)
        p.setBackground('w')
        p.showGrid(x=True, y=True)
        p.setLabel('left', 'GB')
        p.setLabel('bottom', 'Time (s)')
        p.getViewBox().setMouseEnabled(x=False, y=False)

        solid = pg.mkPen(color=line_color, width=4)
        curve = p.plot(pen=solid)

        dash = pg.mkPen(color=avg_color, width=2, style=Qt.CustomDashLine)
        dash.setDashPattern([2, 1])
        avg_curve = p.plot(
            pen=dash,
            fillLevel=0,
            brush=pg.mkBrush(avg_color[0], avg_color[1], avg_color[2], 80)
        )

        

        return p, curve, avg_curve

    def update_tables(self):
        total = psutil.virtual_memory().total
        procs = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
            try:
                mi = proc.info['memory_info']
                procs.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'rss': mi.rss,
                    'vms': mi.vms
                })
            except:
                continue

        top_rss = sorted(procs, key=lambda x: x['rss'], reverse=True)[:512]
        top_vms = sorted(procs, key=lambda x: x['vms'], reverse=True)[:512]
        self._fill(self.tbl_rss, top_rss, 'rss', total)
        self._fill(self.tbl_vms, top_vms, 'vms', total)

    def _fill(self, tbl, data, key, total):
        tbl.setRowCount(len(data))
        for i, info in enumerate(data):
            size = info[key]
            mb   = size / 1024**2
            pct  = size / total * 100 if total else 0

            pid_item = QTableWidgetItem(str(info['pid']))
            name_item= QTableWidgetItem(info['name'])
            mb_item  = NumericItem(mb, fmt="{:.2f}")
            pct_item = NumericItem(pct, fmt="{:.1f}", suffix="%")


            brush = self._get_brush(size)
            mb_item.setBackground(brush)
            pct_item.setBackground(brush)

            tbl.setItem(i, 0, pid_item)
            tbl.setItem(i, 1, name_item)
            tbl.setItem(i, 2, mb_item)
            tbl.setItem(i, 3, pct_item)

    def _get_brush(self, size_bytes):
        for idx, bp in enumerate(self.breakpoints):
            if size_bytes <= bp:
                return self.brushes[idx]
        return self.brushes[-1]

    def update_plots(self):
        t   = time.time() - self.start_time
        mem = psutil.virtual_memory().used
        vms = psutil.virtual_memory().used + psutil.swap_memory().used

        self.ts.append(t)
        self.mem_used.append(mem / 1024**3)
        self.vms_used.append(vms / 1024**3)

        arr_t = np.array(self.ts)
        mask  = arr_t >= (t - 60)

        def avg_smooth(x, y):
            secs = np.floor(x).astype(int)
            ux   = np.unique(secs)
            uy   = np.array([y[secs==u].mean() for u in ux])
            if len(uy) >= 5:
                uy = np.convolve(uy, np.ones(5)/5, mode='same')
            return ux, uy

        # 物理内存
        total_gb = psutil.virtual_memory().total / 1024**3
        y_mem    = np.array(self.mem_used)
        self.mem_curve.setData(arr_t[mask], y_mem[mask])
        ax, ay   = avg_smooth(arr_t[mask], y_mem[mask])
        sx, sy   = self._make_step(ax, ay)
        self.mem_avg.setData(sx, sy)
        self.plot_mem.setYRange(0, total_gb, padding=0)
        self.plot_mem.setXRange(t - 60, t, padding=0)

        self.mem_log.append({
            "timestamp": t,
            "type": "mem",
            "value": self.mem_used[-1]
        })
        self.mem_saved += 1
        self.lbl_mem_saved.setText(f"已保存 {self.mem_saved} 条")


        # 虚拟内存
        max_gb   = (psutil.virtual_memory().total + psutil.swap_memory().total) / 1024**3
        y_vms    = np.array(self.vms_used)
        self.vms_curve.setData(arr_t[mask], y_vms[mask])
        bx, by   = avg_smooth(arr_t[mask], y_vms[mask])
        sx2, sy2 = self._make_step(bx, by)
        self.vms_avg.setData(sx2, sy2)
        self.plot_vms.setYRange(0, max_gb, padding=0)
        self.plot_vms.setXRange(t - 60, t, padding=0)

        self.vms_log.append({
            "timestamp": t,
            "type": "vms",
            "value": self.vms_used[-1]
        })
        self.vms_saved += 1
        self.lbl_vms_saved.setText(f"已保存 {self.vms_saved} 条")


    def _make_step(self, ux, uy):
        sx, sy = [], []
        for i in range(len(ux)):
            if i == 0:
                sx.append(ux[0]); sy.append(uy[0])
            else:
                sx.append(ux[i]);    sy.append(uy[i-1])
                sx.append(ux[i]);    sy.append(uy[i])
        return np.array(sx), np.array(sy)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MonitorUI()
    win.show()
    sys.exit(app.exec_())
