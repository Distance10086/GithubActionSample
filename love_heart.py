import socket
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import openpyxl
from concurrent.futures import ThreadPoolExecutor, as_completed
from openpyxl.styles import Alignment
import re
import os
import time

DEFAULT_DNS = "223.5.5.5"
DEFAULT_DOMAIN_FILE = os.path.join(os.getcwd(), "domain.txt")

def get_ip_addresses(domain, dns_server):
    try:
        resolver = socket.gethostbyname_ex(domain)
        ip_addresses = resolver[2]
        return "\n".join(ip_addresses)
    except socket.gaierror:
        return "解析失败"

def read_domains(file_path):
    with open(file_path, 'r') as file:
        return [line.strip() for line in file]

def clean_ip_addresses(ip_addresses):
    # 去除单引号和双引号
    ip_addresses = re.sub(r"[\"']", "", ip_addresses)
    return ip_addresses

def extract_c_segment(ip_addresses):
    # 提取C段
    c_segments = []
    for ip in ip_addresses.split('\n'):
        parts = ip.split('.')
        if len(parts) >= 3:
            c_segment = '.'.join(parts[:3])
            c_segments.append(c_segment)
    return "\n".join(c_segments)

def write_to_excel(results, output_path):
    workbook = openpyxl.Workbook()

    # Sheet1
    sheet1 = workbook.active
    sheet1.title = "Domain IPs"
    sheet1.append(["域名", "IP地址", "C段"])

    for domain, ip_addresses in results:
        # 清理IP地址
        ip_addresses = clean_ip_addresses(ip_addresses)
        c_segment = extract_c_segment(ip_addresses)
        # 清理C段
        c_segment = clean_ip_addresses(c_segment)
        sheet1.append([domain, ip_addresses, c_segment])
        # 获取当前行的行号
        current_row = sheet1.max_row
        # 设置IP地址和C段单元格的文本自动换行
        sheet1.cell(row=current_row, column=2).alignment = Alignment(wrap_text=True)
        sheet1.cell(row=current_row, column=3).alignment = Alignment(wrap_text=True)

    # 自动设置列宽
    for column in sheet1.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        sheet1.column_dimensions[column_letter].width = adjusted_width

    # Sheet2
    sheet2 = workbook.create_sheet(title="Domain IPs Detail")
    sheet2.append(["域名", "IP地址", "C段"])

    for domain, ip_addresses in results:
        ip_addresses = clean_ip_addresses(ip_addresses)
        ips = ip_addresses.split('\n')
        for ip in ips:
            c_segment = extract_c_segment(ip)
            sheet2.append([domain, ip, c_segment])

    # 自动设置列宽
    for column in sheet2.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        sheet2.column_dimensions[column_letter].width = adjusted_width

    workbook.save(output_path)

def resolve_domains(domains, dns_server, progress_callback, log_callback, stop_event):
    results = []
    total = len(domains)
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=500) as executor:
        future_to_domain = {executor.submit(get_ip_addresses, domain, dns_server): domain for domain in domains}
        for i, future in enumerate(as_completed(future_to_domain)):
            if stop_event.is_set():
                break
            domain = future_to_domain[future]
            try:
                ip_addresses = future.result()
                results.append((domain, ip_addresses))
            except Exception as e:
                results.append((domain, f"解析失败: {e}"))
            progress_callback(i + 1, total)
            log_callback(i + 1, total, time.time() - start_time)

    elapsed_time = time.time() - start_time
    log_callback(total, total, elapsed_time)
    return results

class DomainResolverApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("域名批量解析")
        self.geometry("600x350")

        self.dns_server = tk.StringVar(value=DEFAULT_DNS)
        self.domain_file_path = tk.StringVar(value=DEFAULT_DOMAIN_FILE)
        self.stop_event = threading.Event()

        self.create_widgets()

    def create_widgets(self):
        # 使用grid布局管理器
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # DNS Server Input
        tk.Label(self, text="DNS 服务器:", anchor='w').grid(row=0, column=0, sticky='w')
        # 减少右边的padx值，使得输入框更靠近左侧文本标签
        tk.Entry(self, textvariable=self.dns_server, width=30).grid(row=0, column=1, sticky='ew')

        # Domain File Input
        domain_frame = tk.Frame(self)
        domain_frame.grid(row=1, column=0, columnspan=2, sticky='ew', padx=10, pady=5)

        # 居中对齐
        domain_frame.grid_columnconfigure(1, weight=1)

        tk.Label(domain_frame, text="域名文件:   ", anchor='w').grid(row=0, column=0, sticky='w')
        # 固定宽度为30
        tk.Entry(domain_frame, textvariable=self.domain_file_path, width=30).grid(row=0, column=1, sticky='ew')
        tk.Button(domain_frame, text="选择域名文件", command=self.choose_domain_file).grid(row=0, column=2, sticky='ew',
                                                                                           padx=(5, 0))

        # Progress Bar
        self.progress = ttk.Progressbar(self, mode="determinate")
        self.progress.grid(row=2, column=0, columnspan=2, sticky='ew', padx=10, pady=(0, 10))

        # Button Frame
        button_frame = tk.Frame(self)
        button_frame.grid(row=3, column=0, columnspan=2, sticky='ew', pady=10)
        tk.Button(button_frame, text="开始解析", command=self.start_resolving).grid(row=0, column=0, padx=5)
        tk.Button(button_frame, text="停止解析", command=self.stop_resolving).grid(row=0, column=1, padx=5)

        # Log Text Area
        self.log_text = tk.Text(self, height=10)
        self.log_text.grid(row=4, column=0, columnspan=2, sticky='nsew', padx=10, pady=(0, 5))

    def log_message(self, completed, total, elapsed_time):
        if completed == 0:
            self.log_text.insert(tk.END, "任务开始：\n", "bold")
            self.log_text.tag_configure("bold", font=("TkDefaultFont", 10, "bold"))
        elif completed == total:
            self.log_text.insert(tk.END, "任务结束：Excel处理中...\n", "bold")
        else:
            percent = (completed / total) * 100
            message = f"{completed}/{total} ({percent:.2f}%) - 总耗时: {elapsed_time:.2f}秒\n"
            self.log_text.insert(tk.END, message)
        self.log_text.see(tk.END)

    def choose_domain_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if file_path:
            self.domain_file_path.set(file_path)

    def start_resolving(self):
        if not self.domain_file_path.get():
            messagebox.showerror("错误", "请选择域名文件")
            return

        domain_file = self.domain_file_path.get()
        dns_server = self.dns_server.get()
        self.stop_event.clear()

        current_time = datetime.now().strftime("%Y%m%d%H%M%S")
        output_file = f'domain_ips{current_time}.xlsx'

        domains = read_domains(domain_file)
        total = len(domains)
        self.progress["maximum"] = total
        self.progress["value"] = 0

        def progress_callback(completed, total):
            self.progress["value"] = completed

        def on_complete(elapsed_time):
            messagebox.showinfo("完成", f"解析结果已保存到 {output_file}\n总耗时: {elapsed_time:.2f}秒")

        def run():
            start_time = time.time()
            results = resolve_domains(domains, dns_server, progress_callback, self.log_message, self.stop_event)
            if not self.stop_event.is_set():
                write_to_excel(results, output_file)
                elapsed_time = time.time() - start_time
                self.after(0, on_complete, elapsed_time)

        threading.Thread(target=run).start()

    def stop_resolving(self):
        self.stop_event.set()

if __name__ == "__main__":
    app = DomainResolverApp()
    app.mainloop()
