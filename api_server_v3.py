"""
利润率看板 V3 — 完整数据管道
1. ETL: \\192.168.16.31\...\*.xlsx → 清洗 → MySQL bi.pdd_web_profit_data
2. API: MySQL → 聚合 → JSON (FastAPI :8090)
3. 调度: 每小时自动 ETL + 手动 POST /api/v3/etl/run
"""
import os, sys, json, re, shutil, subprocess, tempfile, threading, time, uuid, math
from datetime import datetime, timedelta
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import pandas as pd
import numpy as np
import pymysql
from sqlalchemy import create_engine
from fastapi import FastAPI, Query, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # The dependency is listed in requirements.txt; this fallback keeps the
    # module importable in a minimal diagnostic shell.
    pass

# ============ 配置 ============
NETWORK_BASE = Path(os.getenv("PROFIT_NETWORK_BASE", r"\\192.168.16.34\d\财务\2026年\拼多多链接利润率\日利润率"))
PROMOTION_BASE = Path(os.getenv("PROFIT_PROMOTION_BASE", r"\\192.168.16.32\Users\bot\Desktop\A.影刀\拼多多\小时平台推广"))
LINK_INFO_BASE = Path(os.getenv("PROFIT_LINK_INFO_BASE", r"\\192.168.16.26\Users\Financial\Desktop\A.影刀\拼多多\链接信息"))
LOCAL_CACHE = Path(os.getenv("PROFIT_LOCAL_CACHE", str(Path(__file__).with_name("cache_v3_etl"))))
MYSQL_CFG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "view"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_PROFIT_DATABASE", "bi"),
    "charset": os.getenv("DB_CHARSET", "utf8mb4"),
}
TABLE_NAME = "pdd_web_profit_data"
LINK_INFO_TABLE = os.getenv("PROFIT_LINK_INFO_TABLE", "pdd_link_info")
PROMOTION_HOURLY_TABLE = os.getenv("PROFIT_PROMOTION_HOURLY_TABLE", "pdd_web_promotion_hourly")
API_PORT = int(os.getenv("PROFIT_API_PORT", "8090"))
ETL_INTERVAL = 3600  # 每小时

# 推广源文件结构：推广根目录 / 店铺名称 / 每日 xlsx。
# 每个文件只读取名称以“商品_分小时数据”开头的 sheet。
PROMOTION_SHEET_PREFIX = "商品_分小时数据"

# 原始推广明细的自然粒度是“店铺 + 商品ID + 日期 + 小时”。
# 这些字段在写入现有利润主表时会按“店铺 + 商品ID + 日期”汇总，
# 不覆盖主表已有的收入、利润和推广费字段。
PROMOTION_STRING_COLUMNS = [
    "出价方式", "商品名称", "推广场景", "推广名称", "分组", "是否已删除",
    "推广小时", "store", "推广来源文件",
]
PROMOTION_NUMERIC_COLUMNS = [
    "成交花费(元)", "总花费(元)", "交易额(元)", "净交易额(元)", "净成交笔数", "成交笔数",
    "直接交易额(元)", "间接交易额(元)", "直接成交笔数", "间接成交笔数",
    "曝光量", "点击量", "询单花费(元)", "询单量", "收藏花费(元)", "收藏量",
    "关注花费(元)", "关注量",
    "结算交易额(元)", "结算成交笔数",
    "每笔结算成交花费(元)", "每笔结算成交金额(元)",
    "平均收藏成本(元)", "平均关注成本(元)", "平均询单成本(元)",
    "全站推广费比", "净交易额占比", "净成交笔数占比", "结算投产比",
    "退款豁免率", "退单豁免率", "交易额结算率", "订单结算率",
    "实际投产比", "净实际投产比",
    "每笔净成交花费(元)", "每笔成交花费(元)", "每笔成交金额(元)",
    "每笔直接成交金额(元)", "每笔间接成交金额(元)",
]
PROMOTION_RAW_NUMERIC_COLUMNS = [
    "成交花费(元)", "总花费(元)", "交易额(元)", "净交易额(元)", "净成交笔数", "成交笔数",
    "直接交易额(元)", "间接交易额(元)", "直接成交笔数", "间接成交笔数",
    "曝光量", "点击量", "询单花费(元)", "询单量", "收藏花费(元)", "收藏量",
    "关注花费(元)", "关注量", "结算交易额(元)", "结算成交笔数",
    "每笔结算成交花费(元)", "每笔结算成交金额(元)",
]
PROMOTION_PERCENTAGE_COLUMNS = [
    "净交易额占比", "净成交笔数占比", "退款豁免率", "退单豁免率",
    "交易额结算率", "订单结算率",
]
PROMOTION_RATIO_COLUMNS = ["实际投产比", "净实际投产比", "结算投产比"]

PROMOTION_HOURLY_COLUMN_MAP = {
    "商品ID": "product_id", "日期": "data_date", "store": "store_name", "推广小时": "promotion_hour", "推广来源文件": "source_file",
    "出价方式": "bid_type", "商品名称": "product_name", "推广场景": "promotion_scene", "推广名称": "promotion_name", "分组": "group_name", "是否已删除": "is_deleted",
    "成交花费(元)": "spend", "总花费(元)": "total_spend", "交易额(元)": "revenue", "净交易额(元)": "net_revenue", "净成交笔数": "net_orders", "成交笔数": "orders",
    "直接交易额(元)": "direct_revenue", "间接交易额(元)": "indirect_revenue", "直接成交笔数": "direct_orders", "间接成交笔数": "indirect_orders",
    "结算交易额(元)": "settled_revenue", "结算成交笔数": "settled_orders", "每笔结算成交花费(元)": "avg_settled_order_spend", "每笔结算成交金额(元)": "avg_settled_order_revenue",
    "曝光量": "impressions", "点击量": "clicks", "询单花费(元)": "inquiry_spend", "询单量": "inquiries", "收藏花费(元)": "favorite_spend", "收藏量": "favorites", "关注花费(元)": "follow_spend", "关注量": "follows",
    "平均收藏成本(元)": "avg_favorite_cost", "平均关注成本(元)": "avg_follow_cost", "平均询单成本(元)": "avg_inquiry_cost", "全站推广费比": "site_promotion_ratio", "净交易额占比": "net_revenue_ratio", "净成交笔数占比": "net_orders_ratio", "结算投产比": "settled_roi", "退款豁免率": "refund_exemption_rate", "退单豁免率": "cancel_exemption_rate", "交易额结算率": "revenue_settlement_rate", "订单结算率": "order_settlement_rate", "实际投产比": "roi", "净实际投产比": "net_roi",
    "每笔净成交花费(元)": "avg_net_order_spend", "每笔成交花费(元)": "avg_order_spend", "每笔成交金额(元)": "avg_order_revenue", "每笔直接成交金额(元)": "avg_direct_order_revenue", "每笔间接成交金额(元)": "avg_indirect_order_revenue",
}
PROMOTION_DATA_COLUMNS = PROMOTION_STRING_COLUMNS + PROMOTION_NUMERIC_COLUMNS + ["推广数据匹配"]

app = FastAPI(title="利润率看板 V3 API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ============ 工具函数 ============
def get_mysql():
    return pymysql.connect(**MYSQL_CFG)

def safe_copy(remote, local_dir):
    """跨平台复制源文件到本地缓存目录。"""
    local_dir = Path(local_dir)
    local_dir.mkdir(parents=True, exist_ok=True)
    local_path = local_dir / remote.name
    shutil.copy2(remote, local_path)
    return local_path

def list_xlsx_files():
    """递归扫描利润率根目录下各月份文件夹中的 xlsx 文件。"""
    base = Path(NETWORK_BASE)
    if not base.is_dir():
        print(f"  ⚠ 利润率目录不存在或不可访问: {base}")
        return []

    files = []
    for month_dir in sorted((path for path in base.iterdir() if path.is_dir()), key=lambda path: path.name):
        for path in sorted(month_dir.glob("*.xlsx"), key=lambda item: item.name):
            if path.name.startswith("~$") or "拼多多链接利润率" not in path.name:
                continue
            files.append((month_dir.name, path))
    return files


def list_link_info_xlsx_files(folder_path=LINK_INFO_BASE):
    """列出链接信息目录中的 xlsx，并按文件数据日期倒序排列。"""
    folder = Path(folder_path)
    if not folder.is_dir():
        print(f"  ⚠ 链接信息目录不存在或不可访问: {folder}")
        return []
    files = [
        path for path in folder.rglob("*.xlsx")
        if path.is_file() and not path.name.startswith("~$")
    ]
    return sorted(files, key=lambda path: (extract_link_info_file_date(path) or "0000-00-00", path.stat().st_mtime, path.name), reverse=True)


def extract_link_info_file_date(filepath):
    """从链接信息文件名提取数据日期，兼容 YYYYMMDD 和 YYYY-MM-DD。"""
    matches = re.findall(r"(?<!\d)(20\d{2})[-_]?([01]\d)[-_]?([0-3]\d)(?!\d)", Path(filepath).stem)
    if not matches:
        return None
    value = pd.to_datetime("".join(matches[-1]), format="%Y%m%d", errors="coerce")
    return None if pd.isna(value) else value.strftime("%Y-%m-%d")


def _normalise_link_info_columns(df):
    """统一链接信息工作簿中的链接 ID 列名，保留原始字段。"""
    frame = df.copy()
    frame.columns = [str(column).strip() for column in frame.columns]
    frame = frame.loc[:, ~frame.columns.duplicated()]
    aliases = {"链接id": "链接ID", "链接 ID": "链接ID", "链接Id": "链接ID", "链接ID": "链接ID"}
    frame = frame.rename(columns={column: aliases[column] for column in frame.columns if column in aliases})
    if "链接ID" not in frame.columns:
        return None
    frame["链接ID"] = normalize_join_id(frame["链接ID"])
    return frame[frame["链接ID"].notna()].copy()


def _link_info_frame_date(frame, filepath):
    """获取链接信息文件的数据日期；优先文件名，兼容从数据时间列推断。"""
    filename_date = extract_link_info_file_date(filepath)
    if filename_date:
        return filename_date
    if "数据时间" in frame.columns:
        values = pd.to_datetime(frame["数据时间"], errors="coerce").dropna()
        if not values.empty:
            return values.max().strftime("%Y-%m-%d")
    return "0000-00-00"


def load_link_info_data(folder_path=LINK_INFO_BASE):
    """读取链接信息目录，按最新文件优先合并，并按链接ID保留第一条。"""
    files = list_link_info_xlsx_files(folder_path)
    stats = {"files_found": len(files), "files_processed": 0, "files_error": 0, "rows_before_dedup": 0, "rows_after_dedup": 0}
    frames = []
    for filepath in files:
        try:
            workbook = pd.ExcelFile(filepath)
            file_frames = []
            for sheet_name in workbook.sheet_names:
                raw = pd.read_excel(workbook, sheet_name=sheet_name)
                if raw is None or raw.empty:
                    continue
                normalised = _normalise_link_info_columns(raw)
                if normalised is not None and not normalised.empty:
                    file_frames.append(normalised)
            workbook.close()
            if file_frames:
                frame = pd.concat(file_frames, ignore_index=True)
                frame["__source_file_mtime"] = datetime.fromtimestamp(filepath.stat().st_mtime)
                frame["__source_data_date"] = _link_info_frame_date(frame, filepath)
                frames.append(frame)
                stats["files_processed"] += 1
        except Exception as exc:
            stats["files_error"] += 1
            print(f"  ⚠ 读取链接信息文件失败 {filepath.name}: {exc}")

    if not frames:
        return pd.DataFrame(), stats
    merged = pd.concat(frames, ignore_index=True)
    merged = merged.sort_values(["__source_data_date", "__source_file_mtime"], ascending=[False, False], kind="stable")
    stats["rows_before_dedup"] = len(merged)
    # 按文件数据日期倒序后，等价于 drop_duplicates(subset=['链接ID'], keep='first')。
    merged = merged.drop_duplicates(subset=["链接ID"], keep="first").reset_index(drop=True)
    merged = merged.drop(columns=["__source_file_mtime", "__source_data_date"], errors="ignore")
    stats["rows_after_dedup"] = len(merged)
    return merged, stats


def replace_link_info_table(conn, link_info):
    """用链接信息目录的最新去重快照替换链接信息表。"""
    if link_info is None or link_info.empty:
        return 0
    frame = link_info.copy().replace([np.inf, -np.inf], np.nan)
    frame = frame.where(pd.notna(frame), None)
    cur = conn.cursor()
    cur.execute(f"DROP TABLE IF EXISTS `{LINK_INFO_TABLE}`")
    definitions = ["id BIGINT AUTO_INCREMENT PRIMARY KEY"]
    for column in frame.columns:
        if column == "链接ID":
            definitions.append(f"`{column}` VARCHAR(200) NOT NULL")
        elif column == "数据时间":
            definitions.append(f"`{column}` DATETIME NULL")
        elif pd.api.types.is_numeric_dtype(frame[column]):
            definitions.append(f"`{column}` DOUBLE NULL")
        else:
            definitions.append(f"`{column}` TEXT NULL")
    definitions.append("INDEX idx_link_info_link (`链接ID`(64))")
    cur.execute(f"CREATE TABLE `{LINK_INFO_TABLE}` (" + ", ".join(definitions) + ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4")
    columns = list(frame.columns)
    insert_sql = f"INSERT INTO `{LINK_INFO_TABLE}` (" + ", ".join(f"`{column}`" for column in columns) + ") VALUES (" + ", ".join(["%s"] * len(columns)) + ")"
    rows = [tuple(None if pd.isna(value) else (value.item() if isinstance(value, np.generic) else value) for value in row) for row in frame.to_numpy()]
    for offset in range(0, len(rows), 500):
        cur.executemany(insert_sql, rows[offset:offset + 500])
    conn.commit()
    return len(rows)

# ============ ETL: xlsx → MySQL ============
def clean_percentage(val):
    """清洗百分比：'45.87%'→0.4587, 0.3864→0.3864, nan→0, -inf→0"""
    if val is None or (isinstance(val, float) and (pd.isna(val) or np.isinf(val))):
        return 0.0
    if isinstance(val, str):
        val = val.strip()
        if val.endswith("%"):
            try:
                return float(val[:-1]) / 100.0
            except ValueError:
                return 0.0
        # "int%" 这类异常值
        if "%" in val:
            return 0.0
    try:
        f = float(val)
        if np.isinf(f) or pd.isna(f):
            return 0.0
        # 如果已经是小数形式 (>1 可能是百分比整数形式，如 45 表示 45%)
        # 这里保持原值，不做假设
        return f
    except (ValueError, TypeError):
        return 0.0

def clean_product_code(code):
    """商品编码：按'-'切分取前段，为空填'暂无编码'"""
    if code is None or (isinstance(code, float) and pd.isna(code)):
        return "暂无编码"
    code = str(code).strip()
    if not code:
        return "暂无编码"
    return code.split("-")[0].strip() or "暂无编码"

def extract_date_from_filename(filename):
    """从文件名提取日期：拼多多链接利润率2026-06-01.xlsx → 2026-06-01"""
    name = Path(filename).stem
    m = re.search(r"(\d{4}-\d{2}-\d{2})", name)
    return m.group(1) if m else None

def process_single_xlsx(month, filepath, cache_dir):
    """处理单个 xlsx 文件，返回清洗后的 DataFrame"""
    try:
        local = safe_copy(filepath, cache_dir)
    except Exception as e:
        print(f"  ⚠ 复制失败 {filepath.name}: {e}")
        return None

    try:
        # 找到包含"链接"的 sheet
        xl = pd.ExcelFile(local)
        target_sheet = None
        for sn in xl.sheet_names:
            if "链接" in sn:
                target_sheet = sn
                break
        if not target_sheet:
            print(f"  ⚠ {filepath.name}: 未找到包含'链接'的sheet, sheets={xl.sheet_names}")
            xl.close()
            return None

        df = pd.read_excel(local, sheet_name=target_sheet)
        xl.close()
    except Exception as e:
        print(f"  ⚠ 读取失败 {filepath.name}: {e}")
        return None

    if df.empty or len(df) < 2:
        return None

    # 日期从文件名取
    file_date = extract_date_from_filename(filepath.name)
    if not file_date:
        print(f"  ⚠ 无法提取日期: {filepath.name}")
        return None

    # 识别并跳过汇总行（第一数据行"共计："）
    # 找到真正的列名行（通常是第0行）
    # 重新读取，使用第一行作为列名
    try:
        df = pd.read_excel(local, sheet_name=target_sheet, dtype=str)
        xl2 = pd.ExcelFile(local)
        df = pd.read_excel(local, sheet_name=target_sheet)
        xl2.close()
    except:
        return None

    # 标准化列名（去除空格）
    df.columns = [str(c).strip() for c in df.columns]

    # 过滤：链接id 不为空
    if "链接id" not in df.columns:
        print(f"  ⚠ {filepath.name}: 缺少'链接id'列, cols={list(df.columns)[:10]}")
        return None

    df = df[df["链接id"].notna() & (df["链接id"] != "")]
    if len(df) == 0:
        return None

    # 百分比列处理
    pct_cols = ["成本占比", "快递占比", "货品快递总和占比", "毛利率", "推广费占比", "利润率", "退货率"]
    for col in pct_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_percentage)

    # 数值列处理
    num_cols = ["单量", "收入", "成本", "快递", "成本+快递", "毛利",
                "技术服务费(1%)", "预估售后", "推广费", "运费险", "税费", "平台利润",
                "30天销量", "收藏"]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # 商品编码清洗
    if "商品编码" in df.columns:
        df["商品编码"] = df["商品编码"].apply(clean_product_code)

    # 添加数据日期
    df["数据日期"] = file_date
    df["来源文件"] = filepath.name

    # 重命名含特殊字符的列
    rename_map = {}
    for c in df.columns:
        if '(' in str(c) or ')' in str(c) or '%' in str(c):
            new_name = str(c).replace('(1%)', '').replace('(', '').replace(')', '').replace('%', 'pct').strip()
            rename_map[c] = new_name
    if rename_map:
        df = df.rename(columns=rename_map)

    # 保留需要的列
    keep_cols = ["店铺名称", "负责人", "商品标题", "链接id", "商品编码",
                 "单量", "收入", "成本", "成本占比", "快递", "快递占比",
                 "成本+快递", "货品快递总和占比", "毛利", "毛利率",
                 "技术服务费", "预估售后", "推广费", "推广费占比",
                 "运费险", "税费", "平台利润", "利润率", "数据日期", "来源文件"]
    available = [c for c in keep_cols if c in df.columns]
    df = df[available].copy()

    return df


def list_promotion_xlsx_files(folder_path=PROMOTION_BASE):
    """列出“店铺文件夹/每日文件.xlsx”，忽略 Excel 临时文件。"""
    folder = Path(folder_path)
    try:
        if not folder.is_dir():
            print(f"  ⚠ 推广目录不存在或不可访问: {folder}")
            return []
        files = []
        for store_dir in folder.iterdir():
            if not store_dir.is_dir():
                continue
            files.extend(
                p for p in store_dir.iterdir()
                if p.is_file()
                and p.suffix.lower() == ".xlsx"
                and not p.name.startswith("~$")
            )
        return sorted(files, key=lambda p: (p.parent.name, p.name))
    except OSError as e:
        print(f"  ⚠ 读取推广目录失败 {folder}: {e}")
        return []


def parse_promotion_file_date(filepath):
    """从每日推广文件名提取日期，兼容 20260712 和 2026-07-12 格式。"""
    date_matches = re.findall(r"(?<!\d)(20\d{2})[-_]?([01]\d)[-_]?([0-3]\d)(?!\d)", Path(filepath).stem)
    if not date_matches:
        return None
    start_date = pd.to_datetime("".join(date_matches[0]), format="%Y%m%d", errors="coerce")
    end_date = pd.to_datetime("".join(date_matches[-1]), format="%Y%m%d", errors="coerce")
    if pd.isna(start_date) or pd.isna(end_date):
        return None
    if start_date.date() != end_date.date():
        print(f"  ⚠ 推广文件不是单日范围，将使用起始日期: {Path(filepath).name}")
    return start_date.strftime("%Y-%m-%d")


def normalize_join_id(values):
    """统一商品 ID/链接 ID，避免 Excel 数值被读成带 .0 的字符串。"""
    result = values.astype("string").str.strip()
    result = result.str.replace(r"\.0$", "", regex=True)
    return result.mask(result.isin(["", "-", "nan", "None", "<NA>"]))


def clean_percentage_value(value):
    """将推广报表中的百分数字符串转为小数；例如 66.67% -> 0.6667。"""
    if value is None or (isinstance(value, float) and (pd.isna(value) or np.isinf(value))):
        return 0.0
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return 0.0
        if text.endswith("%"):
            try:
                return float(text[:-1].strip()) / 100.0
            except (TypeError, ValueError):
                return 0.0
        # 百分比列如果没有 %，仍按数值原样保留，避免擅自改变数据含义。
        value = text
    try:
        number = float(value)
        return 0.0 if np.isinf(number) or pd.isna(number) else number
    except (TypeError, ValueError):
        return 0.0


def safe_divide_series(numerator, denominator):
    """按行安全相除，分母为空或 0 时返回 0，避免产生 inf/NaN。"""
    left = pd.to_numeric(numerator, errors="coerce").fillna(0.0)
    right = pd.to_numeric(denominator, errors="coerce").fillna(0.0)
    return left.div(right.where(right.ne(0), np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def calculate_promotion_metrics(df):
    """补充推广报表中的衍生指标。"""
    df["平均收藏成本(元)"] = safe_divide_series(df["收藏花费(元)"], df["收藏量"])
    df["平均关注成本(元)"] = safe_divide_series(df["关注花费(元)"], df["关注量"])
    df["平均询单成本(元)"] = safe_divide_series(df["询单花费(元)"], df["询单量"])
    df["全站推广费比"] = safe_divide_series(df["直接交易额(元)"], df["总花费(元)"])
    df["净交易额占比"] = safe_divide_series(df["净交易额(元)"], df["交易额(元)"])
    df["实际投产比"] = safe_divide_series(df["交易额(元)"], df["总花费(元)"])
    df["净实际投产比"] = safe_divide_series(df["净交易额(元)"], df["总花费(元)"])
    df["每笔净成交花费(元)"] = safe_divide_series(df["总花费(元)"], df["净成交笔数"])
    df["每笔成交花费(元)"] = safe_divide_series(df["总花费(元)"], df["成交笔数"])
    df["每笔成交金额(元)"] = safe_divide_series(df["交易额(元)"], df["成交笔数"])
    df["每笔直接成交金额(元)"] = safe_divide_series(df["直接交易额(元)"], df["直接成交笔数"])
    df["每笔间接成交金额(元)"] = safe_divide_series(df["间接交易额(元)"], df["间接成交笔数"])
    return df


def process_single_promotion_xlsx(filepath):
    """读取一个店铺每日工作簿中的商品分小时明细 sheet。"""
    frames = []
    filepath = Path(filepath)
    file_date = parse_promotion_file_date(filepath)
    store_name = filepath.parent.name
    if not file_date:
        print(f"  ⚠ 无法从推广文件名提取日期: {filepath.name}")
        return None
    try:
        xls = pd.ExcelFile(filepath)
        sheet_names = [s for s in xls.sheet_names if str(s).startswith(PROMOTION_SHEET_PREFIX)]
        for sheet_name in sheet_names:
            raw = pd.read_excel(xls, sheet_name=sheet_name, header=None)
            if raw is None or raw.empty or len(raw.index) < 2:
                continue

            headers = [str(c).strip() if not pd.isna(c) else "" for c in raw.iloc[0].tolist()]
            if not headers or "商品ID" not in headers:
                print(f"  ⚠ {filepath.name}/{sheet_name}: 首行未找到商品ID字段")
                continue
            headers[0] = "推广小时"
            df = raw.iloc[1:].copy()
            df.columns = headers
            df = df.loc[:, [column for column in df.columns if column]]
            # 同一字段不应重复；若报表重复输出列，保留第一列。
            df = df.loc[:, ~df.columns.duplicated()]
            if "总营销花费(元)" in df.columns and "总花费(元)" not in df.columns:
                df = df.rename(columns={"总营销花费(元)": "总花费(元)"})

            required = {"商品ID", "总花费(元)", "推广小时"}
            missing = required.difference(df.columns)
            if missing:
                print(f"  ⚠ {filepath.name}/{sheet_name}: 缺少字段 {sorted(missing)}")
                continue

            df["商品ID"] = normalize_join_id(df["商品ID"])
            df["日期"] = file_date
            df["推广小时"] = df["推广小时"].astype("string").str.strip()
            df = df[
                df["商品ID"].notna()
                & df["推广小时"].notna()
                & df["推广小时"].ne("")
                & ~df["商品ID"].isin(["总计", "-"])
            ].copy()
            if df.empty:
                continue

            for col in PROMOTION_STRING_COLUMNS:
                if col == "store":
                    df[col] = store_name
                elif col == "推广来源文件":
                    df[col] = filepath.name
                elif col not in df.columns:
                    df[col] = ""
                else:
                    df[col] = df[col].fillna("").astype(str).str.strip()

            for col in PROMOTION_RAW_NUMERIC_COLUMNS:
                if col not in df.columns:
                    df[col] = 0.0
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

            # 报表中的“占比/率”通常是带 % 的字符串，不能直接 pd.to_numeric，
            # 否则例如“100.00%”会先变成 NaN，再被 fillna(0) 清成 0。
            for col in PROMOTION_PERCENTAGE_COLUMNS:
                if col not in df.columns:
                    df[col] = 0.0
                df[col] = df[col].apply(clean_percentage_value)

            # 投产比是倍数，不是百分比；保留 2.86 这类原始数值含义。
            for col in PROMOTION_RATIO_COLUMNS:
                if col not in df.columns:
                    df[col] = 0.0
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

            df = calculate_promotion_metrics(df)
            frames.append(df[["商品ID", "日期"] + PROMOTION_STRING_COLUMNS + PROMOTION_NUMERIC_COLUMNS])
        xls.close()
    except Exception as e:
        print(f"  ⚠ 读取推广文件失败 {filepath.name}: {e}")
        return None

    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def load_promotion_data(file_filter=None):
    """扫描店铺子目录，保留商品级分小时明细。"""
    files = list_promotion_xlsx_files()
    if file_filter:
        files = [filepath for filepath in files if file_filter(filepath)]
    stats = {
        "files_found": len(files),
        "files_processed": 0,
        "files_error": 0,
        "hourly_rows_before_dedup": 0,
        "hourly_rows_after_dedup": 0,
        "stores_found": 0,
    }
    stats["stores_found"] = len({filepath.parent.name for filepath in files})
    frames = []
    for filepath in files:
        result = process_single_promotion_xlsx(filepath)
        if result is None or result.empty:
            stats["files_error"] += 1
            continue
        frames.append(result)
        stats["files_processed"] += 1

    if not frames:
        return pd.DataFrame(columns=["商品ID", "日期"] + PROMOTION_STRING_COLUMNS + PROMOTION_NUMERIC_COLUMNS), stats

    promotion = pd.concat(frames, ignore_index=True)
    stats["hourly_rows_before_dedup"] = len(promotion)
    promotion = promotion.drop_duplicates(["store", "日期", "商品ID", "推广小时"], keep="last").reset_index(drop=True)
    stats["hourly_rows_after_dedup"] = len(promotion)
    # 保留旧统计键，兼容现有日志或管理端读取方。
    stats["rows_before_dedup"] = stats["hourly_rows_before_dedup"]
    stats["rows_after_dedup"] = stats["hourly_rows_after_dedup"]
    return promotion, stats


def aggregate_promotion_daily(promotion_df):
    """将分小时推广明细汇总为现有利润主表可关联的日粒度。"""
    if promotion_df is None or promotion_df.empty:
        return promotion_df

    group_keys = ["store", "日期", "商品ID"]
    grouped = promotion_df.copy()
    # 只汇总原始数值字段，投产比、单笔成本等比例/均值字段在日汇总后重新计算。
    numeric_columns = [column for column in PROMOTION_RAW_NUMERIC_COLUMNS if column in grouped.columns]
    string_columns = [column for column in PROMOTION_STRING_COLUMNS if column in grouped.columns and column not in group_keys]

    aggregations = {column: "sum" for column in numeric_columns}
    aggregations.update({column: "first" for column in string_columns})
    daily = grouped.groupby(group_keys, as_index=False, dropna=False).agg(aggregations)
    daily["推广小时"] = "全天汇总"
    return calculate_promotion_metrics(daily)


def merge_promotion_data(main_df, promotion_df):
    """以主表为左表，将推广明细按链接 ID + 日期补齐。"""
    main = main_df.copy()

    if promotion_df is None or promotion_df.empty:
        for col in PROMOTION_DATA_COLUMNS:
            if col not in main.columns:
                main[col] = 0 if col == "推广数据匹配" else np.nan
        return main, {"matched_rows": 0, "promotion_rows": 0}

    promotion = aggregate_promotion_daily(promotion_df)
    promotion = promotion.copy()
    promotion["__link_id"] = normalize_join_id(promotion["商品ID"])
    promotion["__date"] = pd.to_datetime(promotion["日期"], errors="coerce").dt.strftime("%Y-%m-%d")
    promotion["__store"] = promotion["store"].astype("string").str.strip()
    promotion = promotion[
        promotion["__link_id"].notna()
        & promotion["__date"].notna()
        & promotion["__store"].notna()
        & promotion["__store"].ne("")
    ].copy()
    promotion = promotion.drop_duplicates(["__link_id", "__date", "__store"], keep="last")

    main["__link_id"] = normalize_join_id(main["链接id"])
    main["__date"] = pd.to_datetime(main["数据日期"], errors="coerce").dt.strftime("%Y-%m-%d")
    main["__store"] = main["店铺名称"].astype("string").str.strip() if "店铺名称" in main.columns else ""

    fields = [c for c in PROMOTION_STRING_COLUMNS + PROMOTION_NUMERIC_COLUMNS if c in promotion.columns]
    lookup = promotion[["__link_id", "__date"] + fields].copy()
    lookup["__store"] = promotion["__store"]
    merged = main.merge(lookup, how="left", on=["__link_id", "__date", "__store"], validate="m:1", suffixes=("", "_推广"))
    matched = merged["推广来源文件"].notna() if "推广来源文件" in merged.columns else pd.Series(False, index=merged.index)
    merged["推广数据匹配"] = matched.astype(int)
    merged = merged.drop(columns=["__link_id", "__date", "__store"])
    return merged, {"matched_rows": int(matched.sum()), "promotion_rows": len(promotion)}


def normalize_join_id_value(value):
    """统一单个数据库键值，用于生成主表业务键集合。"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    text = re.sub(r"\.0$", "", text)
    return text or None


def ensure_promotion_columns(conn):
    """为现有主表补充推广字段；已存在字段不会被改写。"""
    cur = conn.cursor()
    cur.execute(f"SHOW COLUMNS FROM {TABLE_NAME}")
    existing = {row[0] for row in cur.fetchall()}
    added = []
    for col in PROMOTION_STRING_COLUMNS:
        if col in existing:
            continue
        sql_type = "VARCHAR(200)" if col == "出价方式" else "TEXT"
        cur.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN `{col}` {sql_type} NULL")
        added.append(col)
    for col in PROMOTION_NUMERIC_COLUMNS:
        if col in existing:
            continue
        cur.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN `{col}` DOUBLE NULL")
        added.append(col)
    if "推广数据匹配" not in existing:
        cur.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN `推广数据匹配` TINYINT NOT NULL DEFAULT 0")
        added.append("推广数据匹配")
    conn.commit()
    return added


def ensure_promotion_hourly_table(conn):
    """Create the independent promotion fact table at date + hour grain."""
    key_columns = {"product_id", "store_name", "promotion_hour"}
    string_columns = ["product_id", "store_name", "promotion_hour", "source_file", "bid_type", "product_name", "promotion_scene", "promotion_name", "group_name", "is_deleted"]
    numeric_columns = [column for column in PROMOTION_HOURLY_COLUMN_MAP.values() if column not in string_columns and column not in {"data_date"}]
    definitions = ["id BIGINT AUTO_INCREMENT PRIMARY KEY", "data_date DATE NOT NULL"]
    for column in string_columns:
        nullability = "NOT NULL" if column in key_columns else "NULL"
        length = 500 if column == "product_name" else 255
        definitions.append(f"`{column}` VARCHAR({length}) {nullability}")
    for column in numeric_columns:
        definitions.append(f"`{column}` DOUBLE NULL")
    definitions.extend([
        "UNIQUE KEY uk_promotion_hourly (store_name(100), product_id(64), data_date, promotion_hour(32))",
        "KEY idx_promotion_date (data_date)",
        "KEY idx_promotion_product (product_id(64))",
        "KEY idx_promotion_store_date (store_name(100), data_date)",
    ])
    cur = conn.cursor()
    cur.execute(f"CREATE TABLE IF NOT EXISTS {PROMOTION_HOURLY_TABLE} (" + ", ".join(definitions) + ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4")
    conn.commit()


def replace_promotion_hourly_table(conn, promotion):
    """Replace the independent hourly fact table with the latest source snapshot."""
    ensure_promotion_hourly_table(conn)
    cur = conn.cursor()
    cur.execute(f"TRUNCATE TABLE {PROMOTION_HOURLY_TABLE}")
    db_columns = list(dict.fromkeys(PROMOTION_HOURLY_COLUMN_MAP.values()))
    insert_columns = [column for column in db_columns if column in {"data_date", *[PROMOTION_HOURLY_COLUMN_MAP.get(c) for c in promotion.columns]}]
    insert_sql = f"INSERT INTO {PROMOTION_HOURLY_TABLE} (" + ", ".join(f"`{column}`" for column in insert_columns) + ") VALUES (" + ", ".join(["%s"] * len(insert_columns)) + ") ON DUPLICATE KEY UPDATE " + ", ".join(f"`{column}` = VALUES(`{column}`)" for column in insert_columns if column not in {"data_date", "store_name", "product_id", "promotion_hour"})
    rows = []
    for _, item in promotion.iterrows():
        values = []
        for db_column in insert_columns:
            source_column = next((source for source, target in PROMOTION_HOURLY_COLUMN_MAP.items() if target == db_column), None)
            value = item.get(source_column) if source_column else None
            if value is None or (isinstance(value, float) and (pd.isna(value) or np.isinf(value))):
                value = None
            elif isinstance(value, np.generic):
                value = value.item()
            values.append(value)
        rows.append(tuple(values))
    for offset in range(0, len(rows), 1000):
        cur.executemany(insert_sql, rows[offset:offset + 1000])
        conn.commit()
    return len(rows)


def run_promotion_backfill():
    """只回填推广字段，不新增主表行，也不覆盖主表已有字段。"""
    promotion, promotion_stats = load_promotion_data()
    if promotion.empty:
        return {
            "status": "error",
            "message": "推广目录没有读取到有效商品明细",
            "promotion": promotion_stats,
        }

    conn = get_mysql()
    try:
        hourly_rows = replace_promotion_hourly_table(conn, promotion)
        added_columns = ensure_promotion_columns(conn)
        cur = conn.cursor()
        # 回填现有日粒度主表前，先把小时明细汇总到店铺 + 商品 + 日期。
        promotion = aggregate_promotion_daily(promotion)
        cur.execute(f"SELECT `链接id`, `店铺名称`, `数据日期` FROM {TABLE_NAME}")
        main_keys = {
            (normalize_join_id_value(link_id), str(store_name or "").strip(), str(data_date))
            for link_id, store_name, data_date in cur.fetchall()
            if normalize_join_id_value(link_id) and data_date is not None
        }

        promotion = promotion.copy()
        promotion["__link_id"] = normalize_join_id(promotion["商品ID"])
        promotion["__date"] = pd.to_datetime(promotion["日期"], errors="coerce").dt.strftime("%Y-%m-%d")
        promotion["__store"] = promotion["store"].astype("string").str.strip()
        promotion["__key"] = list(zip(promotion["__link_id"], promotion["__store"], promotion["__date"]))
        matched = promotion[promotion["__key"].isin(main_keys)].copy()

        update_fields = PROMOTION_STRING_COLUMNS + PROMOTION_NUMERIC_COLUMNS
        set_clause = ", ".join([f"`{col}` = %s" for col in update_fields] + ["`推广数据匹配` = 1"])
        update_sql = (
            f"UPDATE {TABLE_NAME} SET {set_clause} "
            "WHERE `链接id` = %s AND `店铺名称` = %s AND `数据日期` = %s"
        )

        def db_value(value):
            if value is None or (isinstance(value, float) and (pd.isna(value) or np.isinf(value))):
                return None
            return value.item() if isinstance(value, np.generic) else value

        update_rows = []
        for _, row in matched.iterrows():
            values = [db_value(row[col]) for col in update_fields]
            values.extend([row["__link_id"], row["__store"], row["__date"]])
            update_rows.append(tuple(values))

        updated = 0
        for i in range(0, len(update_rows), 500):
            batch = update_rows[i:i + 500]
            cur.executemany(update_sql, batch)
            conn.commit()
            updated += len(batch)

        return {
            "status": "ok",
            "message": "推广字段回填完成",
            "promotion": {
                **promotion_stats,
                "main_keys": len(main_keys),
                "matched_keys": len(matched),
                "updated_rows": updated,
                "hourly_table": PROMOTION_HOURLY_TABLE,
                "hourly_rows": hourly_rows,
                "added_columns": added_columns,
            },
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def run_etl():
    """完整 ETL 流程：扫描→清洗→入库"""
    print(f"\n{'='*60}")
    print(f"🔄 ETL 开始 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
    print(f"{'='*60}")

    xlsx_files = list_xlsx_files()
    print(f"📁 找到 {len(xlsx_files)} 个 xlsx 文件")

    if not xlsx_files:
        print("❌ 未找到任何文件")
        return {"status": "error", "message": "未找到文件", "files": 0}

    cache_dir = LOCAL_CACHE / "etl"
    all_data = []
    processed = 0
    errors = 0

    for month, filepath in xlsx_files:
        df = process_single_xlsx(month, filepath, cache_dir)
        if df is not None and len(df) > 0:
            all_data.append(df)
            processed += 1
            if processed % 20 == 0:
                print(f"  已处理 {processed}/{len(xlsx_files)} ...")
        else:
            errors += 1

    if not all_data:
        print("❌ 没有有效数据")
        return {"status": "error", "message": "没有有效数据", "files": processed, "errors": errors}

    merged = pd.concat(all_data, ignore_index=True)
    
    # 过滤：删除负责人=淘宝的行（李世豪）
    if "负责人" in merged.columns:
        before = len(merged)
        merged = merged[~merged["负责人"].str.contains("淘宝", na=False)]
        print(f"🗑 已过滤负责人=淘宝: {before - len(merged)} 行")

    # 读取推广目录，并以主表为左表补充商品推广明细。
    promotion, promotion_stats = load_promotion_data()
    if not promotion_stats["files_found"] or not promotion_stats["files_processed"]:
        print("❌ 推广目录没有有效数据，停止本次主表重建，避免覆盖已有完整数据")
        return {
            "status": "error",
            "message": "推广目录没有有效数据，未执行主表重建",
            "files_processed": processed,
            "files_error": errors,
            "promotion": promotion_stats,
        }
    merged, merge_stats = merge_promotion_data(merged, promotion)
    link_info, link_info_stats = load_link_info_data()
    if not link_info_stats["files_found"] or not link_info_stats["files_processed"]:
        print("❌ 链接信息目录没有有效数据，停止本次主表重建")
        return {
            "status": "error",
            "message": "链接信息目录没有有效数据，未执行主表重建",
            "files_processed": processed,
            "files_error": errors,
            "promotion": promotion_stats,
            "link_info": link_info_stats,
        }
    print(
        "📣 推广数据: "
        f"{promotion_stats['files_processed']}/{promotion_stats['files_found']} 个文件, "
        f"去重后 {promotion_stats['rows_after_dedup']} 行, "
        f"匹配主表 {merge_stats['matched_rows']} 行"
    )
    print(
        "🔗 链接信息: "
        f"{link_info_stats['files_processed']}/{link_info_stats['files_found']} 个文件, "
        f"按最新文件优先去重 {link_info_stats['rows_before_dedup']} → {link_info_stats['rows_after_dedup']} 行"
    )
    
    print(f"✅ 清洗完成: {processed} 文件, {len(merged)} 行, {errors} 错误")

    # 入库 MySQL（全量替换）
    conn = get_mysql()
    cur = conn.cursor()
    hourly_rows = replace_promotion_hourly_table(conn, promotion)

    # 删旧表重建
    cur.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
    
    # 动态生成建表语句（基于实际数据列）
    col_defs = ["id INT AUTO_INCREMENT PRIMARY KEY"]
    for c in merged.columns:
        col_name = f"`{c}`"
        if c in ("数据日期",):
            col_defs.append(f"{col_name} DATE")
        elif c in ("商品标题", "商品名称", "来源文件", "store", "推广来源文件") or c in PROMOTION_STRING_COLUMNS:
            col_defs.append(f"{col_name} TEXT")
        elif c in ("链接id", "商品编码", "店铺名称", "负责人", "出价方式"):
            col_defs.append(f"{col_name} VARCHAR(200)")
        else:
            col_defs.append(f"{col_name} DOUBLE")
    
    # 添加索引
    if "链接id" in merged.columns:
        col_defs.append("INDEX idx_link (`链接id`(32))")
    if "数据日期" in merged.columns:
        col_defs.append("INDEX idx_date (`数据日期`)")
    if "链接id" in merged.columns and "数据日期" in merged.columns:
        col_defs.append("INDEX idx_link_date (`链接id`(32), `数据日期`)")
    if "商品编码" in merged.columns:
        col_defs.append("INDEX idx_code (`商品编码`(32))")
    
    create_sql = f"CREATE TABLE {TABLE_NAME} (\n        " + ",\n        ".join(col_defs) + "\n    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
    cur.execute(create_sql)
    conn.commit()

    # 分批 INSERT（每批1000行，避免 SQL 过大）
    # 替换 NaN 和 Inf 为 None
    merged = merged.replace([np.inf, -np.inf], np.nan)
    merged = merged.where(pd.notna(merged), None)
    cols = [f"`{c}`" for c in merged.columns]
    col_names = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(cols))
    insert_sql = f"INSERT INTO {TABLE_NAME} ({col_names}) VALUES ({placeholders})"

    batch_size = 100
    total_inserted = 0
    for i in range(0, len(merged), batch_size):
        batch = merged.iloc[i:i+batch_size]
        rows = [tuple(None if pd.isna(v) else v for v in row) for row in batch.values]
        cur.executemany(insert_sql, rows)
        conn.commit()
        total_inserted += len(rows)
        if total_inserted % 20000 == 0:
            print(f"  已入库 {total_inserted}/{len(merged)} ...")
    conn.close()

    link_info_rows = 0
    if not link_info.empty:
        conn = get_mysql()
        try:
            link_info_rows = replace_link_info_table(conn, link_info)
        finally:
            conn.close()

    print(f"✅ 入库完成: {total_inserted} 行 → {TABLE_NAME}")

    return {
        "status": "ok",
        "files_processed": processed,
        "files_error": errors,
        "rows_inserted": total_inserted,
        "promotion": {
            **promotion_stats,
            **merge_stats,
            "hourly_table": PROMOTION_HOURLY_TABLE,
            "hourly_rows": hourly_rows,
        },
        "link_info": {**link_info_stats, "table": LINK_INFO_TABLE, "rows": link_info_rows},
        "dates": sorted(merged["数据日期"].unique().tolist()),
        "timestamp": datetime.now().isoformat()
    }

# ============ FastAPI 端点 ============
@app.get("/api/v3/data")
def get_data(
    link_ids: str = Query(default=""),
    product_code: str = Query(default=""),
    product_name: str = Query(default=""),
    brand: str = Query(default=""),
    store_name: str = Query(default=""),
    store_person: str = Query(default=""),
    creation_days: int = Query(default=None, ge=1, le=3650),
    creation_start: str = Query(default=""),
    creation_end: str = Query(default=""),
):
    """从 MySQL 读取数据并聚合，返回看板所需 JSON。

    筛选条件在数据库层执行，保证所有 Vue 看板使用同一份过滤后的数据。
    link_ids 支持逗号分隔的多个链接 ID。
    """
    where = []
    params = []
    if link_ids:
        ids = [item.strip() for item in link_ids.split(",") if item.strip()]
        if ids:
            placeholders = ",".join(["%s"] * len(ids))
            where.append(f"`链接id` IN ({placeholders})")
            params.extend(ids)
    if product_code:
        where.append("`商品编码` LIKE %s")
        params.append(f"%{product_code.strip()}%")
    if product_name:
        where.append("`商品标题` LIKE %s")
        params.append(f"%{product_name.strip()}%")
    _append_brand_filter(where, params, brand)
    if store_name:
        where.append("`店铺名称` LIKE %s")
        params.append(f"%{store_name.strip()}%")
    if store_person:
        where.append("`负责人` = %s")
        params.append(store_person.strip())
    conn = get_mysql()
    _append_creation_filter(where, params, creation_days, creation_start, creation_end, f"{TABLE_NAME}.`链接id`", conn)

    where_sql = f" WHERE {' AND '.join(where)}" if where else ""
    try:
        # 原始明细
        df = pd.read_sql(f"SELECT * FROM {TABLE_NAME}{where_sql}", conn, params=params)
    finally:
        conn.close()

    if df.empty:
        if where:
            return {"success": False, "error": "当前筛选条件下无数据，请尝试放宽筛选条件"}
        return {"success": False, "error": "数据库暂无数据，请先运行 ETL"}

    return {
        "success": True,
        "data": aggregate_dashboard_data(df),
        "meta": {
            "total_rows": len(df),
            "date_range": [str(df["数据日期"].min()), str(df["数据日期"].max())],
            "generated_at": datetime.now().isoformat()
        }
    }

@app.get("/api/v3/promotion-summary")
def get_promotion_summary(
    start: str = Query(default=""),
    end: str = Query(default=""),
    search: str = Query(default=""),
    product_id: str = Query(default=""),
    product_name: str = Query(default=""),
    brand: str = Query(default=""),
    store_name: str = Query(default=""),
    size: int = Query(default=5000, ge=1, le=20000),
):
    """Aggregate only real promotion facts from the MySQL hourly table."""
    where = ["1=1", "(is_deleted IS NULL OR LOWER(CAST(is_deleted AS CHAR)) NOT IN ('1', 'true', 'yes', '是'))"]
    params = []
    id_values = [normalize_join_id_value(value) for value in str(product_id or "").replace("，", ",").split(",") if value.strip()]
    id_values = [value for value in id_values if value]
    if id_values:
        where.append("product_id IN (" + ",".join(["%s"] * len(id_values)) + ")")
        params.extend(id_values)
    if search:
        search_value = f"%{search.strip()}%"
        where.append("(product_id LIKE %s OR product_name LIKE %s)")
        params.extend([search_value, search_value])
    if product_name:
        where.append("product_name LIKE %s")
        params.append(f"%{product_name.strip()}%")
    if store_name:
        where.append("store_name LIKE %s")
        params.append(f"%{store_name.strip()}%")
    if start:
        where.append("data_date >= %s")
        params.append(start)
    if end:
        where.append("data_date <= %s")
        params.append(end)
    brand_patterns = {
        "浪奇": ["%浪奇%", "%LANGQI%"],
        "威王": ["%威王%", "%VEWIN%"],
        "舒蕾": ["%舒蕾%", "%SLEK%"],
    }
    if brand in brand_patterns:
        patterns = brand_patterns[brand]
        where.append("(" + " OR ".join(["store_name LIKE %s"] * len(patterns)) + ")")
        params.extend(patterns)
    elif brand == "白牌":
        excluded = [pattern for patterns in brand_patterns.values() for pattern in patterns]
        where.append(" AND ".join(["store_name NOT LIKE %s"] * len(excluded)))
        params.extend(excluded)

    select_sql = f"""
        SELECT product_id, MAX(product_name) AS product_name, MAX(store_name) AS store_name,
               MAX(bid_type) AS bid_type, MAX(promotion_scene) AS promotion_scene,
               MAX(promotion_name) AS promotion_name, MAX(is_deleted) AS is_deleted,
               SUM(spend) AS spend, SUM(total_spend) AS total_spend,
               SUM(revenue) AS revenue, SUM(net_revenue) AS net_revenue,
               SUM(orders) AS orders, SUM(net_orders) AS net_orders,
               SUM(direct_revenue) AS direct_revenue, SUM(indirect_revenue) AS indirect_revenue,
               SUM(impressions) AS impressions, SUM(clicks) AS clicks,
               SUM(favorites) AS favorites, SUM(follows) AS follows, SUM(inquiries) AS inquiries,
               MIN(data_date) AS first_date, MAX(data_date) AS last_date,
               COUNT(DISTINCT data_date) AS data_days
        FROM {PROMOTION_HOURLY_TABLE}
        WHERE {' AND '.join(where)}
        GROUP BY store_name, product_id
        ORDER BY SUM(spend) DESC, product_id
        LIMIT %s
    """
    params.append(size)
    conn = get_mysql()
    try:
        cur = conn.cursor()
        cur.execute(select_sql, params)
        source_rows = cur.fetchall()
        columns = [column[0] for column in cur.description]
    except pymysql.err.ProgrammingError as exc:
        if "doesn't exist" in str(exc):
            return {"success": False, "error": f"推广数据表 {PROMOTION_HOURLY_TABLE} 尚未初始化，请先运行推广 ETL"}
        raise
    finally:
        conn.close()

    def number(item, field):
        try:
            return float(item.get(field) or 0)
        except (TypeError, ValueError):
            return 0.0

    def store_brand(store):
        text = str(store or "")
        upper = text.upper()
        if "浪奇" in text or "LANGQI" in upper:
            return "浪奇"
        if "威王" in text or "VEWIN" in upper:
            return "威王"
        if "舒蕾" in text or "SLEK" in upper:
            return "舒蕾"
        return "白牌"

    rows = []
    for source_row in source_rows:
        item = dict(zip(columns, source_row))
        spend = number(item, "spend")
        revenue = number(item, "revenue")
        net_revenue = number(item, "net_revenue")
        store = str(item.get("store_name") or "")
        rows.append({
            "linkId": str(item.get("product_id") or ""),
            "productCode": "",
            "title": str(item.get("product_name") or ""),
            "storeName": store,
            "brand": store_brand(store),
            "person": "",
            "status": "已删除" if str(item.get("is_deleted") or "").lower() in {"1", "true", "yes", "是"} else "推广中",
            "bidType": str(item.get("bid_type") or "—"),
            "stage": str(item.get("promotion_scene") or "—"),
            "targetRoi": None,
            "firstDate": str(item.get("first_date") or ""),
            "lastDate": str(item.get("last_date") or ""),
            "dataDays": int(item.get("data_days") or 0),
            "spend": spend,
            "totalSpend": number(item, "total_spend"),
            "revenue": revenue,
            "roi": revenue / spend if spend else 0,
            "netRevenue": net_revenue,
            "netRoi": net_revenue / spend if spend else 0,
            "directRevenue": number(item, "direct_revenue"),
            "indirectRevenue": number(item, "indirect_revenue"),
            "orders": number(item, "net_orders"),
            "impressions": number(item, "impressions"),
            "clicks": number(item, "clicks"),
            "favorites": number(item, "favorites"),
            "follows": number(item, "follows"),
            "inquiries": number(item, "inquiries"),
        })
    return {
        "success": True,
        "data": rows,
        "total": len(rows),
        "meta": {
            "rows": len(rows),
            "date_range": [start or None, end or None],
            "source_table": PROMOTION_HOURLY_TABLE,
            "source_grain": "store + product_id + data_date + promotion_hour",
        },
    }

@app.get("/api/v3/promotion-hourly")
def get_promotion_hourly(
    link_id: str = Query(default=""),
    product_id: str = Query(default=""),
    product_name: str = Query(default=""),
    store_name: str = Query(default=""),
    start: str = Query(default=""),
    end: str = Query(default=""),
    hour: str = Query(default=""),
    size: int = Query(default=5000, ge=1, le=20000),
):
    """Read the independent MySQL promotion fact table at date + hour grain."""
    where = ["1=1"]
    params = []
    id_values = [normalize_join_id_value(value) for value in (link_id, product_id) if value]
    id_values = [value for value in id_values if value]
    identity = []
    if id_values:
        identity.append("product_id IN (" + ",".join(["%s"] * len(id_values)) + ")")
        params.extend(id_values)
    if product_name:
        identity.append("product_name LIKE %s")
        params.append(f"%{product_name.strip()}%")
    if identity:
        where.append("(" + " OR ".join(identity) + ")")
    if store_name:
        where.append("store_name LIKE %s")
        params.append(f"%{store_name.strip()}%")
    if start:
        where.append("data_date >= %s")
        params.append(start)
    if end:
        where.append("data_date <= %s")
        params.append(end)
    if hour:
        where.append("promotion_hour LIKE %s")
        params.append(f"{hour}%")

    select_sql = f"""
        SELECT data_date, promotion_hour, product_id, product_name, store_name,
               spend, total_spend, revenue, net_revenue, roi, net_roi,
               impressions, clicks, orders, net_orders, direct_revenue,
               indirect_revenue, source_file
        FROM {PROMOTION_HOURLY_TABLE}
        WHERE {' AND '.join(where)}
        ORDER BY data_date, promotion_hour, product_id
        LIMIT %s
    """
    params.append(size)
    conn = get_mysql()
    try:
        cur = conn.cursor()
        cur.execute(select_sql, params)
        source_rows = cur.fetchall()
        columns = [column[0] for column in cur.description]
    except pymysql.err.ProgrammingError as exc:
        if "doesn't exist" in str(exc):
            return {"success": False, "error": f"推广小时数据表 {PROMOTION_HOURLY_TABLE} 尚未初始化，请先运行推广 ETL"}
        raise
    finally:
        conn.close()

    rows = []
    for source_row in source_rows:
        item = dict(zip(columns, source_row))
        raw_hour = str(item.get("promotion_hour") or "")
        match = re.match(r"\s*(\d{1,2})", raw_hour)
        hour_label = f"{int(match.group(1)):02d}:00" if match else raw_hour
        def number(field):
            value = item.get(field)
            try:
                return float(value or 0)
            except (TypeError, ValueError):
                return 0.0
        rows.append({
            "date": str(item.get("data_date")),
            "hour": hour_label,
            "hourRange": raw_hour,
            "productId": str(item.get("product_id") or ""),
            "productName": str(item.get("product_name") or ""),
            "store": str(item.get("store_name") or ""),
            "spend": number("spend"),
            "totalSpend": number("total_spend"),
            "revenue": number("revenue"),
            "netRevenue": number("net_revenue"),
            "roi": number("roi"),
            "netRoi": number("net_roi"),
            "impressions": number("impressions"),
            "clicks": number("clicks"),
            "orders": number("orders"),
            "netOrders": number("net_orders"),
            "directRevenue": number("direct_revenue"),
            "indirectRevenue": number("indirect_revenue"),
            "sourceFile": str(item.get("source_file") or ""),
        })
    date_range = [rows[0]["date"], rows[-1]["date"]] if rows else [start or None, end or None]
    return {"success": True, "data": rows, "meta": {"rows": len(rows), "date_range": date_range, "source_table": PROMOTION_HOURLY_TABLE}}

@app.get("/api/v3/data/range")
def get_data_range(start: str = Query(...), end: str = Query(...)):
    """按日期范围获取数据"""
    conn = get_mysql()
    try:
        df = pd.read_sql(
            f"SELECT * FROM {TABLE_NAME} WHERE 数据日期 >= %s AND 数据日期 <= %s",
            conn, params=(start, end)
        )
    finally:
        conn.close()

    if df.empty:
        return {"success": False, "error": f"日期范围 {start}~{end} 无数据"}

    return {
        "success": True,
        "data": aggregate_dashboard_data(df),
        "meta": {"rows": len(df)}
    }

@app.post("/api/v3/etl/run")
def trigger_etl(background_tasks: BackgroundTasks):
    """手动触发 ETL"""
    # 同步执行（数据量大时可能需要30-60秒）
    result = run_etl()
    return result


@app.post("/api/v3/etl/promotion")
def trigger_promotion_backfill():
    """只从推广目录补齐现有主表，不重建主表。"""
    return run_promotion_backfill()

@app.post("/api/v3/refresh")
def refresh_data():
    """刷新数据：重新从 MySQL 读取（数据由定时 ETL 或手动 /api/v3/etl/run 更新）"""
    return {"success": True, "message": "数据已就绪，请重新加载 /api/v3/data", "timestamp": datetime.now().isoformat()}

# ============ 统一操作任务队列（下架 + 调整投产）============
OPERATION_FILE = Path(os.getenv("PROFIT_OPERATION_FILE", str(Path(__file__).with_name("operation_tasks.json"))))
LEGACY_DELIST_FILE = Path(os.getenv("PROFIT_DELIST_FILE", str(Path(__file__).with_name("delist_tasks.json"))))
LEGACY_ADJUST_FILE = Path(os.getenv("PROFIT_ADJUST_FILE", str(Path(__file__).with_name("promotion_adjust_tasks.json"))))
_operation_lock = threading.Lock()

OPERATION_NAMES = {
    "delist": "产品下架",
    "promotion_adjust": "调整投产",
}
PROMOTION_ADJUST_PRESETS = {
    "maintenance-005": {"label": "日常维护", "display": "+0.05", "value": 0.05},
    "serious-loss-01": {"label": "亏损严重", "display": "+0.1", "value": 0.1},
    "serious-loss-02": {"label": "亏损严重", "display": "+0.2", "value": 0.2},
    "maintenance-001": {"label": "日常维护", "display": "+0.01", "value": 0.01},
}


def _format_adjustment_display(direction, value):
    sign = "+" if direction == "up" else "-"
    number = f"{float(value):.2f}".rstrip("0").rstrip(".")
    return f"{sign}{number}"


def _resolve_promotion_adjustment(data):
    """解析并规范化投产调整档次，同时兼容旧版 direction/value 请求。"""
    direction = str(data.get("direction", "")).strip().lower()
    if direction not in {"up", "down"}:
        return None, "调整方向必须是 up 或 down"

    raw_value = data.get("value", data.get("adjustment_value"))
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        value = math.nan
    if not math.isfinite(value) or value <= 0:
        value = None

    preset_key = str(
        data.get("adjustment_preset_key")
        or data.get("preset_key")
        or data.get("adjustment_preset")
        or ""
    ).strip().lower()
    preset = PROMOTION_ADJUST_PRESETS.get(preset_key) if preset_key else None
    if preset_key and preset is None:
        return None, "未知的投产调整档次"
    if preset is not None:
        if value is not None and not math.isclose(value, preset["value"], rel_tol=0, abs_tol=1e-9):
            return None, "投产调整档次与调整数值不一致"
        value = preset["value"]
    if value is None:
        return None, "调整数值必须是大于 0 的数字"

    if preset is None and direction == "up":
        for candidate_key, candidate in PROMOTION_ADJUST_PRESETS.items():
            if math.isclose(value, candidate["value"], rel_tol=0, abs_tol=1e-9):
                preset_key = candidate_key
                preset = candidate
                break

    label = preset["label"] if preset else "自定义调整"
    display = preset["display"] if preset and direction == "up" else _format_adjustment_display(direction, value)
    return {
        "adjustment_preset_key": preset_key or None,
        "adjustment_label": label,
        "adjustment_display": display,
        "direction": direction,
        "value": value,
    }, None


def _read_task_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) and isinstance(data.get("tasks"), list) else {"tasks": []}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"tasks": []}


def _normalise_task(task, task_type):
    item = dict(task)
    item.setdefault(
        "dingtalk_userid",
        item.get("dingtalk_user_id") or item.get("ding_userid") or item.get("userId") or item.get("userid"),
    )
    item.setdefault(
        "dingtalk_username",
        item.get("dingtalk_user_name") or item.get("ding_username") or item.get("username") or item.get("name"),
    )
    if not item.get("operator") and item.get("dingtalk_username"):
        item["operator"] = item["dingtalk_username"]
    item.setdefault("task_type", task_type)
    item.setdefault("operation", item["task_type"])
    item.setdefault("operation_type", item["task_type"])
    item.setdefault("operation_name", OPERATION_NAMES.get(item["task_type"], item["task_type"]))
    if item["task_type"] == "delist":
        item.setdefault("operation_label", "产品下架")
    elif item["task_type"] == "promotion_adjust":
        adjustment, _ = _resolve_promotion_adjustment(item)
        if adjustment:
            for key, value in adjustment.items():
                item.setdefault(key, value)
            item.setdefault("operation_label", f"{adjustment['adjustment_label']} {adjustment['adjustment_display']}")
        else:
            item.setdefault("operation_label", "调整投产")
    item.setdefault("status", "pending")
    item.setdefault("completed_at", None)
    item.setdefault("result", None)
    item.setdefault("error", None)
    return item


def _read_operation_tasks():
    """读取统一队列，并将旧的两个队列中的历史/待处理任务合并进来。"""
    merged = []
    seen_ids = set()
    sources = (
        (OPERATION_FILE, None),
        (LEGACY_DELIST_FILE, "delist"),
        (LEGACY_ADJUST_FILE, "promotion_adjust"),
    )
    for path, default_type in sources:
        for task in _read_task_file(path).get("tasks", []):
            if not isinstance(task, dict):
                continue
            task_id = str(task.get("id", "")).strip()
            if task_id and task_id in seen_ids:
                continue
            task_type = task.get("task_type") or task.get("operation_type") or task.get("operation") or default_type or "delist"
            task = _normalise_task(task, task_type)
            if task_id:
                seen_ids.add(task_id)
            merged.append(task)
    return {"tasks": merged}


def _write_operation_tasks(data):
    OPERATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OPERATION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _pending_tasks(task_type=None):
    tasks = _read_operation_tasks().get("tasks", [])
    return [
        task for task in tasks
        if task.get("status") == "pending" and (task_type is None or task.get("task_type") == task_type)
    ]


def _history_tasks(task_type=None):
    tasks = _read_operation_tasks().get("tasks", [])
    if task_type is not None:
        tasks = [task for task in tasks if task.get("task_type") == task_type]
    return list(reversed(tasks[-50:]))


def _complete_operation_task(data):
    task_id = str(data.get("task_id", "")).strip()
    if not task_id:
        return JSONResponse({"error": "请提供task_id"}, status_code=400)

    result = str(data.get("result", "")).strip().lower()
    task_status = "completed" if result == "ok" else "failed"
    with _operation_lock:
        tasks = _read_operation_tasks()
        for task in tasks.get("tasks", []):
            if task.get("id") == task_id and task.get("status") == "pending":
                task["status"] = task_status
                task["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                task["result"] = data.get("result", "")
                task["error"] = data.get("error", "")
                _write_operation_tasks(tasks)
                return {"success": True, "task": task}
    return JSONResponse({"error": "任务不存在或已处理"}, status_code=404)


def _create_operation_task(task_type, data):
    raw_link_ids = data.get("link_ids", [])
    link_ids = [str(link_id).strip() for link_id in raw_link_ids if str(link_id).strip()]
    if not link_ids:
        return None, JSONResponse({"error": "请至少选择一个链接"}, status_code=400)

    raw_store_names = data.get("store_names", [])
    store_names = raw_store_names if isinstance(raw_store_names, list) else []
    store_names = [str(store_name).strip() for store_name in store_names[:len(link_ids)]]
    store_names.extend([""] * (len(link_ids) - len(store_names)))

    task = {
        "id": uuid.uuid4().hex[:12],
        "task_type": task_type,
        "operation": task_type,
        "operation_type": task_type,
        "operation_name": OPERATION_NAMES[task_type],
        "operation_label": OPERATION_NAMES[task_type],
        "link_ids": link_ids,
        "count": len(link_ids),
        "store_names": store_names,
        "store_count": len([name for name in store_names if name]),
        "operator": str(data.get("operator") or data.get("dingtalk_username") or "").strip(),
        "dingtalk_userid": str(
            data.get("dingtalk_userid")
            or data.get("dingtalk_user_id")
            or data.get("ding_userid")
            or data.get("userId")
            or data.get("userid")
            or ""
        ).strip() or None,
        "dingtalk_username": str(
            data.get("dingtalk_username")
            or data.get("dingtalk_user_name")
            or data.get("ding_username")
            or data.get("username")
            or data.get("name")
            or ""
        ).strip() or None,
        "status": "pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "completed_at": None,
        "result": None,
        "error": None,
    }

    if task_type == "promotion_adjust":
        adjustment, adjustment_error = _resolve_promotion_adjustment(data)
        if adjustment_error:
            return None, JSONResponse({"error": adjustment_error}, status_code=400)
        task.update(adjustment)
        task["operation_label"] = f"{adjustment['adjustment_label']} {adjustment['adjustment_display']}"

    with _operation_lock:
        tasks = _read_operation_tasks()
        tasks.setdefault("tasks", []).append(task)
        _write_operation_tasks(tasks)
    return task, None


@app.post("/api/operation")
async def operation_submit(request: Request):
    """统一提交入口；task_type 为 delist 或 promotion_adjust。"""
    data = await request.json()
    task_type = str(data.get("task_type", data.get("operation_type", data.get("operation", "")))).strip().lower()
    if task_type not in {"delist", "promotion_adjust"}:
        return JSONResponse({"error": "task_type 必须是 delist 或 promotion_adjust"}, status_code=400)
    task, error = _create_operation_task(task_type, data)
    if error:
        return error
    return {"success": True, "task": task}


@app.get("/api/operation/pending")
async def operation_pending():
    with _operation_lock:
        tasks = _pending_tasks()
    return {"tasks": tasks, "count": len(tasks)}


@app.post("/api/operation/complete")
async def operation_complete(request: Request):
    return _complete_operation_task(await request.json())


@app.get("/api/operation/history")
async def operation_history():
    with _operation_lock:
        tasks = _history_tasks()
    return {"tasks": tasks, "count": len(tasks)}


@app.post("/api/delist")
async def delist_submit(request: Request):
    task, error = _create_operation_task("delist", await request.json())
    if error:
        return error
    return {"success": True, "task": task}


@app.get("/api/delist/pending")
async def delist_pending():
    with _operation_lock:
        tasks = _pending_tasks("delist")
    return {"tasks": tasks, "count": len(tasks)}


@app.post("/api/delist/complete")
async def delist_complete(request: Request):
    return _complete_operation_task(await request.json())


@app.get("/api/delist/history")
async def delist_history():
    with _operation_lock:
        tasks = _history_tasks("delist")
    return {"tasks": tasks, "count": len(tasks)}


@app.post("/api/promotion-adjust")
async def promotion_adjust_submit(request: Request):
    task, error = _create_operation_task("promotion_adjust", await request.json())
    if error:
        return error
    return {"success": True, "task": task}


@app.get("/api/promotion-adjust/pending")
async def promotion_adjust_pending():
    with _operation_lock:
        tasks = _pending_tasks("promotion_adjust")
    return {"tasks": tasks, "count": len(tasks)}


@app.post("/api/promotion-adjust/complete")
async def promotion_adjust_complete(request: Request):
    return _complete_operation_task(await request.json())


@app.get("/api/promotion-adjust/history")
async def promotion_adjust_history():
    with _operation_lock:
        tasks = _history_tasks("promotion_adjust")
    return {"tasks": tasks, "count": len(tasks)}

def _add_range(where, params, col, gte, lte):
    """添加数值范围条件"""
    if gte is not None:
        where.append(f"`{col}` >= %s")
        params.append(gte)
    if lte is not None:
        where.append(f"`{col}` <= %s")
        params.append(lte)


def _creation_date_expression(alias="cp"):
    """把链接信息表中的多种创建时间格式统一成 DATE。"""
    return (
        f"COALESCE("
        f"STR_TO_DATE(NULLIF(TRIM({alias}.`创建时间`), ''), '%%Y-%%m-%%d %%H:%%i:%%s'), "
        f"STR_TO_DATE(NULLIF(TRIM({alias}.`创建时间`), ''), '%%Y-%%m-%%d %%H:%%i'), "
        f"STR_TO_DATE(NULLIF(TRIM({alias}.`创建时间`), ''), '%%Y%%m%%d'), "
        f"STR_TO_DATE(NULLIF(TRIM({alias}.`创建时间`), ''), '%%Y-%%m-%%d')"
        f")"
    )


def _creation_window(creation_days=None, creation_start=None, creation_end=None):
    start = str(creation_start or "").strip()
    end = str(creation_end or "").strip()
    if creation_days and not start and not end:
        try:
            days = max(1, int(creation_days))
            yesterday = datetime.now().date() - timedelta(days=1)
            start = (yesterday - timedelta(days=days - 1)).isoformat()
            end = yesterday.isoformat()
        except (TypeError, ValueError):
            start = end = ""
    if start > end and end:
        start, end = end, start
    return start, end


def _creation_link_ids(conn, creation_days=None, creation_start=None, creation_end=None):
    """一次性读取命中创建日期的链接 ID；pdd_link_info 是链接级资料源，查询量小且稳定。"""
    start, end = _creation_window(creation_days, creation_start, creation_end)
    if not start and not end:
        return None
    date_expr = _creation_date_expression("cp")
    conditions = []
    if start:
        conditions.append(f"DATE({date_expr}) >= %s")
    if end:
        conditions.append(f"DATE({date_expr}) <= %s")
    cur = conn.cursor()
    cur.execute(f"SELECT DISTINCT cp.`链接ID` FROM `{LINK_INFO_TABLE}` cp WHERE {' AND '.join(conditions)}", [value for value in (start, end) if value])
    return [str(row[0]) for row in cur.fetchall() if row[0] not in (None, '')]


def _append_creation_filter(where, params, creation_days=None, creation_start=None, creation_end=None, link_column="`链接id`", conn=None):
    """按链接创建日期过滤，日期来源为链接信息表，范围含首尾日期。"""
    start, end = _creation_window(creation_days, creation_start, creation_end)
    if not start and not end:
        return
    ids = _creation_link_ids(conn, creation_days, creation_start, creation_end) if conn is not None else None
    if ids is not None:
        if not ids:
            where.append("1=0")
            return
        placeholders = ",".join(["%s"] * len(ids))
        where.append(f"{link_column} IN ({placeholders})")
        params.extend(ids)
        return
    date_expr = _creation_date_expression("cp")
    conditions = []
    if start:
        conditions.append(f"DATE({date_expr}) >= %s")
        params.append(start)
    if end:
        conditions.append(f"DATE({date_expr}) <= %s")
        params.append(end)
    where.append(f"{link_column} IN (SELECT cp.`链接ID` FROM `{LINK_INFO_TABLE}` cp WHERE {' AND '.join(conditions)})")


def _creation_select_expression(outer_table=TABLE_NAME):
    return f"(SELECT MAX(cp.`创建时间`) FROM `{LINK_INFO_TABLE}` cp WHERE cp.`链接ID` = {outer_table}.`链接id`) AS `链接创建时间`"


def _link_field_kind(column_type):
    """把 MySQL 字段类型转换成前端筛选器可理解的类型。"""
    normalized = str(column_type or '').lower()
    if any(token in normalized for token in ('date', 'time', 'year')):
        return 'date'
    if any(token in normalized for token in ('int', 'decimal', 'numeric', 'double', 'float', 'real', 'bit')):
        return 'number'
    return 'text'


def _link_schema(cursor):
    cursor.execute(f"SHOW COLUMNS FROM {TABLE_NAME}")
    rows = cursor.fetchall()
    return {row[0]: _link_field_kind(row[1]) for row in rows}


def _append_brand_filter(where, params, brand):
    """品牌是由店铺名称推导的展示字段，统一应用到各个看板接口。"""
    brand = str(brand or '').strip()
    if not brand:
        return
    patterns = {'浪奇': '%浪奇%', '威王': '%威王%', '舒蕾': '%舒蕾%'}
    if brand in patterns:
        where.append('`店铺名称` LIKE %s')
        params.append(patterns[brand])
    elif brand == '白牌':
        where.append('(`店铺名称` IS NULL OR (`店铺名称` NOT LIKE %s AND `店铺名称` NOT LIKE %s AND `店铺名称` NOT LIKE %s))')
        params.extend(['%浪奇%', '%威王%', '%舒蕾%'])


def _apply_link_json_filters(where, params, raw_filters, field_types, deferred_numeric_filters=None):
    """把高级筛选器安全地转换成参数化 SQL 条件。"""
    if not raw_filters:
        return
    try:
        filters = json.loads(raw_filters)
    except (TypeError, json.JSONDecodeError):
        return
    if not isinstance(filters, list):
        return

    for item in filters:
        if not isinstance(item, dict):
            continue
        field = str(item.get('field') or '').strip()
        op = str(item.get('op') or 'contains').strip().lower()
        v1 = str(item.get('v1') or '').strip()
        v2 = str(item.get('v2') or '').strip()
        if not field or (not v1 and not v2):
            continue

        # 品牌是由店铺名称推导的展示字段，不是数据库物理字段。
        if field == '品牌':
            brand = v1 or v2
            if brand == '浪奇':
                where.append("`店铺名称` LIKE %s")
                params.append('%浪奇%')
            elif brand == '威王':
                where.append("`店铺名称` LIKE %s")
                params.append('%威王%')
            elif brand == '舒蕾':
                where.append("`店铺名称` LIKE %s")
                params.append('%舒蕾%')
            elif brand == '白牌':
                where.append("(`店铺名称` IS NULL OR (`店铺名称` NOT LIKE %s AND `店铺名称` NOT LIKE %s AND `店铺名称` NOT LIKE %s))")
                params.extend(['%浪奇%', '%威王%', '%舒蕾%'])
            continue

        if field in ('链接id', '链接 ID'):
            link_id_values = [re.sub(r'\.0$', '', value.strip()) for value in v1.split(',') if value.strip()]
            if link_id_values:
                placeholders = ', '.join(['%s'] * len(link_id_values))
                where.append(f"`链接id` IN ({placeholders})")
                params.extend(link_id_values)
            continue

        if field == '链接创建时间':
            date_expr = _creation_date_expression("cp")
            conditions = []
            if op in ('gte', 'between') and v1:
                conditions.append(f"DATE({date_expr}) >= %s")
                params.append(v1)
            if op in ('lte', 'between') and v2:
                conditions.append(f"DATE({date_expr}) <= %s")
                params.append(v2)
            if op not in ('gte', 'lte', 'between') and v1:
                conditions.append(f"DATE({date_expr}) = %s")
                params.append(v1)
            if len(conditions) > 1:
                where.append(f"{TABLE_NAME}.`链接id` IN (SELECT cp.`链接ID` FROM `{LINK_INFO_TABLE}` cp WHERE {' AND '.join(conditions)})")
            continue

        if field not in field_types or field == 'id':
            continue
        kind = field_types[field]
        column = f"`{field}`"
        if kind == 'text':
            if op in ('equals', 'eq'):
                where.append(f"{column} = %s")
                params.append(v1)
            else:
                where.append(f"{column} LIKE %s")
                params.append(f"%{v1}%")
            continue

        if kind == 'date':
            if op == 'gte':
                where.append(f"{column} >= %s")
                params.append(v1)
            elif op == 'lte':
                where.append(f"{column} <= %s")
                params.append(v1)
            else:
                if v1:
                    where.append(f"{column} >= %s")
                    params.append(v1)
                if v2:
                    where.append(f"{column} <= %s")
                    params.append(v2)
            continue

        try:
            n1 = float(v1) if v1 else None
            n2 = float(v2) if v2 else None
        except ValueError:
            continue
        if deferred_numeric_filters is not None:
            deferred_numeric_filters.append({'field': field, 'op': op, 'v1': n1, 'v2': n2})
            continue
        if op == 'gte' and n1 is not None:
            _add_range(where, params, field, n1, None)
        elif op == 'lte' and n1 is not None:
            _add_range(where, params, field, None, n1)
        else:
            _add_range(where, params, field, n1, n2)


def _aggregate_ratio(numerator, denominator):
    """按聚合后的分子/分母重新计算比例字段，保持数据库的十进制口径。"""
    try:
        numerator = float(numerator or 0)
        denominator = float(denominator or 0)
    except (TypeError, ValueError):
        return 0.0
    return round(numerator / denominator, 4) if denominator else 0.0


def _recompute_link_person_metrics(item):
    """把链接 ID + 负责人分组后的金额字段转换为周期比例指标。"""
    revenue = item.get('收入', 0)
    cost = item.get('成本', 0)
    shipping = item.get('快递', 0)
    gross_profit = item.get('毛利', 0)
    promotion = item.get('推广费', 0)
    platform_profit = item.get('平台利润', 0)
    total_spend = item.get('总花费(元)', 0)
    trade_amount = item.get('交易额(元)', 0)
    net_trade_amount = item.get('净交易额(元)', 0)
    orders = item.get('成交笔数', 0)
    net_orders = item.get('净成交笔数', 0)
    direct_orders = item.get('直接成交笔数', 0)
    indirect_orders = item.get('间接成交笔数', 0)

    if '成本+快递' in item:
        item['成本+快递'] = round(float(cost or 0) + float(shipping or 0), 4)
    ratio_fields = {
        '成本占比': (cost, revenue),
        '快递占比': (shipping, revenue),
        '货品快递总和占比': (float(cost or 0) + float(shipping or 0), revenue),
        '毛利率': (gross_profit, revenue),
        '推广费占比': (promotion, revenue),
        '利润率': (platform_profit, revenue),
        '全站推广费比': (item.get('直接交易额(元)', 0), total_spend),
        '净交易额占比': (net_trade_amount, trade_amount),
        '实际投产比': (trade_amount, total_spend),
        '净实际投产比': (net_trade_amount, total_spend),
        '每笔净成交花费(元)': (total_spend, net_orders),
        '每笔成交花费(元)': (total_spend, orders),
        '每笔成交金额(元)': (trade_amount, orders),
        '每笔直接成交金额(元)': (item.get('直接交易额(元)', 0), direct_orders),
        '每笔间接成交金额(元)': (item.get('间接交易额(元)', 0), indirect_orders),
    }
    for field, (numerator, denominator) in ratio_fields.items():
        if field in item:
            item[field] = _aggregate_ratio(numerator, denominator)
    return item


def _matches_aggregated_numeric_filters(item, filters):
    """在聚合结果上执行数值筛选，避免把日粒度比例误当成周期比例。"""
    for item_filter in filters or []:
        field = item_filter.get('field')
        try:
            actual = float(item.get(field) or 0)
        except (TypeError, ValueError):
            return False
        op = item_filter.get('op')
        v1 = item_filter.get('v1')
        v2 = item_filter.get('v2')
        if op == 'gte' and v1 is not None and actual < v1:
            return False
        if op == 'lte' and v1 is not None and actual > v1:
            return False
        if op == 'between' and ((v1 is not None and actual < v1) or (v2 is not None and actual > v2)):
            return False
    return True


def _get_aggregated_link_person_page(conn, where, params, deferred_numeric_filters, page, size):
    """查询链接设置预览：先筛选明细，再按链接 ID + 负责人聚合。"""
    schema_cursor = conn.cursor()
    schema_cursor.execute(f"SHOW COLUMNS FROM {TABLE_NAME}")
    columns = [row[0] for row in schema_cursor.fetchall()]
    field_types = _link_schema(conn.cursor())
    select_parts = []
    for column in columns:
        quoted = f"{TABLE_NAME}.`{column}`"
        alias = f"`{column}`"
        if column in ('链接id', '负责人'):
            select_parts.append(f"{quoted} AS {alias}")
        elif column == 'id':
            select_parts.append(f"MIN({quoted}) AS {alias}")
        elif field_types.get(column) == 'number':
            select_parts.append(f"SUM(COALESCE({quoted}, 0)) AS {alias}")
        elif field_types.get(column) == 'date':
            select_parts.append(f"MAX({quoted}) AS {alias}")
        else:
            select_parts.append(f"MAX({quoted}) AS {alias}")
    select_parts.append("MAX(link_created.link_created_at) AS `链接创建时间`")
    where_clause = " AND ".join(where)
    query = (
        f"SELECT {', '.join(select_parts)} "
        f"FROM {TABLE_NAME} "
        f"LEFT JOIN (SELECT `链接ID` AS link_id, MAX(`创建时间`) AS link_created_at "
        f"FROM `{LINK_INFO_TABLE}` GROUP BY `链接ID`) link_created "
        f"ON link_created.link_id = {TABLE_NAME}.`链接id` "
        f"WHERE {where_clause} "
        f"GROUP BY {TABLE_NAME}.`链接id`, {TABLE_NAME}.`负责人` "
        f"ORDER BY SUM(COALESCE({TABLE_NAME}.`收入`, 0)) DESC, "
        f"MAX({TABLE_NAME}.`数据日期`) DESC, {TABLE_NAME}.`链接id`"
    )
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    result_columns = [description[0] for description in cursor.description]
    data = []
    for row in rows:
        item = dict(zip(result_columns, row))
        for key, value in list(item.items()):
            if isinstance(value, Decimal):
                item[key] = round(float(value), 4)
            elif isinstance(value, float):
                item[key] = round(value, 4)
        _recompute_link_person_metrics(item)
        if _matches_aggregated_numeric_filters(item, deferred_numeric_filters):
            data.append(item)

    total = len(data)
    offset = (page - 1) * size
    return {
        'success': True,
        'data': data[offset:offset + size],
        'total': total,
        'page': page,
        'size': size,
        'pages': (total + size - 1) // size if total > 0 else 0,
        'aggregation': 'link_person',
        'aggregation_label': '链接 ID + 负责人',
        'profit_rate_formula': 'SUM(平台利润) / SUM(收入)',
    }


@app.get("/api/v3/link-fields")
def get_link_fields():
    """返回链接明细表当前数据库字段，供字段选择器动态使用。"""
    conn = get_mysql()
    try:
        cursor = conn.cursor()
        cursor.execute(f"SHOW COLUMNS FROM {TABLE_NAME}")
        fields = [
            {'key': row[0], 'label': row[0], 'type': _link_field_kind(row[1]), 'nullable': row[2] == 'YES'}
            for row in cursor.fetchall()
            if row[0] != 'id'
        ]
        fields.append({'key': '链接创建时间', 'label': '链接创建时间', 'type': 'date', 'nullable': True})
        return {'success': True, 'fields': fields}
    finally:
        conn.close()

@app.get("/api/v3/links")
def get_links(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str = Query(default=""),
    start: str = Query(default=None),
    end: str = Query(default=None),
    link_ids: str = Query(default=None),
    # 多维度筛选参数
    product_code: str = Query(default=None),
    product_name: str = Query(default=None),
    brand: str = Query(default=None),
    store_name: str = Query(default=None),
    store_person: str = Query(default=None),
    profit_rate_gte: float = Query(default=None),
    profit_rate_lte: float = Query(default=None),
    gm_gte: float = Query(default=None),
    gm_lte: float = Query(default=None),
    promo_pct_gte: float = Query(default=None),
    promo_pct_lte: float = Query(default=None),
    cost_pct_gte: float = Query(default=None),
    cost_pct_lte: float = Query(default=None),
    revenue_gte: float = Query(default=None),
    revenue_lte: float = Query(default=None),
    orders_gte: float = Query(default=None),
    orders_lte: float = Query(default=None),
    creation_days: int = Query(default=None, ge=1, le=3650),
    creation_start: str = Query(default=None),
    creation_end: str = Query(default=None),
    filter_json: str = Query(default=""),
    aggregate: str = Query(default=""),
):
    """分页返回链接级明细数据（支持多维度筛选）"""
    conn = get_mysql()
    try:
        field_types = _link_schema(conn.cursor())
        where = ["1=1"]
        params = []
        if search:
            where.append("(链接id LIKE %s OR 商品编码 LIKE %s OR 商品标题 LIKE %s OR 店铺名称 LIKE %s)")
            like = f"%{search}%"
            params.extend([like, like, like, like])
        if link_ids:
            ids = [x.strip() for x in link_ids.split(",") if x.strip()]
            if ids:
                placeholders = ",".join(["%s"] * len(ids))
                where.append(f"链接id IN ({placeholders})")
                params.extend(ids)
        if start:
            where.append("数据日期 >= %s")
            params.append(start)
        if end:
            where.append("数据日期 <= %s")
            params.append(end)
        # 多维度筛选
        if product_code:
            where.append("商品编码 LIKE %s")
            params.append(f"%{product_code}%")
        if product_name:
            where.append("商品标题 LIKE %s")
            params.append(f"%{product_name}%")
        _append_brand_filter(where, params, brand)
        if store_name:
            where.append("店铺名称 LIKE %s")
            params.append(f"%{store_name}%")
        if store_person:
            where.append("负责人 = %s")
            params.append(store_person)
        _append_creation_filter(where, params, creation_days, creation_start, creation_end, f"{TABLE_NAME}.`链接id`", conn)
        # 数值范围筛选
        _add_range(where, params, "利润率", profit_rate_gte, profit_rate_lte)
        _add_range(where, params, "毛利率", gm_gte, gm_lte)
        _add_range(where, params, "推广费占比", promo_pct_gte, promo_pct_lte)
        _add_range(where, params, "成本占比", cost_pct_gte, cost_pct_lte)
        _add_range(where, params, "收入", revenue_gte, revenue_lte)
        _add_range(where, params, "单量", orders_gte, orders_lte)
        deferred_numeric_filters = [] if aggregate == 'link_person' else None
        _apply_link_json_filters(where, params, filter_json, field_types, deferred_numeric_filters)

        if aggregate == 'link_person':
            return _get_aggregated_link_person_page(
                conn,
                where,
                params,
                deferred_numeric_filters,
                page,
                size,
            )

        where_clause = " AND ".join(where)

        # 总数
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE {where_clause}", params)
        total = cur.fetchone()[0]

        # 分页数据
        offset = (page - 1) * size
        cur.execute(
            f"SELECT {TABLE_NAME}.*, {_creation_select_expression(TABLE_NAME)} "
            f"FROM {TABLE_NAME} WHERE {where_clause} "
            f"ORDER BY 数据日期 DESC, 收入 DESC "
            f"LIMIT %s OFFSET %s",
            params + [size, offset]
        )
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        data = [dict(zip(cols, row)) for row in rows]

        # 处理浮点数精度
        for item in data:
            for k, v in item.items():
                if isinstance(v, float):
                    item[k] = round(v, 4)

        return {
            "success": True,
            "data": data,
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size if total > 0 else 0
        }
    finally:
        conn.close()

def _link_summary_brand(store):
    store = str(store or "")
    if "浪奇" in store:
        return "浪奇"
    if "威王" in store or "VEWIN" in store.upper():
        return "威王"
    if "舒蕾" in store or "SLEK" in store.upper():
        return "舒蕾"
    return "白牌"

def _summary_ratio(numerator, denominator):
    numerator = float(numerator or 0)
    denominator = float(denominator or 0)
    return round(numerator / denominator * 100, 1) if denominator else 0.0


def _operating_number(value):
    """把 MySQL Decimal/None/字符串安全转换为浮点数。"""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _operating_ratio(numerator, denominator):
    """统一计算比例；接口输出比例数值而不是百分号字符串。"""
    numerator = _operating_number(numerator)
    denominator = _operating_number(denominator)
    return round(numerator / denominator * 100, 2) if denominator else 0.0


def _operating_brand(store_name):
    """链接信息表没有单独品牌列时，沿用店铺名称推导品牌。"""
    store = str(store_name or "")
    upper = store.upper()
    if "浪奇" in store or "LANGQI" in upper:
        return "浪奇"
    if "威王" in store or "VEWIN" in upper:
        return "威王"
    if "舒蕾" in store or "SLEK" in upper:
        return "舒蕾"
    return "白牌"


def _operating_sum(row, field):
    return _operating_number(row.get(field))


def _operating_profit_row(row):
    """把利润日粒度行转换为统一接口字段。"""
    revenue = _operating_sum(row, "order_amount")
    goods_cost = _operating_sum(row, "goods_cost")
    shipping_cost = _operating_sum(row, "shipping_cost")
    gross_profit = _operating_sum(row, "gross_profit")
    platform_profit = _operating_sum(row, "platform_profit")
    return {
        "dataDate": str(row.get("data_date") or "")[:10],
        "person": str(row.get("person") or ""),
        "profitOrders": _operating_sum(row, "profit_orders"),
        "orderAmount": revenue,
        "refundAmount": _operating_sum(row, "refund_amount"),
        "goodsCost": goods_cost,
        "shippingCost": shipping_cost,
        "afterRefundOrderAmount": _operating_sum(row, "after_refund_order_amount"),
        "afterReturnOrderAmount": _operating_sum(row, "after_return_order_amount"),
        "afterReturnGoodsCost": _operating_sum(row, "after_return_goods_cost"),
        "costPct": _operating_ratio(goods_cost, revenue),
        "afterReturnShippingCost": _operating_sum(row, "after_return_shipping_cost"),
        "shippingPct": _operating_ratio(shipping_cost, revenue),
        "goodsShippingTotal": _operating_sum(row, "goods_shipping_total"),
        "goodsShippingPct": _operating_ratio(_operating_sum(row, "goods_shipping_total"), revenue),
        "remoteSurcharge": _operating_sum(row, "remote_surcharge"),
        "grossProfit": gross_profit,
        "grossMargin": _operating_ratio(gross_profit, revenue),
        "techServiceFee": _operating_sum(row, "tech_service_fee"),
        "estimatedAfterSale": _operating_sum(row, "estimated_after_sale"),
        "profitPromotionFee": _operating_sum(row, "profit_promotion_fee"),
        "profitPromotionPct": _operating_ratio(_operating_sum(row, "profit_promotion_fee"), revenue),
        "freightInsurance": _operating_sum(row, "freight_insurance"),
        "tax": _operating_sum(row, "tax"),
        "platformProfit": platform_profit,
        "profitRate": _operating_ratio(platform_profit, revenue),
        "returnRate": _operating_number(row.get("return_rate")),
        "dataSource": "profit",
    }


def _operating_promotion_row(row):
    """把推广表的小时源数据按日期聚合后的行转换为统一字段。"""
    spend = _operating_sum(row, "promotion_spend")
    revenue = _operating_sum(row, "promotion_revenue")
    net_revenue = _operating_sum(row, "promotion_net_revenue")
    orders = _operating_sum(row, "promotion_orders")
    net_orders = _operating_sum(row, "promotion_net_orders")
    settled_revenue = _operating_sum(row, "settled_revenue")
    settled_orders = _operating_sum(row, "settled_orders")
    return {
        "dataDate": str(row.get("data_date") or "")[:10],
        "promotionSpend": spend,
        "promotionRevenue": revenue,
        "promotionRoi": revenue / spend if spend else 0.0,
        "promotionTotalSpend": _operating_sum(row, "promotion_total_spend"),
        "promotionNetRevenue": net_revenue,
        "promotionNetRoi": net_revenue / spend if spend else 0.0,
        "promotionNetOrders": net_orders,
        "promotionAvgNetOrderSpend": spend / net_orders if net_orders else 0.0,
        "promotionNetRevenueRatio": _operating_ratio(net_revenue, revenue),
        "promotionNetOrdersRatio": _operating_ratio(net_orders, orders),
        "promotionAvgNetOrderRevenue": net_revenue / net_orders if net_orders else 0.0,
        "settledRevenue": settled_revenue,
        "settledRoi": settled_revenue / spend if spend else 0.0,
        "settledOrders": settled_orders,
        "refundExemptionRate": _operating_number(row.get("refund_exemption_rate")),
        "cancelExemptionRate": _operating_number(row.get("cancel_exemption_rate")),
        "settledAvgOrderSpend": spend / settled_orders if settled_orders else 0.0,
        "revenueSettlementRate": _operating_ratio(settled_revenue, revenue),
        "orderSettlementRate": _operating_ratio(settled_orders, orders),
        "settledAvgOrderRevenue": settled_revenue / settled_orders if settled_orders else 0.0,
        "promotionOrders": orders,
        "promotionAvgOrderSpend": spend / orders if orders else 0.0,
        "promotionAvgOrderRevenue": revenue / orders if orders else 0.0,
        "directRevenue": _operating_sum(row, "direct_revenue"),
        "indirectRevenue": _operating_sum(row, "indirect_revenue"),
        "directOrders": _operating_sum(row, "direct_orders"),
        "indirectOrders": _operating_sum(row, "indirect_orders"),
        "impressions": _operating_sum(row, "impressions"),
        "clicks": _operating_sum(row, "clicks"),
        "sitePromotionRatio": _operating_number(row.get("site_promotion_ratio")),
        "promotionSource": "promotion_hourly",
    }


@app.get("/api/v3/link-operating-summary")
def get_link_operating_summary(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=20000),
    search: str = Query(default=""),
    start: str = Query(default=None),
    end: str = Query(default=None),
    link_ids: str = Query(default=None),
    product_code: str = Query(default=None),
    product_name: str = Query(default=None),
    brand: str = Query(default=None),
    store_name: str = Query(default=None),
    store_person: str = Query(default=None),
    creation_days: int = Query(default=None, ge=1, le=3650),
    creation_start: str = Query(default=None),
    creation_end: str = Query(default=None),
    sort_by: str = Query(default="orderAmount"),
    sort_order: str = Query(default="desc"),
):
    """统一链接经营表：链接维度 + 利润日粒度 + 推广小时粒度安全合并。

    利润表先按 链接ID + 负责人 + 数据日期 聚合，推广表先按
    商品ID(链接ID) + 日期 + 小时写入事实粒度，再按日期汇总到主表。
    两类事实不会直接做明细 JOIN，从根源上避免利润金额被小时数放大。
    """
    conn = get_mysql()
    try:
        # 1) 链接信息维度：它是展示字段和创建时间筛选的来源。
        info_where = ["`链接ID` IS NOT NULL", "`链接ID` <> ''"]
        info_params = []
        requested_ids = [normalize_join_id_value(item) for item in str(link_ids or "").replace("，", ",").split(",") if item.strip()]
        requested_ids = [item for item in requested_ids if item]
        if requested_ids:
            info_where.append("`链接ID` IN (" + ",".join(["%s"] * len(requested_ids)) + ")")
            info_params.extend(requested_ids)
        if search:
            like = f"%{search.strip()}%"
            info_where.append("(`链接ID` LIKE %s OR `商品编码` LIKE %s OR `商品标题` LIKE %s OR `店铺名称` LIKE %s)")
            info_params.extend([like, like, like, like])
        if product_code:
            info_where.append("`商品编码` LIKE %s")
            info_params.append(f"%{product_code.strip()}%")
        if product_name:
            info_where.append("`商品标题` LIKE %s")
            info_params.append(f"%{product_name.strip()}%")
        if store_name:
            info_where.append("`店铺名称` LIKE %s")
            info_params.append(f"%{store_name.strip()}%")
        if brand:
            brand_patterns = {"浪奇": "%浪奇%", "威王": "%威王%", "舒蕾": "%舒蕾%"}
            if brand in brand_patterns:
                info_where.append("`店铺名称` LIKE %s")
                info_params.append(brand_patterns[brand])
            elif brand == "白牌":
                info_where.append("(`店铺名称` IS NULL OR (`店铺名称` NOT LIKE %s AND `店铺名称` NOT LIKE %s AND `店铺名称` NOT LIKE %s))")
                info_params.extend(["%浪奇%", "%威王%", "%舒蕾%"])
        creation_start_value, creation_end_value = _creation_window(creation_days, creation_start, creation_end)
        if creation_start_value or creation_end_value:
            date_expr = _creation_date_expression("li")
            if creation_start_value:
                info_where.append(f"DATE({date_expr}) >= %s")
                info_params.append(creation_start_value)
            if creation_end_value:
                info_where.append(f"DATE({date_expr}) <= %s")
                info_params.append(creation_end_value)

        cur = conn.cursor()
        cur.execute(
            f"SELECT `链接ID`, `店铺名称`, `图片链接`, `商品标题`, `创建时间`, `商品编码` "
            f"FROM `{LINK_INFO_TABLE}` li WHERE {' AND '.join(info_where)}",
            info_params,
        )
        info_by_id = {}
        for link_id, store, image_url, title, created_at, code in cur.fetchall():
            normalized_id = normalize_join_id_value(link_id)
            if not normalized_id or normalized_id in info_by_id:
                continue
            info_by_id[normalized_id] = {
                "storeName": str(store or ""),
                "imageUrl": str(image_url or ""),
                "title": str(title or ""),
                "createdAt": str(created_at or "")[:19],
                "productCode": str(code or ""),
            }
        allowed_ids = set(info_by_id)
        if not allowed_ids:
            return {"success": True, "data": [], "summary": {"links": 0}, "total": 0, "page": page, "size": size, "pages": 0}

        # 2) 利润事实：明确按 链接ID + 负责人 + 数据日期 聚合。
        cur.execute(f"SHOW COLUMNS FROM `{TABLE_NAME}`")
        profit_columns = {row[0] for row in cur.fetchall()}

        def profit_expr(column, alias, aggregate="SUM"):
            return f"{aggregate}(COALESCE(`{column}`, 0)) AS `{alias}`" if column in profit_columns else f"0 AS `{alias}`"

        profit_where = ["`链接id` IS NOT NULL", "`链接id` <> ''"]
        profit_params = []
        if start:
            profit_where.append("`数据日期` >= %s")
            profit_params.append(start)
        if end:
            profit_where.append("`数据日期` <= %s")
            profit_params.append(end)
        if store_person:
            profit_where.append("`负责人` = %s")
            profit_params.append(store_person)
        profit_sql = (
            f"SELECT `链接id` AS link_id, `负责人` AS person, `数据日期` AS data_date, "
            f"MAX(`商品编码`) AS product_code, MAX(`商品标题`) AS title, MAX(`店铺名称`) AS store_name, "
            f"{profit_expr('单量', 'profit_orders')}, {profit_expr('收入', 'order_amount')}, "
            f"{profit_expr('退款金额', 'refund_amount')}, {profit_expr('成本', 'goods_cost')}, {profit_expr('快递', 'shipping_cost')}, "
            f"{profit_expr('扣除退款订单金额', 'after_refund_order_amount')}, {profit_expr('扣除退货率后订单金额', 'after_return_order_amount')}, "
            f"{profit_expr('扣除退货率后货品成本', 'after_return_goods_cost')}, {profit_expr('扣除退货率后快递成本', 'after_return_shipping_cost')}, "
            f"{profit_expr('成本+快递', 'goods_shipping_total')}, {profit_expr('偏远加收', 'remote_surcharge')}, "
            f"{profit_expr('毛利', 'gross_profit')}, {profit_expr('技术服务费', 'tech_service_fee')}, {profit_expr('预估售后', 'estimated_after_sale')}, "
            f"{profit_expr('推广费', 'profit_promotion_fee')}, {profit_expr('运费险', 'freight_insurance')}, {profit_expr('税费', 'tax')}, "
            f"{profit_expr('平台利润', 'platform_profit')}, {profit_expr('退货率', 'return_rate', 'AVG')} "
            f"FROM `{TABLE_NAME}` WHERE {' AND '.join(profit_where)} "
            f"GROUP BY `链接id`, `负责人`, `数据日期`"
        )
        cur.execute(profit_sql, profit_params)
        profit_columns_result = [item[0] for item in cur.description]
        profit_daily = []
        for raw in cur.fetchall():
            item = dict(zip(profit_columns_result, raw))
            link_id = normalize_join_id_value(item.get("link_id"))
            if link_id in allowed_ids:
                item["link_id"] = link_id
                profit_daily.append(item)

        # 3) 推广事实：先按 商品ID + 店铺 + 日期 聚合；源表自身仍保持日期 + 小时唯一粒度。
        promotion_where = ["(is_deleted IS NULL OR LOWER(CAST(is_deleted AS CHAR)) NOT IN ('1', 'true', 'yes'))"]
        promotion_params = []
        if start:
            promotion_where.append("data_date >= %s")
            promotion_params.append(start)
        if end:
            promotion_where.append("data_date <= %s")
            promotion_params.append(end)
        cur.execute(f"SHOW COLUMNS FROM `{PROMOTION_HOURLY_TABLE}`")
        promotion_columns = {item[0] for item in cur.fetchall()}

        def promotion_expr(column, alias, aggregate="SUM"):
            if column not in promotion_columns:
                return f"0 AS `{alias}`"
            return f"{aggregate}(COALESCE(`{column}`, 0)) AS `{alias}`"

        promotion_sql = f"""
            SELECT product_id, store_name, data_date,
                   MAX(product_name) AS product_name,
                   {promotion_expr('spend', 'promotion_spend')}, {promotion_expr('total_spend', 'promotion_total_spend')},
                   {promotion_expr('revenue', 'promotion_revenue')}, {promotion_expr('net_revenue', 'promotion_net_revenue')},
                   {promotion_expr('net_orders', 'promotion_net_orders')}, {promotion_expr('orders', 'promotion_orders')},
                   {promotion_expr('settled_revenue', 'settled_revenue')}, {promotion_expr('settled_orders', 'settled_orders')},
                   {promotion_expr('refund_exemption_rate', 'refund_exemption_rate', 'AVG')},
                   {promotion_expr('cancel_exemption_rate', 'cancel_exemption_rate', 'AVG')},
                   {promotion_expr('direct_revenue', 'direct_revenue')}, {promotion_expr('indirect_revenue', 'indirect_revenue')},
                   {promotion_expr('direct_orders', 'direct_orders')}, {promotion_expr('indirect_orders', 'indirect_orders')},
                   {promotion_expr('impressions', 'impressions')}, {promotion_expr('clicks', 'clicks')},
                   {promotion_expr('site_promotion_ratio', 'site_promotion_ratio', 'AVG')}
            FROM `{PROMOTION_HOURLY_TABLE}`
            WHERE {' AND '.join(promotion_where)}
            GROUP BY product_id, store_name, data_date
        """
        cur.execute(promotion_sql, promotion_params)
        promotion_columns_result = [item[0] for item in cur.description]
        promotion_daily = []
        for raw in cur.fetchall():
            item = dict(zip(promotion_columns_result, raw))
            link_id = normalize_join_id_value(item.get("product_id"))
            if link_id in allowed_ids:
                item["link_id"] = link_id
                promotion_daily.append(item)

        profit_by_link = defaultdict(list)
        for item in profit_daily:
            profit_by_link[item["link_id"]].append(_operating_profit_row(item))
        promotion_by_link = defaultdict(list)
        for item in promotion_daily:
            promotion_by_link[item["link_id"]].append(_operating_promotion_row(item))

        if store_person:
            person_ids = set(item["link_id"] for item in profit_daily)
        else:
            person_ids = allowed_ids

        def in_text_filter(link_id, info):
            if search:
                needle = search.strip().lower()
                values = [link_id, info.get("productCode"), info.get("title"), info.get("storeName")]
                if not any(needle in str(value or "").lower() for value in values):
                    return False
            if product_code and product_code.strip().lower() not in info.get("productCode", "").lower():
                return False
            if product_name and product_name.strip().lower() not in info.get("title", "").lower():
                return False
            if store_name and store_name.strip().lower() not in info.get("storeName", "").lower():
                return False
            if brand and _operating_brand(info.get("storeName")) != brand:
                return False
            return True

        def merge_daily(link_id):
            profit_items = profit_by_link.get(link_id, [])
            promotion_items = promotion_by_link.get(link_id, [])
            dates = sorted({item["dataDate"] for item in profit_items + promotion_items if item.get("dataDate")})
            daily = []
            persons = sorted({item.get("person") for item in profit_items if item.get("person")})
            for data_date in dates:
                profit_day = [item for item in profit_items if item["dataDate"] == data_date]
                promotion_day = [item for item in promotion_items if item["dataDate"] == data_date]
                profit = {}
                for item in profit_day:
                    for key, value in item.items():
                        if key not in {"dataDate", "person", "dataSource", "returnRate"}:
                            profit[key] = profit.get(key, 0) + _operating_number(value)
                    if item.get("returnRate") is not None:
                        profit["returnRate"] = item.get("returnRate")
                promo = {}
                for item in promotion_day:
                    for key, value in item.items():
                        if key not in {"dataDate", "promotionSource", "promotionRoi", "promotionNetRoi", "promotionAvgNetOrderSpend", "promotionNetRevenueRatio", "promotionNetOrdersRatio", "promotionAvgNetOrderRevenue", "settledRoi", "settledAvgOrderSpend", "revenueSettlementRate", "orderSettlementRate", "settledAvgOrderRevenue", "promotionAvgOrderSpend", "promotionAvgOrderRevenue"}:
                            promo[key] = promo.get(key, 0) + _operating_number(value)
                row = {"linkId": link_id, "dataDate": data_date, "person": "、".join(persons) or ""}
                row.update(profit)
                row.update(promo)
                row["promotionRoi"] = row.get("promotionRevenue", 0) / row.get("promotionSpend", 0) if row.get("promotionSpend") else 0.0
                row["promotionNetRoi"] = row.get("promotionNetRevenue", 0) / row.get("promotionSpend", 0) if row.get("promotionSpend") else 0.0
                row["promotionAvgNetOrderSpend"] = row.get("promotionSpend", 0) / row.get("promotionNetOrders", 0) if row.get("promotionNetOrders") else 0.0
                row["promotionNetRevenueRatio"] = _operating_ratio(row.get("promotionNetRevenue"), row.get("promotionRevenue"))
                row["promotionNetOrdersRatio"] = _operating_ratio(row.get("promotionNetOrders"), row.get("promotionOrders"))
                row["promotionAvgNetOrderRevenue"] = row.get("promotionNetRevenue", 0) / row.get("promotionNetOrders", 0) if row.get("promotionNetOrders") else 0.0
                row["settledRoi"] = row.get("settledRevenue", 0) / row.get("promotionSpend", 0) if row.get("promotionSpend") else 0.0
                row["settledAvgOrderSpend"] = row.get("promotionSpend", 0) / row.get("settledOrders", 0) if row.get("settledOrders") else 0.0
                row["revenueSettlementRate"] = _operating_ratio(row.get("settledRevenue"), row.get("promotionRevenue"))
                row["orderSettlementRate"] = _operating_ratio(row.get("settledOrders"), row.get("promotionOrders"))
                row["settledAvgOrderRevenue"] = row.get("settledRevenue", 0) / row.get("settledOrders", 0) if row.get("settledOrders") else 0.0
                row["promotionAvgOrderSpend"] = row.get("promotionSpend", 0) / row.get("promotionOrders", 0) if row.get("promotionOrders") else 0.0
                row["promotionAvgOrderRevenue"] = row.get("promotionRevenue", 0) / row.get("promotionOrders", 0) if row.get("promotionOrders") else 0.0
                row["costPct"] = _operating_ratio(row.get("goodsCost"), row.get("orderAmount"))
                row["shippingPct"] = _operating_ratio(row.get("shippingCost"), row.get("orderAmount"))
                row["goodsShippingPct"] = _operating_ratio(row.get("goodsShippingTotal"), row.get("orderAmount"))
                row["grossMargin"] = _operating_ratio(row.get("grossProfit"), row.get("orderAmount"))
                row["profitPromotionPct"] = _operating_ratio(row.get("profitPromotionFee"), row.get("orderAmount"))
                row["profitRate"] = _operating_ratio(row.get("platformProfit"), row.get("orderAmount"))
                daily.append(row)
            return daily

        rows = []
        for link_id in sorted(person_ids):
            info = info_by_id.get(link_id, {})
            if not in_text_filter(link_id, info):
                continue
            daily_rows = merge_daily(link_id)
            if not daily_rows:
                continue
            persons = sorted({item.get("person") for item in profit_by_link.get(link_id, []) if item.get("person")})
            row = {"linkId": link_id, **info}
            row["brand"] = _operating_brand(info.get("storeName"))
            row["person"] = persons[0] if len(persons) == 1 else ("多个负责人" if persons else "")
            row["persons"] = persons
            row["firstDate"] = daily_rows[0]["dataDate"]
            row["lastDate"] = daily_rows[-1]["dataDate"]
            row["dataDays"] = len(daily_rows)
            row["profitDataDays"] = len(profit_by_link.get(link_id, []))
            row["promotionDataDays"] = len(promotion_by_link.get(link_id, []))
            for key in set().union(*(item.keys() for item in daily_rows)):
                if key in {"linkId", "dataDate", "person"}:
                    continue
                if key in {"costPct", "shippingPct", "goodsShippingPct", "grossMargin", "profitPromotionPct", "profitRate", "promotionRoi", "promotionNetRoi", "promotionAvgNetOrderSpend", "promotionNetRevenueRatio", "promotionNetOrdersRatio", "promotionAvgNetOrderRevenue", "settledRoi", "settledAvgOrderSpend", "revenueSettlementRate", "orderSettlementRate", "settledAvgOrderRevenue", "promotionAvgOrderSpend", "promotionAvgOrderRevenue"}:
                    continue
                row[key] = sum(_operating_number(item.get(key)) for item in daily_rows)
            revenue = row.get("orderAmount", 0)
            row["costPct"] = _operating_ratio(row.get("goodsCost"), revenue)
            row["shippingPct"] = _operating_ratio(row.get("shippingCost"), revenue)
            row["goodsShippingPct"] = _operating_ratio(row.get("goodsShippingTotal"), revenue)
            row["grossMargin"] = _operating_ratio(row.get("grossProfit"), revenue)
            row["profitPromotionPct"] = _operating_ratio(row.get("profitPromotionFee"), revenue)
            row["profitRate"] = _operating_ratio(row.get("platformProfit"), revenue)
            row["promotionRoi"] = row.get("promotionRevenue", 0) / row.get("promotionSpend", 0) if row.get("promotionSpend") else 0.0
            row["promotionNetRoi"] = row.get("promotionNetRevenue", 0) / row.get("promotionSpend", 0) if row.get("promotionSpend") else 0.0
            row["promotionAvgNetOrderSpend"] = row.get("promotionSpend", 0) / row.get("promotionNetOrders", 0) if row.get("promotionNetOrders") else 0.0
            row["promotionNetRevenueRatio"] = _operating_ratio(row.get("promotionNetRevenue"), row.get("promotionRevenue"))
            row["promotionNetOrdersRatio"] = _operating_ratio(row.get("promotionNetOrders"), row.get("promotionOrders"))
            row["promotionAvgNetOrderRevenue"] = row.get("promotionNetRevenue", 0) / row.get("promotionNetOrders", 0) if row.get("promotionNetOrders") else 0.0
            row["settledRoi"] = row.get("settledRevenue", 0) / row.get("promotionSpend", 0) if row.get("promotionSpend") else 0.0
            row["settledAvgOrderSpend"] = row.get("promotionSpend", 0) / row.get("settledOrders", 0) if row.get("settledOrders") else 0.0
            row["revenueSettlementRate"] = _operating_ratio(row.get("settledRevenue"), row.get("promotionRevenue"))
            row["orderSettlementRate"] = _operating_ratio(row.get("settledOrders"), row.get("promotionOrders"))
            row["settledAvgOrderRevenue"] = row.get("settledRevenue", 0) / row.get("settledOrders", 0) if row.get("settledOrders") else 0.0
            row["promotionAvgOrderSpend"] = row.get("promotionSpend", 0) / row.get("promotionOrders", 0) if row.get("promotionOrders") else 0.0
            row["promotionAvgOrderRevenue"] = row.get("promotionRevenue", 0) / row.get("promotionOrders", 0) if row.get("promotionOrders") else 0.0
            row["spend"] = row.get("promotionSpend", 0)
            row["revenue"] = row.get("promotionRevenue", 0)
            row["netRevenue"] = row.get("promotionNetRevenue", 0)
            row["orders"] = row.get("promotionNetOrders", 0)
            row["roi"] = row.get("promotionRoi", 0)
            row["netRoi"] = row.get("promotionNetRoi", 0)
            row["status"] = "有推广数据" if row.get("promotionDataDays") else "无推广数据"
            row["stage"] = ""
            row["targetRoi"] = None
            row["dailyRows"] = daily_rows
            rows.append(row)

        # 主表保留“链接信息表”中的全部链接；没有利润/推广事实的链接也展示，指标按 0 处理。
        # 这样用户才能识别“暂无事实数据”的链接，而不是把它误认为链接不存在。
        for link_id in sorted(allowed_ids - {item.get("linkId") for item in rows}):
            info = info_by_id.get(link_id, {})
            if not in_text_filter(link_id, info):
                continue
            row = {
                "linkId": link_id, **info, "brand": _operating_brand(info.get("storeName")),
                "person": "", "persons": [], "firstDate": "", "lastDate": "", "dataDays": 0,
                "profitDataDays": 0, "promotionDataDays": 0, "status": "无事实数据", "stage": "",
                "targetRoi": None, "dailyRows": [], "spend": 0, "revenue": 0, "netRevenue": 0,
                "orders": 0, "roi": 0, "netRoi": 0,
            }
            rows.append(row)

        sort_key_map = {
            "linkId": "linkId", "orderAmount": "orderAmount", "revenue": "orderAmount", "profitRate": "profitRate",
            "promotionSpend": "promotionSpend", "spend": "promotionSpend", "promotionRevenue": "promotionRevenue",
            "promotionRoi": "promotionRoi", "grossProfit": "grossProfit", "createdAt": "createdAt",
        }
        sort_key = sort_key_map.get(sort_by, "orderAmount")
        rows_with_value = [item for item in rows if item.get(sort_key) not in (None, "")]
        rows_without_value = [item for item in rows if item.get(sort_key) in (None, "")]
        rows_with_value.sort(
            key=lambda item: item.get(sort_key) or 0,
            reverse=str(sort_order).lower() != "asc",
        )
        rows = rows_with_value + rows_without_value
        for item in rows:
            for key, value in list(item.items()):
                if isinstance(value, float):
                    item[key] = round(value, 4)

        def total_of(field):
            return sum(_operating_number(item.get(field)) for item in rows)

        total_order_amount = total_of("orderAmount")
        total_promotion_revenue = total_of("promotionRevenue")
        total_promotion_spend = total_of("promotionSpend")
        summary = {
            "links": len(rows), "rows": sum(len(item.get("dailyRows", [])) for item in rows),
            "dataDays": len({daily.get("dataDate") for item in rows for daily in item.get("dailyRows", [])}),
            "firstDate": min((item.get("firstDate") for item in rows if item.get("firstDate")), default=""),
            "lastDate": max((item.get("lastDate") for item in rows if item.get("lastDate")), default=""),
            "orders": total_of("profitOrders"), "revenue": total_promotion_revenue,
            "spend": total_promotion_spend, "netRevenue": total_of("promotionNetRevenue"),
            "impressions": total_of("impressions"), "clicks": total_of("clicks"),
            "cost": total_of("goodsCost"), "shipping": total_of("shippingCost"),
            "grossProfit": total_of("grossProfit"), "promotion": total_of("profitPromotionFee"),
            "platformProfit": total_of("platformProfit"), "promotionOrders": total_of("promotionOrders"),
            "costPct": _operating_ratio(total_of("goodsCost"), total_order_amount),
            "shippingPct": _operating_ratio(total_of("shippingCost"), total_order_amount),
            "grossMargin": _operating_ratio(total_of("grossProfit"), total_order_amount),
            "promotionPct": _operating_ratio(total_of("profitPromotionFee"), total_order_amount),
            "profitRate": _operating_ratio(total_of("platformProfit"), total_order_amount),
            "roi": total_promotion_revenue / total_promotion_spend if total_promotion_spend else 0.0,
        }
        summary["links"] = len(rows)
        total = len(rows)
        offset = (page - 1) * size
        page_rows = rows[offset:offset + size]
        return sanitize_json({
            "success": True, "data": page_rows, "summary": summary, "total": total,
            "page": page, "size": size, "pages": (total + size - 1) // size if total else 0,
            "meta": {
                "source_tables": {"link_info": LINK_INFO_TABLE, "profit": TABLE_NAME, "promotion": PROMOTION_HOURLY_TABLE},
                "link_info_grain": "链接ID",
                "profit_grain": "链接ID + 负责人 + 数据日期",
                "promotion_grain": "商品ID + 店铺 + 数据日期 + 推广小时",
                "display_grain": "链接ID",
            },
        })
    finally:
        conn.close()

@app.get("/api/v3/link-summary")
def get_link_summary(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str = Query(default=""),
    start: str = Query(default=None),
    end: str = Query(default=None),
    link_ids: str = Query(default=None),
    product_code: str = Query(default=None),
    product_name: str = Query(default=None),
    brand: str = Query(default=None),
    store_name: str = Query(default=None),
    store_person: str = Query(default=None),
    creation_days: int = Query(default=None, ge=1, le=3650),
    creation_start: str = Query(default=None),
    creation_end: str = Query(default=None),
    sort_by: str = Query(default="revenue"),
    sort_order: str = Query(default="desc"),
):
    """按链接 ID 聚合指定日期范围内的数据，并重新计算所有比例字段。"""
    conn = get_mysql()
    try:
        where = ["`链接id` IS NOT NULL", "`链接id` <> ''"]
        params = []
        if search:
            where.append("(`链接id` LIKE %s OR `商品编码` LIKE %s OR `商品标题` LIKE %s OR `店铺名称` LIKE %s)")
            like = f"%{search}%"
            params.extend([like, like, like, like])
        if start:
            where.append("`数据日期` >= %s")
            params.append(start)
        if end:
            where.append("`数据日期` <= %s")
            params.append(end)
        if link_ids:
            ids = [item.strip() for item in link_ids.split(",") if item.strip()]
            if ids:
                placeholders = ",".join(["%s"] * len(ids))
                where.append(f"`链接id` IN ({placeholders})")
                params.extend(ids)
        if product_code:
            where.append("`商品编码` LIKE %s")
            params.append(f"%{product_code}%")
        if product_name:
            where.append("`商品标题` LIKE %s")
            params.append(f"%{product_name}%")
        _append_brand_filter(where, params, brand)
        if store_name:
            where.append("`店铺名称` LIKE %s")
            params.append(f"%{store_name}%")
        if store_person:
            where.append("`负责人` = %s")
            params.append(store_person)
        _append_creation_filter(where, params, creation_days, creation_start, creation_end, f"{TABLE_NAME}.`链接id`", conn)
        where_clause = " AND ".join(where)

        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(DISTINCT `链接id`) FROM {TABLE_NAME} WHERE {where_clause}", params)
        total = int(cur.fetchone()[0] or 0)

        cur.execute(
            f"SELECT COUNT(*) AS row_count, COUNT(DISTINCT `数据日期`) AS data_days, "
            f"MIN(`数据日期`) AS first_date, MAX(`数据日期`) AS last_date, "
            f"SUM(COALESCE(`单量`, 0)), SUM(COALESCE(`收入`, 0)) AS revenue, SUM(COALESCE(`成本`, 0)), "
            f"SUM(COALESCE(`快递`, 0)), SUM(COALESCE(`毛利`, 0)), SUM(COALESCE(`技术服务费`, 0)), "
            f"SUM(COALESCE(`预估售后`, 0)), SUM(COALESCE(`推广费`, 0)), SUM(COALESCE(`运费险`, 0)), "
            f"SUM(COALESCE(`税费`, 0)), SUM(COALESCE(`平台利润`, 0)) "
            f"FROM {TABLE_NAME} WHERE {where_clause}",
            params,
        )
        total_row = cur.fetchone()
        total_revenue = float(total_row[5] or 0)
        total_cost = float(total_row[6] or 0)
        total_shipping = float(total_row[7] or 0)
        total_gross_profit = float(total_row[8] or 0)
        total_promotion = float(total_row[11] or 0)
        total_platform_profit = float(total_row[14] or 0)
        summary = {
            "links": total,
            "rows": int(total_row[0] or 0),
            "dataDays": int(total_row[1] or 0),
            "firstDate": str(total_row[2])[:10] if total_row[2] else "",
            "lastDate": str(total_row[3])[:10] if total_row[3] else "",
            "orders": int(float(total_row[4] or 0)),
            "revenue": round(total_revenue, 2),
            "cost": round(total_cost, 2),
            "shipping": round(total_shipping, 2),
            "grossProfit": round(total_gross_profit, 2),
            "promotion": round(total_promotion, 2),
            "platformProfit": round(total_platform_profit, 2),
            "costPct": _summary_ratio(total_cost, total_revenue),
            "shippingPct": _summary_ratio(total_shipping, total_revenue),
            "grossMargin": _summary_ratio(total_gross_profit, total_revenue),
            "promotionPct": _summary_ratio(total_promotion, total_revenue),
            "profitRate": _summary_ratio(total_platform_profit, total_revenue),
        }

        sort_expressions = {
            "linkId": "`链接id`",
            "productCode": "MAX(`商品编码`)",
            "title": "MAX(`商品标题`)",
            "storeName": "MAX(`店铺名称`)",
            "brand": "MAX(`店铺名称`)",
            "person": "MAX(`负责人`)",
            "firstDate": "MIN(`数据日期`)",
            "lastDate": "MAX(`数据日期`)",
            "dataDays": "COUNT(DISTINCT `数据日期`)",
            "orders": "SUM(COALESCE(`单量`, 0))",
            "revenue": "SUM(COALESCE(`收入`, 0))",
            "cost": "SUM(COALESCE(`成本`, 0))",
            "costPct": "COALESCE(SUM(COALESCE(`成本`, 0)) / NULLIF(SUM(COALESCE(`收入`, 0)), 0), 0)",
            "shipping": "SUM(COALESCE(`快递`, 0))",
            "shippingPct": "COALESCE(SUM(COALESCE(`快递`, 0)) / NULLIF(SUM(COALESCE(`收入`, 0)), 0), 0)",
            "costShipping": "SUM(COALESCE(`成本`, 0)) + SUM(COALESCE(`快递`, 0))",
            "costShippingPct": "COALESCE((SUM(COALESCE(`成本`, 0)) + SUM(COALESCE(`快递`, 0))) / NULLIF(SUM(COALESCE(`收入`, 0)), 0), 0)",
            "grossProfit": "SUM(COALESCE(`毛利`, 0))",
            "grossMargin": "COALESCE(SUM(COALESCE(`毛利`, 0)) / NULLIF(SUM(COALESCE(`收入`, 0)), 0), 0)",
            "promotion": "SUM(COALESCE(`推广费`, 0))",
            "promotionPct": "COALESCE(SUM(COALESCE(`推广费`, 0)) / NULLIF(SUM(COALESCE(`收入`, 0)), 0), 0)",
            "platformProfit": "SUM(COALESCE(`平台利润`, 0))",
            "profitRate": "COALESCE(SUM(COALESCE(`平台利润`, 0)) / NULLIF(SUM(COALESCE(`收入`, 0)), 0), 0)",
        }
        sort_expression = sort_expressions.get(sort_by, sort_expressions["revenue"])
        sort_direction = "ASC" if str(sort_order).lower() == "asc" else "DESC"
        offset = (page - 1) * size
        cur.execute(
            f"SELECT `链接id`, MAX(`商品编码`), MAX(`商品标题`), MAX(`店铺名称`), MAX(`负责人`), "
            f"MIN(`数据日期`) AS first_date, MAX(`数据日期`) AS last_date, COUNT(DISTINCT `数据日期`) AS data_days, "
            f"SUM(COALESCE(`单量`, 0)), SUM(COALESCE(`收入`, 0)) AS revenue, SUM(COALESCE(`成本`, 0)), "
            f"SUM(COALESCE(`快递`, 0)), SUM(COALESCE(`毛利`, 0)), SUM(COALESCE(`技术服务费`, 0)), "
            f"SUM(COALESCE(`预估售后`, 0)), SUM(COALESCE(`推广费`, 0)), SUM(COALESCE(`运费险`, 0)), "
            f"SUM(COALESCE(`税费`, 0)), SUM(COALESCE(`平台利润`, 0)) "
            f"FROM {TABLE_NAME} WHERE {where_clause} "
            f"GROUP BY `链接id` ORDER BY {sort_expression} {sort_direction}, `链接id` ASC "
            f"LIMIT %s OFFSET %s",
            params + [size, offset],
        )
        rows = []
        for row in cur.fetchall():
            revenue = float(row[9] or 0)
            cost = float(row[10] or 0)
            shipping = float(row[11] or 0)
            gross_profit = float(row[12] or 0)
            promotion = float(row[15] or 0)
            platform_profit = float(row[18] or 0)
            rows.append({
                "linkId": str(row[0]),
                "productCode": row[1] or "",
                "title": row[2] or "",
                "storeName": row[3] or "",
                "brand": _link_summary_brand(row[3]),
                "person": row[4] or "",
                "firstDate": str(row[5])[:10] if row[5] else "",
                "lastDate": str(row[6])[:10] if row[6] else "",
                "dataDays": int(row[7] or 0),
                "orders": int(float(row[8] or 0)),
                "revenue": round(revenue, 2),
                "cost": round(cost, 2),
                "costPct": _summary_ratio(cost, revenue),
                "shipping": round(shipping, 2),
                "shippingPct": _summary_ratio(shipping, revenue),
                "costShipping": round(cost + shipping, 2),
                "costShippingPct": _summary_ratio(cost + shipping, revenue),
                "grossProfit": round(gross_profit, 2),
                "grossMargin": _summary_ratio(gross_profit, revenue),
                "techServiceFee": round(float(row[13] or 0), 2),
                "estimatedAfterSale": round(float(row[14] or 0), 2),
                "promotion": round(promotion, 2),
                "promotionPct": _summary_ratio(promotion, revenue),
                "freightInsurance": round(float(row[16] or 0), 2),
                "tax": round(float(row[17] or 0), 2),
                "platformProfit": round(platform_profit, 2),
                "profitRate": _summary_ratio(platform_profit, revenue),
            })

        return sanitize_json({
            "success": True,
            "data": rows,
            "summary": summary,
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size if total > 0 else 0,
        })
    finally:
        conn.close()

@app.get("/api/v3/link-dashboard")
def get_link_dashboard(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str = Query(default=""),
    start: str = Query(default=None),
    end: str = Query(default=None),
    store_person: str = Query(default=None),
    link_ids: str = Query(default=None),
    product_code: str = Query(default=None),
    product_name: str = Query(default=None),
    brand: str = Query(default=None),
    store_name: str = Query(default=None),
    creation_days: int = Query(default=None, ge=1, le=3650),
    creation_start: str = Query(default=None),
    creation_end: str = Query(default=None),
):
    """返回链接明细看板所需的透视数据和连续亏损预警。

    /api/v3/links 保留一行一日的高级明细表接口；本接口按链接聚合，
    将日期利润率透视成 rates，避免前端重新拉取或内嵌整份历史数据。
    """
    conn = get_mysql()
    try:
        where = ["`链接id` IS NOT NULL", "`链接id` <> ''"]
        params = []
        if search:
            where.append("(`链接id` LIKE %s OR `商品编码` LIKE %s OR `商品标题` LIKE %s OR `店铺名称` LIKE %s)")
            like = f"%{search}%"
            params.extend([like, like, like, like])
        if start:
            where.append("`数据日期` >= %s")
            params.append(start)
        if end:
            where.append("`数据日期` <= %s")
            params.append(end)
        if store_person:
            where.append("`负责人` = %s")
            params.append(store_person)
        if link_ids:
            ids = [item.strip() for item in link_ids.split(",") if item.strip()]
            if ids:
                placeholders = ",".join(["%s"] * len(ids))
                where.append(f"`链接id` IN ({placeholders})")
                params.extend(ids)
        if product_code:
            where.append("`商品编码` LIKE %s")
            params.append(f"%{product_code}%")
        if product_name:
            where.append("`商品标题` LIKE %s")
            params.append(f"%{product_name}%")
        _append_brand_filter(where, params, brand)
        if store_name:
            where.append("`店铺名称` LIKE %s")
            params.append(f"%{store_name}%")
        _append_creation_filter(where, params, creation_days, creation_start, creation_end, f"{TABLE_NAME}.`链接id`", conn)
        where_clause = " AND ".join(where)

        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(DISTINCT `链接id`) FROM {TABLE_NAME} WHERE {where_clause}", params)
        total = int(cur.fetchone()[0] or 0)

        cur.execute(
            f"SELECT DISTINCT `数据日期` FROM {TABLE_NAME} WHERE {where_clause} ORDER BY `数据日期`",
            params,
        )
        dates = [str(row[0])[:10] for row in cur.fetchall()]

        offset = (page - 1) * size
        cur.execute(
            f"SELECT `链接id`, MAX(`商品编码`), MAX(`商品标题`), MAX(`店铺名称`), "
            f"MAX(`负责人`), MAX(`数据日期`) AS latest_date, SUM(COALESCE(`收入`, 0)) AS revenue_sum "
            f"FROM {TABLE_NAME} WHERE {where_clause} "
            f"GROUP BY `链接id` ORDER BY latest_date DESC, revenue_sum DESC, `链接id` "
            f"LIMIT %s OFFSET %s",
            params + [size, offset],
        )
        page_rows = cur.fetchall()
        link_ids = [str(row[0]) for row in page_rows]

        def brand_of(store):
            store = str(store or "")
            if "浪奇" in store:
                return "浪奇"
            if "威王" in store or "VEWIN" in store.upper():
                return "威王"
            if "舒蕾" in store or "SLEK" in store.upper():
                return "舒蕾"
            return "白牌"

        page_data = {}
        if link_ids:
            placeholders = ",".join(["%s"] * len(link_ids))
            cur.execute(
                f"SELECT `链接id`, `商品编码`, `商品标题`, `店铺名称`, `负责人`, `数据日期`, `利润率` "
                f"FROM {TABLE_NAME} WHERE {where_clause} AND `链接id` IN ({placeholders}) "
                f"ORDER BY `链接id`, `数据日期`",
                params + link_ids,
            )
            for row in cur.fetchall():
                link_id = str(row[0])
                date = str(row[5])[:10]
                item = page_data.setdefault(link_id, {
                    "linkId": link_id,
                    "productCode": row[1] or "",
                    "title": row[2] or "",
                    "storeName": row[3] or "",
                    "person": row[4] or "",
                    "brand": brand_of(row[3]),
                    "rates": {},
                })
                rate = row[6]
                item["rates"][date] = round(float(rate), 6) if rate is not None else None

        # 预警按所有匹配链接计算，沿用原 HTML：只统计从最新日期开始连续为负的天数。
        cur.execute(
            f"SELECT `链接id`, `商品编码`, `店铺名称`, `数据日期`, `利润率` "
            f"FROM {TABLE_NAME} WHERE {where_clause} ORDER BY `链接id`, `数据日期`",
            params,
        )
        alert_rows = defaultdict(lambda: {"code": "", "store": "", "rates": {}})
        for row in cur.fetchall():
            link_id = str(row[0])
            entry = alert_rows[link_id]
            entry["code"] = row[1] or entry["code"]
            entry["store"] = row[2] or entry["store"]
            entry["rates"][str(row[3])[:10]] = row[4]

        alerts = {"a15": [], "a10": [], "a5": []}
        for link_id, entry in alert_rows.items():
            recent_negative_days = 0
            for date in reversed(dates):
                rate = entry["rates"].get(date)
                if rate is not None and float(rate) < 0:
                    recent_negative_days += 1
                else:
                    break
            alert = {"id": link_id, "code": entry["code"], "store": entry["store"], "days": recent_negative_days}
            if recent_negative_days >= 15:
                alerts["a15"].append(alert)
            elif recent_negative_days >= 10:
                alerts["a10"].append(alert)
            elif recent_negative_days >= 5:
                alerts["a5"].append(alert)
        for group in alerts.values():
            group.sort(key=lambda item: item["days"], reverse=True)

        return sanitize_json({
            "success": True,
            "data": [page_data[link_id] for link_id in link_ids if link_id in page_data],
            "dates": dates,
            "alerts": {key: value[:50] for key, value in alerts.items()},
            "alertCounts": {key: len(value) for key, value in alerts.items()},
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size if total > 0 else 0,
        })
    finally:
        conn.close()

@app.get("/api/v3/status")
def get_status():
    """系统状态"""
    conn = get_mysql()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*), MIN(数据日期), MAX(数据日期) FROM {TABLE_NAME}")
        row = cur.fetchone()
        db_info = {"rows": row[0], "min_date": str(row[1]) if row[1] else None, "max_date": str(row[2]) if row[2] else None}
        cur.execute(f"SELECT COUNT(*), MIN(data_date), MAX(data_date), COUNT(DISTINCT store_name), COUNT(DISTINCT product_id), COUNT(DISTINCT promotion_hour) FROM {PROMOTION_HOURLY_TABLE}")
        hourly = cur.fetchone()
        promotion_info = {
            "table": PROMOTION_HOURLY_TABLE,
            "rows": hourly[0],
            "min_date": str(hourly[1]) if hourly[1] else None,
            "max_date": str(hourly[2]) if hourly[2] else None,
            "stores": hourly[3],
            "products": hourly[4],
            "hours": hourly[5],
        }
    except Exception as e:
        db_info = {"error": str(e)}
        promotion_info = {"table": PROMOTION_HOURLY_TABLE, "error": str(e)}
    finally:
        conn.close()

    # 可用的 xlsx 文件
    xlsx_count = len(list_xlsx_files())

    return {
        "database": db_info,
        "promotion_hourly": promotion_info,
        "xlsx_files_available": xlsx_count,
        "server_time": datetime.now().isoformat()
    }

# ============ 管理中台目标值持久化 ============
@app.get("/api/v3/admin/targets")
def get_admin_targets(month: str = Query(default=None)):
    """读取目标值配置。month 为空则返回所有月份"""
    conn = get_mysql()
    try:
        cur = conn.cursor()
        if month:
            cur.execute("SELECT target_month, config_json FROM admin_targets WHERE target_month = %s", (month,))
        else:
            cur.execute("SELECT target_month, config_json FROM admin_targets ORDER BY target_month")
        rows = cur.fetchall()
        result = {}
        for r in rows:
            try:
                result[r[0]] = json.loads(r[1])
            except:
                result[r[0]] = {}
        return {"success": True, "data": result}
    finally:
        conn.close()

@app.post("/api/v3/admin/targets")
async def save_admin_targets(request: Request):
    """保存目标值配置。body: {month: '2026-07', config: {...}}"""
    data = await request.json()
    month = data.get("month", "")
    config = data.get("config", {})
    if not month:
        return {"error": "请提供 month 参数"}
    config_json = json.dumps(config, ensure_ascii=False)
    conn = get_mysql()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO admin_targets (target_month, config_json) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE config_json = VALUES(config_json)",
            (month, config_json)
        )
        conn.commit()
        return {"success": True, "message": f"已保存 {month} 目标值"}
    finally:
        conn.close()

# ============ 管理中台标准规则 ============
def _ensure_standards_table(cursor):
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS dashboard_standards ("
        "id INT AUTO_INCREMENT PRIMARY KEY, "
        "dimension_type VARCHAR(40) NOT NULL, "
        "brand VARCHAR(100) DEFAULT '', product_code VARCHAR(100) DEFAULT '', product_name VARCHAR(255) DEFAULT '', "
        "metric_key VARCHAR(80) NOT NULL, operator VARCHAR(20) NOT NULL DEFAULT 'gte', "
        "threshold_min DOUBLE NULL, threshold_max DOUBLE NULL, enabled TINYINT NOT NULL DEFAULT 1, "
        "note VARCHAR(255) DEFAULT '', filter_config LONGTEXT NULL, "
        "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, "
        "INDEX idx_standards_dimension (dimension_type), INDEX idx_standards_product (product_code)"
        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
    )
    cursor.execute(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = 'dashboard_standards' "
        "AND column_name = 'filter_config'"
    )
    if not cursor.fetchone()[0]:
        cursor.execute("ALTER TABLE dashboard_standards ADD COLUMN filter_config LONGTEXT NULL")


@app.get("/api/v3/admin/standards")
def get_admin_standards():
    """读取多维度运营标准；首次访问时安全创建配置表。"""
    conn = get_mysql()
    try:
        cur = conn.cursor()
        _ensure_standards_table(cur)
        conn.commit()
        cur.execute(
            "SELECT id, dimension_type, brand, product_code, product_name, metric_key, operator, "
            "threshold_min, threshold_max, enabled, note, filter_config, updated_at "
            "FROM dashboard_standards ORDER BY dimension_type, brand, product_code, id"
        )
        rows = []
        for row in cur.fetchall():
            try:
                filter_config = json.loads(row[11]) if row[11] else {}
            except (TypeError, json.JSONDecodeError):
                filter_config = {}
            rows.append({
                "id": row[0], "dimensionType": row[1], "brand": row[2] or "", "productCode": row[3] or "",
                "productName": row[4] or "", "metricKey": row[5], "operator": row[6],
                "thresholdMin": row[7], "thresholdMax": row[8], "enabled": bool(row[9]),
                "note": row[10] or "", "filterConfig": filter_config,
                "updatedAt": str(row[12]) if row[12] else "",
            })
        return {"success": True, "data": rows}
    finally:
        conn.close()


@app.post("/api/v3/admin/standards")
async def save_admin_standards(request: Request):
    """保存或删除一条标准规则。body action=save|delete。"""
    data = await request.json()
    action = str(data.get("action") or "save").lower()
    conn = get_mysql()
    try:
        cur = conn.cursor()
        _ensure_standards_table(cur)
        if action == "delete":
            standard_id = data.get("id")
            if not standard_id:
                return {"success": False, "error": "缺少标准 id"}
            cur.execute("DELETE FROM dashboard_standards WHERE id = %s", (standard_id,))
        else:
            standard = data.get("standard") or data
            values = (
                str(standard.get("dimensionType") or standard.get("dimension_type") or "brand"),
                str(standard.get("brand") or ""),
                str(standard.get("productCode") or standard.get("product_code") or ""),
                str(standard.get("productName") or standard.get("product_name") or ""),
                str(standard.get("metricKey") or standard.get("metric_key") or "profitRate"),
                str(standard.get("operator") or "gte"),
                standard.get("thresholdMin") if standard.get("thresholdMin") is not None else standard.get("threshold_min"),
                standard.get("thresholdMax") if standard.get("thresholdMax") is not None else standard.get("threshold_max"),
                1 if standard.get("enabled", True) else 0,
                str(standard.get("note") or ""),
                json.dumps(standard.get("filterConfig") or standard.get("filter_config") or {}, ensure_ascii=False),
            )
            standard_id = standard.get("id")
            if standard_id:
                cur.execute(
                    "UPDATE dashboard_standards SET dimension_type=%s, brand=%s, product_code=%s, product_name=%s, "
                    "metric_key=%s, operator=%s, threshold_min=%s, threshold_max=%s, enabled=%s, note=%s, filter_config=%s WHERE id=%s",
                    values + (standard_id,),
                )
            else:
                cur.execute(
                    "INSERT INTO dashboard_standards (dimension_type, brand, product_code, product_name, metric_key, operator, threshold_min, threshold_max, enabled, note, filter_config) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    values,
                )
        conn.commit()
        return {"success": True, "id": cur.lastrowid if action != "delete" else data.get("id")}
    finally:
        conn.close()

# ============ 用户认证与权限 ============
import hashlib

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

@app.post("/api/v3/auth/login")
async def auth_login(request: Request):
    data = await request.json()
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return {"success": False, "error": "用户名和密码不能为空"}
    conn = get_mysql()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, username, role, display_name FROM dashboard_users WHERE username=%s AND password_hash=%s",
                     (username, hash_password(password)))
        row = cur.fetchone()
        if row:
            return {"success": True, "user": {"id": row[0], "username": row[1], "role": row[2], "display_name": row[3] or row[1]}}
        return {"success": False, "error": "用户名或密码错误"}
    finally:
        conn.close()

@app.get("/api/v3/admin/users")
async def admin_list_users(request: Request):
    username = request.query_params.get("username", "")
    password = request.query_params.get("password", "")
    if not username or not password:
        return {"success": False, "error": "请提供认证信息"}
    conn = get_mysql()
    try:
        cur = conn.cursor()
        cur.execute("SELECT role FROM dashboard_users WHERE username=%s AND password_hash=%s",
                     (username, hash_password(password)))
        row = cur.fetchone()
        if not row or row[0] != "admin":
            return {"success": False, "error": "无权限"}
        cur.execute("SELECT id, username, password_plain, role, display_name, created_at FROM dashboard_users ORDER BY id")
        users = [{"id": r[0], "username": r[1], "password": r[2] or "", "role": r[3], "display_name": r[4], "created_at": str(r[5])} for r in cur.fetchall()]
        return {"success": True, "users": users}
    finally:
        conn.close()

@app.post("/api/v3/admin/users")
async def admin_save_user(request: Request):
    data = await request.json()
    username = data.get("auth_username", "")
    password = data.get("auth_password", "")
    if not username or not password:
        return {"success": False, "error": "请提供认证信息"}
    conn = get_mysql()
    try:
        cur = conn.cursor()
        cur.execute("SELECT role FROM dashboard_users WHERE username=%s AND password_hash=%s",
                     (username, password))
        row = cur.fetchone()
        if not row or row[0] != "admin":
            return {"success": False, "error": "无权限"}
        action = data.get("action", "add")
        if action == "add":
            nu = data.get("new_username", "").strip()
            np = data.get("new_password", "")
            nr = data.get("new_role", "user")
            nd = data.get("new_display", nu)
            if not nu or not np:
                return {"success": False, "error": "用户名和密码不能为空"}
            try:
                cur.execute("INSERT INTO dashboard_users (username, password_hash, role, display_name) VALUES (%s,%s,%s,%s)",
                             (nu, hash_password(np), nr, nd))
                conn.commit()
                return {"success": True, "message": f"已添加用户 {nu}"}
            except pymysql.IntegrityError:
                return {"success": False, "error": f"用户名 {nu} 已存在"}
        elif action == "update":
            uid = data.get("user_id")
            nr = data.get("new_role", "")
            nd = data.get("new_display", "")
            if not uid:
                return {"success": False, "error": "请指定用户"}
            parts = []; vals = []
            if nr: parts.append("role=%s"); vals.append(nr)
            if nd: parts.append("display_name=%s"); vals.append(nd)
            if parts:
                vals.append(uid)
                cur.execute(f"UPDATE dashboard_users SET {', '.join(parts)} WHERE id=%s", vals)
                conn.commit()
                return {"success": True, "message": "已更新"}
            return {"success": False, "error": "无更新内容"}
        elif action == "delete":
            uid = data.get("user_id")
            if not uid:
                return {"success": False, "error": "请指定用户"}
            cur.execute("DELETE FROM dashboard_users WHERE id=%s AND username!='admin'", (uid,))
            conn.commit()
            return {"success": True, "message": "已删除" if cur.rowcount else "无法删除（admin不可删除）"}
        elif action == "reset_pw":
            uid = data.get("user_id")
            np = data.get("new_password", "")
            if not uid or not np:
                return {"success": False, "error": "请指定用户和新密码"}
            cur.execute("UPDATE dashboard_users SET password_hash=%s, password_hash=%s WHERE id=%s", (hash_password(np), uid))
            conn.commit()
            return {"success": True, "message": "密码已重置"}
    finally:
        conn.close()

# ============ 数据聚合 ============
def sanitize_json(obj):
    """递归清理 NaN/Inf，确保 JSON 可序列化"""
    if isinstance(obj, dict):
        return {k: sanitize_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_json(v) for v in obj]
    elif isinstance(obj, float):
        if pd.isna(obj) or np.isinf(obj):
            return 0.0
        return obj
    return obj

def aggregate_dashboard_data(df):
    """从明细 DataFrame 聚合出看板需要的所有数据"""
    # === 全局汇总 grand ===
    grand = {
        "orders": int(df["单量"].sum()),
        "revenue": round(float(df["收入"].sum()), 2),
        "cost": round(float(df["成本"].sum()), 2),
        "shipping": round(float(df["快递"].sum()), 2),
        "gross_profit": round(float(df["毛利"].sum()), 2),
        "promotion": round(float(df["推广费"].sum()), 2),
        "platform_profit": round(float(df["平台利润"].sum()), 2),
        "stores": int(df["店铺名称"].nunique()),
    }
    grand["gross_margin"] = round(grand["gross_profit"] / grand["revenue"] * 100, 1) if grand["revenue"] > 0 else 0
    grand["profit_rate"] = round(grand["platform_profit"] / grand["revenue"] * 100, 1) if grand["revenue"] > 0 else 0

    # === 负责人汇总 ===
    person = df.groupby("负责人").agg(
        revenue=("收入", "sum"), cost=("成本", "sum"), shipping=("快递", "sum"),
        promotion=("推广费", "sum"), platform_profit=("平台利润", "sum"),
        orders=("单量", "sum"), stores=("店铺名称", "nunique")
    ).reset_index()
    person = person[person["负责人"].notna() & (person["负责人"] != "")]
    person["gross_profit"] = person["revenue"] - person["cost"] - person["shipping"]
    person["gross_margin"] = (person["gross_profit"] / person["revenue"] * 100).round(1)
    person["promotion_pct"] = (person["promotion"] / person["revenue"] * 100).round(1)
    person["profit_rate"] = (person["platform_profit"] / person["revenue"] * 100).round(1)
    person = person.rename(columns={"负责人": "name"})
    people_summary = person.sort_values("revenue", ascending=False).to_dict("records")

    # === 商品汇总 ===
    prod = df.groupby("商品编码").agg(
        revenue=("收入", "sum"), cost=("成本", "sum"), shipping=("快递", "sum"),
        promotion=("推广费", "sum"), platform_profit=("平台利润", "sum"),
        orders=("单量", "sum"), name=("商品标题", "first")
    ).reset_index()
    prod = prod[prod["商品编码"].notna() & (prod["商品编码"] != "")]
    prod["cost_pct"] = (prod["cost"] / prod["revenue"] * 100).round(1)
    prod["shipping_pct"] = (prod["shipping"] / prod["revenue"] * 100).round(1)
    prod["gross_profit"] = prod["revenue"] - prod["cost"] - prod["shipping"]
    prod["gross_margin"] = (prod["gross_profit"] / prod["revenue"] * 100).round(1)
    prod["promotion_pct"] = (prod["promotion"] / prod["revenue"] * 100).round(1)
    prod["profit_rate"] = (prod["platform_profit"] / prod["revenue"] * 100).round(1)
    prod = prod.rename(columns={"商品编码": "code"})
    products = prod.sort_values("revenue", ascending=False).to_dict("records")

    # === 店铺汇总 ===
    store = df.groupby(["店铺名称", "负责人"]).agg(
        revenue=("收入", "sum"), cost=("成本", "sum"), shipping=("快递", "sum"),
        promotion=("推广费", "sum"), platform_profit=("平台利润", "sum"),
        orders=("单量", "sum"),
    ).reset_index()
    store = store[store["店铺名称"].notna() & (store["店铺名称"] != "")]
    store["cost_pct"] = (store["cost"] / store["revenue"] * 100).round(1)
    store["shipping_pct"] = (store["shipping"] / store["revenue"] * 100).round(1)
    store["gross_profit"] = store["revenue"] - store["cost"] - store["shipping"]
    store["gross_margin"] = (store["gross_profit"] / store["revenue"] * 100).round(1)
    store["promotion_pct"] = (store["promotion"] / store["revenue"] * 100).round(1)
    store["profit_rate"] = (store["platform_profit"] / store["revenue"] * 100).round(1)
    store = store.rename(columns={"店铺名称": "store", "负责人": "person"})
    all_stores = store.sort_values("revenue", ascending=False).to_dict("records")

    # === 每日趋势 ===
    daily = df.groupby("数据日期").agg(
        revenue=("收入", "sum"), cost=("成本", "sum"), shipping=("快递", "sum"),
        promotion=("推广费", "sum"), profit=("平台利润", "sum"), orders=("单量", "sum"),
    ).reset_index()
    daily["profit_rate"] = (daily["profit"] / daily["revenue"] * 100).round(2)
    daily = daily.rename(columns={"数据日期": "date"})
    daily_overall = daily.sort_values("date").to_dict("records")

    # === 每日×人 ===
    dp = df.groupby(["数据日期", "负责人"]).agg(
        revenue=("收入", "sum"), cost=("成本", "sum"), shipping=("快递", "sum"),
        promotion=("推广费", "sum"), profit=("平台利润", "sum"), orders=("单量", "sum"),
    ).reset_index()
    dp["profit_rate"] = (dp["profit"] / dp["revenue"] * 100).round(2)
    daily_by_person = {}
    for _, r in dp.iterrows():
        d = str(r["数据日期"])[:10]
        daily_by_person.setdefault(d, {})[str(r["负责人"])] = {
            "revenue": round(float(r["revenue"]), 2), "cost": round(float(r["cost"]), 2),
            "shipping": round(float(r["shipping"]), 2), "promotion": round(float(r["promotion"]), 2),
            "profit": round(float(r["profit"]), 2), "orders": int(r["orders"]),
            "profit_rate": round(float(r["profit_rate"]), 2),
        }

    # === 每日×商品 ===
    dpr = df.groupby(["数据日期", "商品编码"]).agg(
        revenue=("收入", "sum"), profit=("平台利润", "sum"),
    ).reset_index()
    daily_by_product = {}
    for _, r in dpr.iterrows():
        daily_by_product.setdefault(str(r["数据日期"])[:10], {})[str(r["商品编码"])] = {
            "revenue": round(float(r["revenue"]), 2), "profit": round(float(r["profit"]), 2),
        }

    # === 每日×店铺 ===
    dst = df.groupby(["数据日期", "店铺名称"]).agg(
        revenue=("收入", "sum"), cost=("成本", "sum"), shipping=("快递", "sum"), promotion=("推广费", "sum"), orders=("单量", "sum"), profit=("平台利润", "sum"),
    ).reset_index()
    daily_by_store = {}
    for _, r in dst.iterrows():
        daily_by_store.setdefault(str(r["数据日期"])[:10], {})[str(r["店铺名称"])] = {
            "revenue": round(float(r["revenue"]), 2),
            "cost": round(float(r["cost"]), 2),
            "shipping": round(float(r["shipping"]), 2),
            "promotion": round(float(r["promotion"]), 2),
            "orders": int(r["orders"]),
            "profit": round(float(r["profit"]), 2),
        }

    result = {
        "grand": grand,
        "peopleSummary": people_summary,
        "products": products,
        "allStores": all_stores,
        "dailyOverall": daily_overall,
        "dailyByPerson": daily_by_person,
        "dailyByProduct": daily_by_product,
        "dailyByStore": daily_by_store,
    }
    return sanitize_json(result)

# ============ 后台调度 ============
def etl_scheduler():
    """每小时自动运行 ETL"""
    while True:
        time.sleep(ETL_INTERVAL)
        try:
            run_etl()
        except Exception as e:
            print(f"⏰ 定时 ETL 失败: {e}")

# ============ 启动 ============
if __name__ == "__main__":
    LOCAL_CACHE.mkdir(parents=True, exist_ok=True)
    print("=" * 60)
    print("📊 利润率看板 V3 — 数据管道")
    print(f"   ETL: {NETWORK_BASE} → MySQL {TABLE_NAME}")
    print(f"   API: http://0.0.0.0:{API_PORT}")
    print("=" * 60)
    
    # 检查是否已有数据，跳过重复ETL
    try:
        conn = get_mysql()
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        existing = cur.fetchone()[0]
        conn.close()
        if existing > 0:
            print(f"\n✅ 已有 {existing} 行数据，跳过首次 ETL")
        else:
            print("\n▶ 首次 ETL 数据加载...")
            run_etl()
    except:
        print("\n▶ 首次 ETL 数据加载...")
        run_etl()

    # 后台定时任务
    t = threading.Thread(target=etl_scheduler, daemon=True)
    t.start()
    print(f"⏰ 定时 ETL 已启动 (每 {ETL_INTERVAL//3600} 小时)\n")

    # 挂载静态文件目录
    static_dir = Path(__file__).parent
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    @app.get("/profit-dashboard-v3")
    @app.get("/v3")
    async def serve_v3():
        return FileResponse(str(static_dir / "profit-dashboard-v3.html"))
    
    uvicorn.run(app, host="0.0.0.0", port=API_PORT, log_level="info")
