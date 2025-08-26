import sys
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QComboBox, QCheckBox
)
from PyQt5.QtCore import Qt
import pyqtgraph as pg
import os

class LogViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("内存日志图表查看器")
        self.resize(1000, 600)

        layout = QVBoxLayout(self)

        # 文件选择器
        self.combo = QComboBox()
        self.combo.addItems(["mem_log.json", "vms_log.json"])
        self.combo.currentTextChanged.connect(self.load_and_plot)
        layout.addWidget(QLabel("选择日志文件："))
        layout.addWidget(self.combo)

        # 功能开关
        self.chk_avg = QCheckBox("显示平均线")
        self.chk_peaks = QCheckBox("标记多个峰值")
        self.chk_hover = QCheckBox("启用悬停提示")
        for chk in [self.chk_avg, self.chk_peaks, self.chk_hover]:
            chk.stateChanged.connect(lambda _: self.load_and_plot(self.combo.currentText()))
            layout.addWidget(chk)

        # 图表区域
        self.plot = pg.PlotWidget()
        self.plot.setBackground("w")
        self.plot.showGrid(x=True, y=True)
        self.plot.setLabel("left", "内存使用量")
        self.plot.setLabel("bottom", "时间（秒）")
        layout.addWidget(self.plot)

        # 悬停提示组件
        self.vLine = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("gray", style=Qt.DashLine))
        self.hLine = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen("gray", style=Qt.DashLine))
        self.label = pg.TextItem("", anchor=(0,1), color="black")
        self.plot.addItem(self.vLine, ignoreBounds=True)
        self.plot.addItem(self.hLine, ignoreBounds=True)
        self.plot.addItem(self.label)
        self.proxy = pg.SignalProxy(self.plot.scene().sigMouseMoved, rateLimit=60, slot=self.mouse_moved)

        # 初次加载
        self.load_and_plot(self.combo.currentText())

    def load_and_plot(self, filename):
        self.plot.clear()

        if not os.path.exists(filename):
            self.plot.setTitle("文件不存在：" + filename)
            return

        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)

        if len(data) < 20:
            self.plot.setTitle("数据不足：" + filename)
            return

        # 去掉前10条异常数据
        data = data[10:]

        # 按类型筛选
        target_type = "mem" if "mem" in filename else "vms"
        filtered = [d for d in data if d.get("type") == target_type]

        if not filtered:
            self.plot.setTitle("没有有效数据")
            return

        times_raw = [d["timestamp"] for d in filtered]
        values = [d["value"] for d in filtered]
        t0 = times_raw[0]
        times = [round(t - t0, 2) for t in times_raw]

        self.plot.setTitle(f"{filename} - 共 {len(values)} 条记录")

        # 主曲线
        pen = pg.mkPen(color=(0, 120, 200), width=2)
        self.curve = self.plot.plot(times, values, pen=pen)

        # 平均线
        if self.chk_avg.isChecked():
            avg = sum(values) / len(values)
            avg_line = pg.InfiniteLine(pos=avg, angle=0, pen=pg.mkPen("green", style=Qt.DotLine))
            self.plot.addItem(avg_line)

        # 多个峰值标记（显著高的点）
        if self.chk_peaks.isChecked():
            threshold = max(values) * 0.98  # 取最高值的98%以上
            peak_points = [(times[i], values[i]) for i in range(len(values)) if values[i] >= threshold]
            if peak_points:
                scatter = pg.ScatterPlotItem(
                    [pt[0] for pt in peak_points],
                    [pt[1] for pt in peak_points],
                    symbol='o', size=10, brush='red'
                )
                self.plot.addItem(scatter)

        # 悬停提示开关
        self.label.setVisible(self.chk_hover.isChecked())
        self.vLine.setVisible(self.chk_hover.isChecked())
        self.hLine.setVisible(self.chk_hover.isChecked())

        # 保存数据用于悬停
        self.times = times
        self.values = values

    def mouse_moved(self, evt):
        if not self.chk_hover.isChecked():
            return
        pos = evt[0]
        if self.plot.sceneBoundingRect().contains(pos):
            mousePoint = self.plot.plotItem.vb.mapSceneToView(pos)
            x = mousePoint.x()
            y = mousePoint.y()
            self.vLine.setPos(x)
            self.hLine.setPos(y)

            # 找最近点
            if self.times:
                idx = min(range(len(self.times)), key=lambda i: abs(self.times[i] - x))
                self.label.setText(f"时间: {self.times[idx]} s\n值: {self.values[idx]:.2f}")
                self.label.setPos(self.times[idx], self.values[idx])

if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = LogViewer()
    viewer.show()
    sys.exit(app.exec_())
