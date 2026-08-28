#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PubMed PDF 下载器 (适配 Tab 分隔格式) —— Selenium 点击下载 + tkinter 界面
"""
import csv
import time
import threading
import shutil
import os
from pathlib import Path
from tkinter import *
from tkinter import ttk, filedialog, messagebox, scrolledtext

from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from openpyxl import Workbook

# ================= 配置区域 =================
# 【注意】请将 msedgedriver.exe 放在和本脚本同一个文件夹下，或者在此处修改绝对路径
# 如果放在同级目录下，保持默认即可
DEFAULT_DRIVER_PATH = Path.cwd() / "msedgedriver.exe"
# ===========================================

# 全局变量，用于存储用户选择的保存路径
CURRENT_SAVE_DIR = Path.home() / 'Desktop' / 'PubMedPDFs'


# ---------- 解析器 (修改核心) ----------
def parse_txt_tsv(txt_path):
    """
    解析 Tab 分隔的 txt 文件
    格式：PMID | DOI | PMCID | Title | Year ...
    """
    papers = []
    # 使用 csv 模块读取，delimiter='\t' 表示制表符分隔
    with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f, delimiter='\t')

        # 跳过第一行表头 (PMID, DOI, PMCID...)
        try:
            headers = next(reader)
        except StopIteration:
            return []

        for row_idx, row in enumerate(reader, 2):  # 从第2行开始计数
            # 确保行内至少有 5 列数据，防止空行报错
            if len(row) < 5:
                continue

            # 根据你的截图列顺序提取
            # Col 0: PMID, Col 1: DOI, Col 2: PMCID, Col 3: Title, Col 4: Year
            pmid = row[0].strip()
            pmcid_raw = row[2].strip()
            title = row[3].strip()
            year = row[4].strip()

            # 处理 PMCID 为 "None" 或空的情况
            real_pmc = None
            if pmcid_raw and pmcid_raw.lower() != 'none':
                real_pmc = pmcid_raw

            # 只要有标题且看起来有效，就加入列表
            if title:
                papers.append({
                    'title': title,
                    'year': year,
                    'pmc': real_pmc,
                    'pmid': pmid
                })

    return papers


# ---------- 工具 ----------
def safe_name(title):
    # 去掉文件名非法字符
    for ch in r'\/:*?"<>|':
        title = title.replace(ch, '_')
    # 限制长度防止报错
    return title[:150]


def build_pubmed_url(pmid: str):
    return f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/' if pmid else None


# ---------- Selenium 初始化 ----------
def build_driver(download_dir):
    """返回配置好的 Edge 实例，传入动态下载路径"""
    edge_options = Options()
    edge_options.add_experimental_option('prefs', {
        "plugins.always_open_pdf_externally": True,  # 禁止预览，直接下载
        "download.default_directory": str(download_dir),  # 动态设置下载路径
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    })

    # 检查驱动是否存在
    driver_path = DEFAULT_DRIVER_PATH
    if not driver_path.exists():
        # 如果默认路径没有，尝试寻找简单的 "msedgedriver.exe"
        if Path("msedgedriver.exe").exists():
            driver_path = Path("msedgedriver.exe")
        else:
            raise FileNotFoundError(f"找不到驱动文件：{DEFAULT_DRIVER_PATH}\n请确保 msedgedriver.exe 在脚本同级目录下。")

    service = Service(executable_path=str(driver_path))
    # 隐藏浏览器窗口运行（可选，调试时建议注释掉下面这行）
    # edge_options.add_argument('--headless')

    return webdriver.Edge(service=service, options=edge_options)


# ---------- 单篇下载 ----------
def download_one(pmc, title, year, pmid, log_func):
    """
    返回 (success:bool, local_pdf:Path or error_msg:str, pubmed_url:str)
    """
    pubmed_url = build_pubmed_url(pmid)

    # 1. 无 PMC 直接跳过
    if not pmc:
        return False, '无 PMC 号 (原数据为 None)', pubmed_url

    # 构造保存文件名
    final_pdf_path = CURRENT_SAVE_DIR / f'{year}_{safe_name(title)}.pdf'

    # 2. 已存在跳过
    if final_pdf_path.exists():
        log_func(f'  [跳过] 文件已存在: {final_pdf_path.name}')
        return True, final_pdf_path, pubmed_url

    driver = None
    try:
        # 每次下载启动一个新驱动实例以确保下载路径配置生效（虽然稍微慢点，但稳定）
        driver = build_driver(CURRENT_SAVE_DIR)

        article_url = f'https://pmc.ncbi.nlm.nih.gov/articles/{pmc}/'
        log_func(f'  正在访问: {article_url}')

        driver.execute_cdp_cmd('Page.setDownloadBehavior', {
            'behavior': 'allow',
            'downloadPath': str(CURRENT_SAVE_DIR)
        })

        driver.get(article_url)
        # 等待页面加载
        time.sleep(3)

        # 寻找pdf下载按钮
        # 策略：寻找 href 中包含 pdf 且有特定 data 标签的链接
        pdf_btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable(
                (By.XPATH, '//a[starts-with(@href,"pdf/") and contains(@data-ga-label,"pdf_download_desktop")]')
            )
        )

        # 获取默认文件名 (例如: fcimb-12-813790.pdf)
        href = pdf_btn.get_attribute('href')
        default_name = href.rsplit('/', 1)[-1]

        log_func(f'  检测到目标文件: [{default_name}]，等待下载完成...')

        # 点击下载（双击策略）
        pdf_btn.click()
        time.sleep(2)
        # 有时候只需点一次，有时候需要防弹窗，再次尝试点击确保触发
        try:
            pdf_btn.click()
        except:
            pass

        # 轮询检查文件是否出现在下载目录
        start_time = time.time()
        downloaded_temp_file = CURRENT_SAVE_DIR / default_name

        while time.time() - start_time < 60:  # 最多等60秒
            if downloaded_temp_file.exists():
                # 稍微等一下确保文件写入完成（防止0kb）
                time.sleep(10)
                # 重命名
                try:
                    shutil.move(str(downloaded_temp_file), str(final_pdf_path))
                    return True, final_pdf_path, pubmed_url
                except Exception as move_err:
                    # 如果移动失败（例如文件占位），尝试加个后缀
                    return False, f"重命名失败: {move_err}", pubmed_url
            time.sleep(1)

        return False, f'超时：文件 [{default_name}] 未在60秒内下载完成', pubmed_url

    except Exception as e:
        err_msg = str(e).split('\n')[0]  # 只取第一行错误信息
        if "element" in err_msg:
            return False, "未找到PDF下载按钮 (可能无权限或页面结构不同)", pubmed_url
        return False, f"错误: {err_msg}", pubmed_url
    finally:
        if driver:
            driver.quit()


# ---------- GUI 界面 ----------
class App:
    def __init__(self, root):
        self.root = root
        root.title('PubMed PDF 批量下载器 (TSV适配版)')
        root.geometry('750x550')
        self.papers = []

        # --- 第一行：选择文件 ---
        frm_top = Frame(root)
        frm_top.pack(pady=5, fill=X, padx=10)

        Label(frm_top, text='1. 列表文件(txt):').pack(side=LEFT)
        self.txt_var = StringVar()
        Entry(frm_top, textvariable=self.txt_var).pack(side=LEFT, fill=X, expand=True, padx=5)
        Button(frm_top, text='浏览', command=self.choose_txt).pack(side=LEFT)

        # --- 第二行：选择保存目录 ---
        frm_dir = Frame(root)
        frm_dir.pack(pady=5, fill=X, padx=10)

        Label(frm_dir, text='2. 保存目录:').pack(side=LEFT)
        self.dir_var = StringVar(value=str(CURRENT_SAVE_DIR))
        Entry(frm_dir, textvariable=self.dir_var).pack(side=LEFT, fill=X, expand=True, padx=5)
        Button(frm_dir, text='选择文件夹', command=self.choose_save_dir).pack(side=LEFT)

        # --- 日志区 ---
        self.log = scrolledtext.ScrolledText(root, height=18)
        self.log.pack(fill=BOTH, expand=True, padx=10, pady=5)

        # --- 进度条 ---
        self.bar = ttk.Progressbar(root, length=650)
        self.bar.pack(pady=5, padx=10, fill=X)

        # --- 按钮区 ---
        frm_btn = Frame(root)
        frm_btn.pack(pady=10)

        self.btn_parse = Button(frm_btn, text='解析文件', command=self.parse, width=15, bg='#e1f5fe')
        self.btn_down = Button(frm_btn, text='开始下载', command=self.download, state=DISABLED, width=15, bg='#e8f5e9')
        self.btn_parse.pack(side=LEFT, padx=20)
        self.btn_down.pack(side=LEFT, padx=20)

    def choose_txt(self):
        f = filedialog.askopenfilename(filetypes=[('Text Files', '*.txt'), ('All Files', '*.*')])
        if f:
            self.txt_var.set(f)

    def choose_save_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.dir_var.set(d)
            global CURRENT_SAVE_DIR
            CURRENT_SAVE_DIR = Path(d)

    def parse(self):
        path_str = self.txt_var.get()
        if not path_str:
            messagebox.showerror('错误', '请先选择 txt 文件！')
            return

        path = Path(path_str)
        if not path.is_file():
            messagebox.showerror('错误', '文件不存在！')
            return

        self.log_insert('正在解析...')
        try:
            # 调用新的解析函数
            self.papers = parse_txt_tsv(path)

            total = len(self.papers)
            has_pmc = sum(1 for p in self.papers if p['pmc'])

            self.log_insert(f'解析成功！\n共读取到 {total} 篇文献。\n其中 {has_pmc} 篇包含 PMC ID (可尝试下载)。\n')

            if total > 0:
                self.btn_down.config(state=NORMAL)
            else:
                self.log_insert("警告：未解析到任何数据，请检查 txt 文件格式是否正确（需为 Tab 分隔）。")

        except Exception as e:
            self.log_insert(f'解析失败：{e}')
            import traceback
            traceback.print_exc()

    def download(self):
        # 确认保存路径
        save_path = Path(self.dir_var.get())
        if not save_path.exists():
            try:
                save_path.mkdir(parents=True, exist_ok=True)
            except:
                messagebox.showerror('错误', '保存目录无法创建，请重新选择！')
                return

        global CURRENT_SAVE_DIR
        CURRENT_SAVE_DIR = save_path

        if not self.papers:
            messagebox.showerror('错误', '先解析！')
            return

        self.btn_down.config(state=DISABLED)
        self.btn_parse.config(state=DISABLED)
        threading.Thread(target=self.batch_down, daemon=True).start()

    def batch_down(self):
        total = len(self.papers)
        success_count = 0

        for idx, p in enumerate(self.papers, 1):
            self.bar.config(value=idx, maximum=total)
            self.log_insert(f'[{idx}/{total}] 处理: {p["title"][:40]}...')

            ok, info, pubmed_url = download_one(p['pmc'], p['title'], p['year'], p['pmid'], self.log_insert)

            p['ok'] = ok
            p['pubmed_url'] = pubmed_url
            p['info'] = info  # 记录详细信息用于Excel

            if ok:
                success_count += 1
                self.log_insert('  -> 成功 √\n')
            else:
                self.log_insert(f'  -> 失败 × ({info})\n')

            # 这里的sleep不需要太长，因为download_one里面有等待
            time.sleep(0.5)

            # --- 生成 Excel 报告 ---
        try:
            report_path = CURRENT_SAVE_DIR / f'下载报告_{time.strftime("%Y%m%d_%H%M%S")}.xlsx'
            wb = Workbook()
            ws = wb.active
            ws.append(['状态', '失败原因', '标题', '年份', 'PMC', 'PMID', 'PubMed链接'])

            for p in self.papers:
                status = '成功' if p.get('ok') else '失败'
                reason = '' if p.get('ok') else p.get('info')
                ws.append([status, reason, p['title'], p['year'], p.get('pmc'), p.get('pmid'), p['pubmed_url']])

                # 给最后一列加超链接
                if p['pubmed_url']:
                    ws.cell(row=ws.max_row, column=7).hyperlink = p['pubmed_url']

            wb.save(report_path)
            self.log_insert(f'\n===== 全部完成 =====')
            self.log_insert(f'成功: {success_count} / {total}')
            self.log_insert(f'详细报告已生成: {report_path}')
        except Exception as e:
            self.log_insert(f'Excel报告生成失败: {e}')

        messagebox.showinfo('完成', f'下载结束！\n成功：{success_count}\n失败：{total - success_count}')
        self.btn_down.config(state=NORMAL)
        self.btn_parse.config(state=NORMAL)

    def log_insert(self, msg):
        self.log.insert(END, msg + '\n')
        self.log.see(END)


if __name__ == '__main__':
    root = Tk()
    App(root)
    root.mainloop()