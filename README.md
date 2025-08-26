# 实时内存监控工具

一个使用 PyQt5 构建的桌面应用程序，用于实时监控系统内存和虚拟内存使用情况。界面简洁，支持图表展示，适合开发者或系统管理员快速查看arm资源占用。

---

## 项目特点

- 实时获取系统内存使用率
- 能看虚拟内存使用情况
- 有排序可用来查找占用最高/低的进程
- 图形化展示内存变化趋势

---

## 界面预览

> 启动后显示主窗口，包含内存使用率图表和数值信息  
> 可以导出json曲线
> 显示pid 进程名称 占用大小 占有率

---

## 安装与运行

### 克隆项目

```bash
git clone https://github.com/yourusername/memory-monitor.git
cd memory-monitor
```
## 项目结构

memory-monitor/
> cx.py               # 主程序入口
> 数据转图片.py        # 字面意思
> icon.png / icon.ico # 应用图标
> README.md           # 项目说明文件
> requirements.txt    # 依赖列表
