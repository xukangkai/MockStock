#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股全自动智能交易系统
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
你只需要设定初始金额，其余全部由系统自主完成：
- 自动扫描A股全市场选股
- 自动技术分析决策买卖
- 自动仓位管理和风险控制
- 自动止盈止损
- Web界面仅用于查看运行状态
"""
import json
import math
import os
import random
import threading
import time
import traceback
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone, time as dtime

# 加载 .env 文件（如果存在）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv 未安装时忽略，使用环境变量或 config.json

BEIJING_TZ = timezone(timedelta(hours=8))

def beijing_now() -> datetime:
    """获取北京时间"""
    return datetime.now(tz=BEIJING_TZ)

def is_trading_hours() -> bool:
    """判断当前是否在A股交易时间内（工作日 9:30-11:30, 13:00-15:00）"""
    now = beijing_now()
    if now.weekday() >= 5:  # 周末
        return False
    t = now.time()
    return (dtime(9, 30) <= t <= dtime(11, 30)) or (dtime(13, 0) <= t <= dtime(15, 0))

# /api/picks 缓存：避免频繁调用 AI
_picks_cache = {"data": [], "time": None}
PICKS_CACHE_TTL = 300  # 缓存有效期 5 分钟
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict

import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from langgraph.graph import END, StateGraph
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, Integer,
                         String, Text, create_engine, func)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# ── 数据库配置 ──────────────────────────────────────
APP_DIR = Path.home() / ".a_share_sim_trader_web"
APP_DIR.mkdir(parents=True, exist_ok=True)

DB_TYPE = os.environ.get("DB_TYPE", "sqlite").lower()

if DB_TYPE == "mysql":
    DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.environ.get("DB_PORT", "3306"))
    DB_USER = os.environ.get("DB_USER", "root")
    DB_PASS = os.environ.get("DB_PASS", "")
    DB_NAME = os.environ.get("DB_NAME", "sim_trader")
    DB_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

    import sqlalchemy as sa
    try:
        temp_engine = sa.create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}?charset=utf8mb4")
        with temp_engine.connect() as conn:
            conn.execute(sa.text(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` DEFAULT CHARACTER SET utf8mb4"))
            conn.commit()
        temp_engine.dispose()
    except Exception:
        pass
else:
    # SQLite（默认，零配置）
    DB_URL = f"sqlite:///{APP_DIR / 'trader.db'}"

LOT_SIZE = 100
COMMISSION_RATE = 0.0003
MIN_COMMISSION = 5.0
STAMP_TAX_RATE = 0.0005
TRANSFER_RATE = 0.00001
_trade_lock = threading.Lock()  # 防止并发买入/卖出

# ═════════════════════════════════════════════════════
#  主流ETF池（适合1万元小资金配置）
# ═════════════════════════════════════════════════════
MAINSTREAM_ETFS = {
    # 大盘指数ETF
    "510300": "沪深300ETF",
    "510500": "中证500ETF",
    "510050": "上证50ETF",
    "159919": "沪深300ETF",
    "159915": "创业板ETF",
    "512100": "中证1000ETF",
    # 行业ETF
    "512880": "证券ETF",
    "512690": "酒ETF",
    "512010": "医药ETF",
    "512480": "半导体ETF",
    "515790": "光伏ETF",
    "516160": "新能源ETF",
    "159869": "游戏ETF",
    "515030": "新能源车ETF",
    "515880": "通信ETF",
    # 跨境ETF
    "159941": "纳指ETF",
    "513100": "纳斯达克100",
    "159920": "恒生ETF",
    "513050": "中概互联ETF",
}

def is_etf_code(symbol: str) -> bool:
    """判断是否为ETF代码"""
    return symbol in MAINSTREAM_ETFS or symbol.startswith(("510", "511", "512", "513", "515", "516", "159"))

engine = create_engine(DB_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ═════════════════════════════════════════════════════
#  实时日志系统
# ═════════════════════════════════════════════════════
import collections
_realtime_logs = collections.deque(maxlen=200)  # 最多保存200条日志
_log_lock = threading.Lock()

def add_realtime_log(level: str, message: str, detail: str = ""):
    """添加实时日志"""
    with _log_lock:
        log_entry = {
            "time": beijing_now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,  # info, warning, error, success, ai
            "message": message,
            "detail": detail[:500] if detail else "",
        }
        _realtime_logs.appendleft(log_entry)
        # 同时打印到控制台
        print(f"[{level.upper()}] {message}")

# ═════════════════════════════════════════════════════
#  数据库模型
# ═════════════════════════════════════════════════════
class AccountModel(Base):
    __tablename__ = "account"
    id = Column(Integer, primary_key=True, autoincrement=True)
    initial_cash = Column(Float, nullable=False, default=100000.0)
    cash = Column(Float, nullable=False, default=100000.0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class PositionModel(Base):
    __tablename__ = "positions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(16), nullable=False, index=True)
    name = Column(String(64), default="")
    qty = Column(Integer, default=0)
    avg_cost = Column(Float, default=0.0)
    last_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    buy_reason = Column(String(128), default="")
    score = Column(Float, default=0.0)
    kind = Column(String(16), default="stock")  # stock or etf
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class LotModel(Base):
    __tablename__ = "lots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(16), nullable=False, index=True)
    buy_date = Column(Date, nullable=False)
    qty = Column(Integer, nullable=False)
    remaining = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    stop = Column(Float, nullable=True)

class TradeModel(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime, default=datetime.now)
    side = Column(String(8), nullable=False)
    symbol = Column(String(16), nullable=False)
    name = Column(String(64), default="")
    qty = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    gross = Column(Float, default=0.0)
    fee = Column(Float, default=0.0)
    cash_after = Column(Float, default=0.0)
    reason = Column(Text, default="")
    realized_pnl = Column(Float, nullable=True)
    is_auto = Column(Boolean, default=True)

class EquitySnapshotModel(Base):
    __tablename__ = "equity_snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime, default=datetime.now)
    cash = Column(Float, nullable=False)
    equity = Column(Float, nullable=False)
    note = Column(String(128), default="")

class DecisionLogModel(Base):
    __tablename__ = "decision_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime, default=datetime.now)
    action = Column(String(32), nullable=False)  # buy / sell / hold / scan
    symbol = Column(String(16), default="")
    name = Column(String(64), default="")
    price = Column(Float, nullable=True)
    score = Column(Float, nullable=True)
    reason = Column(Text, default="")
    detail = Column(Text, default="")

class AgentCycleLogModel(Base):
    __tablename__ = "agent_cycle_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cycle_id = Column(String(64), unique=True, index=True, nullable=False)
    time = Column(DateTime, default=datetime.now, index=True)
    status = Column(String(16), default="success")
    duration_ms = Column(Integer, default=0)
    risk_level = Column(String(16), default="mid")
    summary = Column(Text, default="")
    triggered_trade = Column(Boolean, default=False)
    plan_json = Column(Text, default="{}")

class AgentNodeLogModel(Base):
    __tablename__ = "agent_node_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cycle_id = Column(String(64), index=True, nullable=False)
    node_name = Column(String(64), index=True, nullable=False)
    time = Column(DateTime, default=datetime.now, index=True)
    duration_ms = Column(Integer, default=0)
    model_name = Column(String(128), default="")
    tool_calls = Column(Text, default="[]")
    input_summary = Column(Text, default="")
    output_summary = Column(Text, default="")

class AgentMemoryModel(Base):
    __tablename__ = "agent_memories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    memory_type = Column(String(32), index=True, nullable=False)
    memory_date = Column(DateTime, default=datetime.now, index=True)
    tags = Column(String(255), default="")
    content_json = Column(Text, default="{}")
    relevance_score = Column(Float, default=0.0)

class AgentFeedbackModel(Base):
    __tablename__ = "agent_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cycle_id = Column(String(64), index=True, nullable=False)
    symbol = Column(String(16), index=True, nullable=False)
    action_type = Column(String(16), nullable=False)
    feedback_date = Column(DateTime, default=datetime.now, index=True)
    horizon_1d = Column(Float, default=0.0)
    horizon_3d = Column(Float, default=0.0)
    horizon_5d = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    outcome_label = Column(String(32), default="pending")
    notes = Column(Text, default="")

Base.metadata.create_all(bind=engine)

# 尝试补齐旧表字段（保护本地 MySQL 历史数据，不自动删表）
try:
    from sqlalchemy import inspect
    inspector = inspect(engine)
    pos_cols = [c['name'] for c in inspector.get_columns('positions')]
    alter_sql = []
    if 'score' not in pos_cols:
        alter_sql.append("ALTER TABLE positions ADD COLUMN score FLOAT DEFAULT 0")
    if 'buy_reason' not in pos_cols:
        alter_sql.append("ALTER TABLE positions ADD COLUMN buy_reason VARCHAR(128) DEFAULT ''")
    if alter_sql:
        print("[数据库] 检测到旧表缺少字段，正在安全补齐...")
        with engine.begin() as conn:
            for sql in alter_sql:
                conn.execute(sa.text(sql))
        print("[数据库] 表字段已补齐，历史数据已保留")
except Exception as e:
    print(f"[数据库] 旧表字段检查跳过: {e}")

# ═════════════════════════════════════════════════════
#  工具函数
# ═════════════════════════════════════════════════════
def money(x: float) -> str:
    return f"¥{x:,.2f}"

def now_str() -> str:
    return beijing_now().strftime("%Y-%m-%d %H:%M:%S")

def today_str() -> str:
    return beijing_now().date().isoformat()

def round_lot(qty: int) -> int:
    return max(0, int(qty // LOT_SIZE * LOT_SIZE))

def normalize_symbol(s: str) -> str:
    return s.strip().upper().replace(".SH", "").replace(".SZ", "")

def fee_for_trade(amount: float, side: str, is_etf: bool = False) -> float:
    """计算交易手续费，ETF免印花税"""
    commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
    transfer = amount * TRANSFER_RATE
    # ETF卖出免印花税
    stamp = 0.0 if is_etf else (amount * STAMP_TAX_RATE if side == "sell" else 0.0)
    return round(commission + transfer + stamp, 2)

# ═════════════════════════════════════════════════════
#  行情获取（新浪财经API，稳定可靠）
# ═════════════════════════════════════════════════════

def _symbol_to_sina(code: str) -> str:
    """股票代码转新浪格式: 600519 -> sh600519, 000001 -> sz000001"""
    code = code.zfill(6)
    if code.startswith(('6', '9', '5')):
        return f"sh{code}"
    return f"sz{code}"

def _parse_sina_line(sina_code: str, data_str: str) -> Optional[Dict]:
    """解析新浪行情数据行"""
    if not data_str:
        return None
    fields = data_str.split(',')
    if len(fields) < 10:
        return None
    try:
        name = fields[0]
        open_price = float(fields[1] or 0)
        pre_close = float(fields[2] or 0)
        price = float(fields[3] or 0)
        high = float(fields[4] or 0)
        low = float(fields[5] or 0)
        volume = float(fields[8] or 0)
        amount = float(fields[9] or 0)
        if price <= 0 or pre_close <= 0:
            return None
        change_pct = round((price - pre_close) / pre_close * 100, 2)
        code = sina_code[2:]
        return {
            "symbol": code, "name": name, "price": price,
            "pct": change_pct, "high": high, "low": low,
            "open": open_price, "pre_close": pre_close,
            "volume": volume, "amount": amount,
            "change_pct": change_pct, "turnover": 0,
        }
    except (ValueError, IndexError):
        return None

def _fetch_sina_batch(sina_codes: List[str]) -> Dict[str, Dict]:
    """批量获取新浪行情，返回 {sina_code: quote_dict}"""
    import urllib.request
    sina_headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': 'https://finance.sina.com.cn/',
    }
    codes_str = ','.join(sina_codes)
    url = f'https://hq.sinajs.cn/list={codes_str}'
    req = urllib.request.Request(url, headers=sina_headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode('gbk')
        result = {}
        for line in raw.strip().split('\n'):
            if '=' not in line:
                continue
            var_part, data_part = line.split('=', 1)
            sina_code = var_part.split('_')[-1]
            data_str = data_part.strip().strip(';').strip('"')
            quote = _parse_sina_line(sina_code, data_str)
            if quote:
                result[sina_code] = quote
        return result
    except Exception:
        return {}

# 股票代码列表缓存（1小时刷新）
_stock_code_cache: Dict[str, Any] = {"data": None, "time": 0}
_STOCK_CODE_CACHE_TTL = 3600

def _get_all_stock_codes() -> List[Tuple[str, str]]:
    """获取全部A股代码列表 [(code, name), ...]，带缓存"""
    now = time.time()
    if _stock_code_cache["data"] is not None and (now - _stock_code_cache["time"]) < _STOCK_CODE_CACHE_TTL:
        return _stock_code_cache["data"]
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        if df is not None and not df.empty:
            codes = [(str(row["code"]).zfill(6), str(row["name"])) for _, row in df.iterrows()]
            _stock_code_cache["data"] = codes
            _stock_code_cache["time"] = now
            return codes
    except Exception:
        pass
    return _stock_code_cache["data"] or []

def fetch_quote(symbol: str) -> Optional[Dict[str, Any]]:
    """获取单个股票/ETF实时行情（新浪财经API）"""
    symbol = normalize_symbol(symbol)
    sina_code = _symbol_to_sina(symbol)
    for attempt in range(3):
        try:
            result = _fetch_sina_batch([sina_code])
            if sina_code in result:
                return result[sina_code]
            return None
        except Exception:
            time.sleep(0.5)
            continue
    return None

def fetch_all_stocks() -> List[Dict[str, Any]]:
    """获取全市场A股行情（新浪财经批量API，多线程并发）+ 主流ETF"""
    codes = _get_all_stock_codes()
    if not codes:
        return []
    sina_codes = [_symbol_to_sina(code) for code, _ in codes]
    BATCH_SIZE = 500
    batches = [sina_codes[i:i + BATCH_SIZE] for i in range(0, len(sina_codes), BATCH_SIZE)]

    def _fetch_one_batch(batch):
        try:
            return _fetch_sina_batch(batch)
        except Exception:
            return {}

    from concurrent.futures import ThreadPoolExecutor, as_completed
    all_stocks = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_fetch_one_batch, b): b for b in batches}
        for future in as_completed(futures):
            result = future.result()
            for sina_code, quote in result.items():
                name = quote.get("name", "")
                if name.startswith("*") or name.startswith("ST") or name.startswith("N") or name.startswith("C"):
                    continue
                if quote.get("amount", 0) < 10000000:
                    continue
                if quote.get("price", 0) <= 0:
                    continue
                all_stocks.append(quote)

    # 财务排雷：过滤亏损股和营收暴雷股
    try:
        fin_data = fetch_financial_batch()
        if fin_data:
            blacklist = financial_screen(fin_data)
            before = len(all_stocks)
            all_stocks = [s for s in all_stocks if s["symbol"] not in blacklist]
            filtered = before - len(all_stocks)
            if filtered > 0:
                add_realtime_log("info", f"📊 财务排雷：过滤 {filtered} 只问题股票（亏损/营收暴雷）")
    except Exception as e:
        add_realtime_log("warning", f"⚠️ 财务排雷跳过: {e}")

    # 添加主流ETF行情
    for symbol, name in MAINSTREAM_ETFS.items():
        try:
            quote = fetch_quote(symbol)
            if quote and quote.get("price", 0) > 0:
                quote["name"] = name
                quote["is_etf"] = True
                all_stocks.append(quote)
        except Exception:
            continue

    return all_stocks

def fetch_history(symbol: str, days: int = 60) -> Optional[List[Dict]]:
    """获取历史K线数据用于技术分析，支持股票和ETF"""
    symbol = normalize_symbol(symbol)
    try:
        import akshare as ak

        # 根据是否为ETF选择不同的接口
        if is_etf_code(symbol):
            df = ak.fund_etf_hist_em(symbol=symbol, period="daily", start_date=(date.today() - timedelta(days=days+10)).strftime("%Y%m%d"), adjust="qfq")
        else:
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=(date.today() - timedelta(days=days+10)).strftime("%Y%m%d"), adjust="qfq")

        if df is None or df.empty:
            return None
        records = []
        for _, row in df.iterrows():
            records.append({
                "date": str(row.iloc[0]),
                "open": float(row.get("开盘", row.iloc[1])),
                "close": float(row.get("收盘", row.iloc[2])),
                "high": float(row.get("最高", row.iloc[3])),
                "low": float(row.get("最低", row.iloc[4])),
                "volume": float(row.get("成交量", row.iloc[5])),
                "amount": float(row.get("成交额", row.iloc[6])),
                "change_pct": float(row.get("涨跌幅", 0) or 0),
            })
        return records[-days:]
    except Exception:
        return None

def fetch_market_news() -> List[Dict]:
    """获取最新财经新闻用于AI决策"""
    try:
        import akshare as ak
        news_list = []
        # 1. 全球财经新闻
        try:
            df = ak.stock_info_global_cls()
            if df is not None and not df.empty:
                for _, row in df.head(10).iterrows():
                    news_list.append({
                        "source": "global",
                        "title": str(row.get("标题", row.get("title", "")))[:200],
                        "time": str(row.get("发布时间", row.get("time", "")))[:20],
                        "content": str(row.get("摘要", row.get("content", "")))[:500],
                    })
        except Exception:
            pass

        # 2. 百度热点财经
        try:
            df = ak.news_economic_baidu()
            if df is not None and not df.empty:
                for _, row in df.head(5).iterrows():
                    news_list.append({
                        "source": "baidu",
                        "title": str(row.get("标题", ""))[:200],
                        "time": str(row.get("时间", ""))[:20],
                        "content": str(row.get("内容", row.get("摘要", "")))[:500],
                    })
        except Exception:
            pass

        return news_list[:15]
    except Exception:
        return []

# ═════════════════════════════════════════════════════
#  基本面财务数据获取与排雷
# ═════════════════════════════════════════════════════

def _safe_float(val) -> Optional[float]:
    """安全转换为float，None/空字符串/异常返回None"""
    if val is None or val == "" or val == "-":
        return None
    try:
        v = float(val)
        return v if not math.isnan(v) and not math.isinf(v) else None
    except (ValueError, TypeError):
        return None

# 财务数据缓存（6小时刷新，财报数据变化频率低）
_financial_cache: Dict[str, Any] = {"data": None, "time": 0}
_FINANCIAL_CACHE_TTL = 21600  # 6小时

def fetch_financial_batch() -> Dict[str, Dict]:
    """批量获取全市场业绩报表，返回 {symbol: {eps, net_profit, net_profit_yoy, revenue, revenue_yoy}}"""
    now = time.time()
    if _financial_cache["data"] is not None and (now - _financial_cache["time"]) < _FINANCIAL_CACHE_TTL:
        return _financial_cache["data"]

    result: Dict[str, Dict] = {}
    try:
        import akshare as ak
        add_realtime_log("info", "📊 正在获取全市场业绩报表...")
        df = ak.stock_yjbb_em(date="")  # 空字符串=最新季度
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                code = str(row.get("代码", "")).zfill(6)
                result[code] = {
                    "eps": _safe_float(row.get("每股收益")),
                    "net_profit": _safe_float(row.get("净利润-净利润")),
                    "net_profit_yoy": _safe_float(row.get("净利润-同比增长")),
                    "revenue": _safe_float(row.get("营业收入-营业收入")),
                    "revenue_yoy": _safe_float(row.get("营业收入-同比增长")),
                }
            add_realtime_log("success", f"✅ 业绩报表获取完成，共 {len(result)} 只股票")
        else:
            add_realtime_log("warning", "⚠️ 业绩报表返回空数据")
    except Exception as e:
        add_realtime_log("warning", f"⚠️ 业绩报表获取失败: {e}")

    _financial_cache["data"] = result
    _financial_cache["time"] = now
    return result

def fetch_valuation(symbol: str) -> Optional[Dict]:
    """获取单只股票的PE/PB等估值指标（akshare 乐咕乐股）"""
    symbol = normalize_symbol(symbol)
    try:
        import akshare as ak
        df = ak.stock_a_indicator_lg(symbol=symbol)
        if df is None or df.empty:
            return None
        latest = df.iloc[-1]
        return {
            "pe": _safe_float(latest.get("pe")),
            "pe_ttm": _safe_float(latest.get("pe_ttm")),
            "pb": _safe_float(latest.get("pb")),
            "ps_ttm": _safe_float(latest.get("ps_ttm")),
            "dv_ttm": _safe_float(latest.get("dv_ttm")),
            "total_mv": _safe_float(latest.get("total_mv")),
        }
    except Exception:
        return None

def financial_screen(financial_data: Dict[str, Dict]) -> set:
    """宽松排雷：返回应该被排除的股票代码集合
    规则：1.净利润为负（亏损股） 2.营收同比下滑超过50%（业绩暴雷）
    """
    blacklist = set()
    for code, fin in financial_data.items():
        # 规则1: 亏损
        if fin.get("net_profit") is not None and fin["net_profit"] < 0:
            blacklist.add(code)
            continue
        # 规则2: 营收腰斩
        if fin.get("revenue_yoy") is not None and fin["revenue_yoy"] < -50:
            blacklist.add(code)
            continue
    return blacklist

# ═════════════════════════════════════════════════════
#  量化技术指标计算
# ═════════════════════════════════════════════════════
import numpy as np

def calculate_indicators(history: List[Dict]) -> Dict:
    """计算技术指标：MA/MACD/RSI/KDJ/布林带/动量"""
    if not history or len(history) < 20:
        return {}

    closes = [h["close"] for h in history]
    highs = [h["high"] for h in history]
    lows = [h["low"] for h in history]
    volumes = [h["volume"] for h in history]

    indicators = {}

    # 1. 均线系统
    indicators["ma5"] = round(float(np.mean(closes[-5:])), 3)
    indicators["ma10"] = round(float(np.mean(closes[-10:])), 3)
    indicators["ma20"] = round(float(np.mean(closes[-20:])), 3)

    # 2. MACD
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    dif = ema12 - ema26
    dea = _ema([dif], 9)
    indicators["macd_dif"] = round(dif, 3)
    indicators["macd_dea"] = round(dea, 3)
    indicators["macd_hist"] = round((dif - dea) * 2, 3)

    # 3. RSI
    indicators["rsi6"] = _rsi(closes, 6)
    indicators["rsi14"] = _rsi(closes, 14)

    # 4. KDJ
    k, d, j = _kdj(closes, highs, lows)
    indicators["kdj_k"] = k
    indicators["kdj_d"] = d
    indicators["kdj_j"] = j

    # 5. 布林带
    upper, mid, lower = _boll(closes)
    indicators["boll_upper"] = upper
    indicators["boll_mid"] = mid
    indicators["boll_lower"] = lower

    # 6. 成交量指标
    avg_vol_5 = float(np.mean(volumes[-5:]))
    indicators["vol_ratio"] = round(volumes[-1] / avg_vol_5, 2) if avg_vol_5 > 0 else 1.0

    # 7. 动量指标
    indicators["momentum_5d"] = round((closes[-1] / closes[-6] - 1) * 100, 2) if len(closes) >= 6 else 0
    indicators["momentum_10d"] = round((closes[-1] / closes[-11] - 1) * 100, 2) if len(closes) >= 11 else 0

    # 8. 趋势判断
    indicators["trend"] = "bullish" if indicators["ma5"] > indicators["ma10"] > indicators["ma20"] else \
                          "bearish" if indicators["ma5"] < indicators["ma10"] < indicators["ma20"] else "neutral"

    return indicators

def _ema(data: List[float], period: int) -> float:
    """指数移动平均"""
    if len(data) < period:
        return data[-1]
    multiplier = 2 / (period + 1)
    ema = data[0]
    for price in data[1:]:
        ema = (price - ema) * multiplier + ema
    return ema

def _rsi(closes: List[float], period: int = 14) -> float:
    """相对强弱指标"""
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas[-period:]]
    losses = [-d if d < 0 else 0 for d in deltas[-period:]]
    avg_gain = float(np.mean(gains))
    avg_loss = float(np.mean(losses))
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def _kdj(closes: List[float], highs: List[float], lows: List[float], n: int = 9) -> Tuple[float, float, float]:
    """KDJ指标"""
    if len(closes) < n:
        return 50.0, 50.0, 50.0
    low_n = min(lows[-n:])
    high_n = max(highs[-n:])
    if high_n == low_n:
        rsv = 50.0
    else:
        rsv = (closes[-1] - low_n) / (high_n - low_n) * 100
    k = round(rsv * 2/3 + 50 * 1/3, 2)
    d = round(k * 2/3 + 50 * 1/3, 2)
    j = round(3 * k - 2 * d, 2)
    return k, d, j

def _boll(closes: List[float], period: int = 20) -> Tuple[float, float, float]:
    """布林带"""
    if len(closes) < period:
        period = len(closes)
    ma = float(np.mean(closes[-period:]))
    std = float(np.std(closes[-period:]))
    upper = round(ma + 2 * std, 2)
    lower = round(ma - 2 * std, 2)
    return upper, round(ma, 2), lower

def calculate_market_sentiment(all_stocks: List[Dict]) -> Dict:
    """计算市场情绪指标"""
    if not all_stocks:
        return {"sentiment": "neutral", "score": 50, "up_down_ratio": 1.0, "limit_up": 0, "limit_down": 0, "avg_change": 0}

    up_count = sum(1 for s in all_stocks if s.get("pct", 0) > 0 or s.get("change_pct", 0) > 0)
    down_count = sum(1 for s in all_stocks if s.get("pct", 0) < 0 or s.get("change_pct", 0) < 0)
    up_down_ratio = up_count / max(down_count, 1)

    limit_up = sum(1 for s in all_stocks if (s.get("pct", 0) or s.get("change_pct", 0)) >= 9.5)
    limit_down = sum(1 for s in all_stocks if (s.get("pct", 0) or s.get("change_pct", 0)) <= -9.5)

    avg_change = float(np.mean([s.get("pct", 0) or s.get("change_pct", 0) for s in all_stocks]))

    score = 50
    if up_down_ratio > 1.5:
        score += 20
    elif up_down_ratio < 0.7:
        score -= 20

    if limit_up > limit_down + 5:
        score += 15
    elif limit_down > limit_up + 5:
        score -= 15

    if avg_change > 1:
        score += 10
    elif avg_change < -1:
        score -= 10

    score = max(0, min(100, score))

    if score >= 70:
        sentiment = "bullish"
    elif score <= 30:
        sentiment = "bearish"
    else:
        sentiment = "neutral"

    return {
        "sentiment": sentiment,
        "score": score,
        "up_down_ratio": round(up_down_ratio, 2),
        "limit_up": limit_up,
        "limit_down": limit_down,
        "avg_change": round(avg_change, 2)
    }

# ═════════════════════════════════════════════════════
#  数据库操作
# ═════════════════════════════════════════════════════
def get_account(db: Session) -> AccountModel:
    acct = db.query(AccountModel).first()
    if not acct:
        acct = AccountModel(initial_cash=100000.0, cash=100000.0)
        db.add(acct)
        db.commit()
        db.refresh(acct)
    return acct

def calc_available_to_sell(db: Session, symbol: str) -> int:
    t = beijing_now().date()
    lots = db.query(LotModel).filter(
        LotModel.symbol == symbol, LotModel.remaining > 0, LotModel.buy_date < t
    ).all()
    return sum(lot.remaining for lot in lots)

def calc_current_equity(db: Session) -> Tuple[float, List[Dict]]:
    acct = get_account(db)
    positions = db.query(PositionModel).filter(PositionModel.qty > 0).all()
    trading = is_trading_hours()
    total_hold = 0.0
    rows = []
    for pos in positions:
        q = fetch_quote(pos.symbol) if trading else None
        price = q["price"] if q else (pos.last_price or pos.avg_cost)
        if q:
            pos.last_price = price
        market = pos.qty * price
        unrealized = (price - pos.avg_cost) * pos.qty
        total_hold += market
        avails = calc_available_to_sell(db, pos.symbol)
        rows.append({
            "symbol": pos.symbol, "name": pos.name,
            "qty": pos.qty, "avg_cost": round(pos.avg_cost, 4),
            "price": round(price, 4), "market_value": round(market, 2),
            "unrealized": round(unrealized, 2),
            "unrealized_pct": round((price/pos.avg_cost - 1)*100, 2) if pos.avg_cost else 0,
            "available": avails, "stop": pos.stop_loss,
            "buy_reason": pos.buy_reason, "score": pos.score,
        })
    db.flush()
    return acct.cash + total_hold, rows


def calc_position_pct(market_value: float, total_equity: float) -> float:
    if total_equity <= 0:
        return 0.0
    return round(market_value / total_equity * 100, 2)


def cap_target_pct(target_pct: float, max_position_pct: float) -> float:
    return round(max(0.0, min(target_pct, max_position_pct)), 2)


def safe_json_loads(raw: str, default):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


# ═════════════════════════════════════════════════════
#  Agent 上下文与记忆辅助函数
# ═════════════════════════════════════════════════════
def build_agent_cycle_context(cycle_id: str, timestamp: str, account_info: Dict,
                              positions_ctx: List[Dict], candidates_ctx: List[Dict],
                              market_sentiment: Dict, engine_params: Dict,
                              recent_trades: List[Dict], recent_decisions: List[Dict],
                              memory_summary: Dict) -> Dict:
    # Parameter names use *_ctx/*_info suffixes, while returned keys stay aligned
    # with the stable agent payload consumed elsewhere in the harness.
    context_sections = {
        "account": account_info,
        "positions": positions_ctx,
        "candidate_pool": candidates_ctx,
        "market_snapshot": market_sentiment,
        "engine_params": engine_params,
        "recent_trades": recent_trades,
        "recent_decisions": recent_decisions,
    }
    return {
        "cycle_id": cycle_id,
        "timestamp": timestamp,
        **context_sections,
        "memory_summary": memory_summary or {"items": [], "notes": []},
    }


def recall_recent_agent_memory(db: Session, limit: int = 5, memory_type: str = "short_term") -> Dict:
    rows = db.query(AgentMemoryModel).filter(
        AgentMemoryModel.memory_type == memory_type
    ).order_by(AgentMemoryModel.memory_date.desc()).limit(limit).all()

    items = []
    notes = []
    for row in rows:
        payload = safe_json_loads(row.content_json, {})
        if not isinstance(payload, dict):
            payload = {}

        row_notes = payload.get("notes", [])
        if isinstance(row_notes, list):
            notes.extend(str(note) for note in row_notes if note is not None)
        elif row_notes:
            notes.append(str(row_notes))

        items.append({
            "id": row.id,
            "memory_type": row.memory_type,
            "memory_date": row.memory_date.isoformat() if row.memory_date else "",
            "tags": row.tags,
            "content": payload,
            "relevance_score": row.relevance_score,
        })

    return {"items": items, "notes": notes[:5]}


class TradingAgentState(TypedDict, total=False):
    context: Dict[str, Any]
    memory_summary: Dict[str, Any]
    market_assessment: Dict[str, Any]
    position_assessments: List[Dict[str, Any]]
    candidate_assessments: List[Dict[str, Any]]
    risk_review: Dict[str, Any]
    final_plan: Dict[str, Any]



def run_market_analysis_node(state: TradingAgentState) -> Dict[str, Any]:
    context = state["context"]
    snapshot = context.get("market_snapshot", {})
    score = float(snapshot.get("score", 50) or 50)
    regime = "bullish" if score >= 70 else "defensive" if score <= 45 else "neutral"
    return {
        "market_assessment": {
            "regime": regime,
            "sentiment_score": score,
            "risk_bias": "aggressive" if score >= 70 else "conservative" if score <= 45 else "balanced",
            "sector_focus": [],
            "warnings": [],
            "reasoning": snapshot.get("sentiment", "市场中性"),
        }
    }



def run_position_review_node(state: TradingAgentState) -> Dict[str, Any]:
    positions = []
    for pos in state["context"].get("positions", []):
        positions.append({
            "symbol": pos["symbol"],
            "action": "hold",
            "target_pct": min(50.0, pos.get("target_pct", 20.0) or 20.0),
            "confidence": 0.6,
            "thesis": "等待 AI 细化",
            "risks": [],
            "supports": [],
        })
    return {"position_assessments": positions}



def run_candidate_research_node(state: TradingAgentState) -> Dict[str, Any]:
    return {"candidate_assessments": []}



def run_risk_review_node(state: TradingAgentState) -> Dict[str, Any]:
    return {
        "risk_review": {
            "overall_pass": True,
            "risk_level": "medium",
            "blocked_actions": [],
            "adjustments": [],
            "notes": [],
        }
    }



def run_decision_synthesizer_node(state: TradingAgentState) -> Dict[str, Any]:
    assessments = state.get("position_assessments", [])
    final_plan = {
        "cycle_id": state["context"]["cycle_id"],
        "position_actions": [
            {
                "symbol": item["symbol"],
                "action": item["action"],
                "target_pct": item["target_pct"],
            }
            for item in assessments
        ],
        "new_entries": [],
        "buy_picks": [],
        "portfolio_bias": state.get("market_assessment", {}).get("risk_bias", "balanced"),
        "cash_reserve_target": 0.35,
        "summary": state.get("market_assessment", {}).get("reasoning", "Agent plan"),
        "confidence": 0.6,
        "risk_level": state.get("risk_review", {}).get("risk_level", "medium"),
    }
    return {"final_plan": final_plan}



def build_trading_agent_graph():
    """构建交易 Agent 有向图，串联记忆召回、市场分析、持仓审视、候选研究、风控审查和决策综合六个节点。"""
    graph = StateGraph(TradingAgentState)
    graph.add_node("recall_memory", lambda state: {"memory_summary": state["context"].get("memory_summary", {})})
    graph.add_node("analyze_market", run_market_analysis_node)
    graph.add_node("review_positions", run_position_review_node)
    graph.add_node("research_candidates", run_candidate_research_node)
    graph.add_node("risk_review", run_risk_review_node)
    graph.add_node("synthesize_decision", run_decision_synthesizer_node)

    graph.set_entry_point("recall_memory")
    graph.add_edge("recall_memory", "analyze_market")
    graph.add_edge("analyze_market", "review_positions")
    graph.add_edge("review_positions", "research_candidates")
    graph.add_edge("research_candidates", "risk_review")
    graph.add_edge("risk_review", "synthesize_decision")
    graph.add_edge("synthesize_decision", END)
    return graph.compile()



def run_trading_agent_cycle(context: Dict[str, Any]) -> Dict[str, Any]:
    """执行一次完整的交易 Agent 决策周期，返回最终计划字典。异常时返回空安全计划。"""
    graph = build_trading_agent_graph()
    try:
        result = graph.invoke({"context": context})
        return result.get("final_plan", {})
    except Exception as e:
        print(f"[Agent] 交易周期执行异常: {e}")
        return {
            "cycle_id": context.get("cycle_id", ""),
            "position_actions": [],
            "new_entries": [],
            "buy_picks": [],
            "portfolio_bias": "balanced",
            "cash_reserve_target": 1.0,
            "summary": f"Agent 执行异常，已回退至安全计划: {e}",
            "confidence": 0.0,
            "risk_level": "high",
        }


def calc_target_delta_amount(current_pct: float, target_pct: float, total_equity: float) -> float:
    if total_equity <= 0:
        return 0.0
    return round((target_pct - current_pct) / 100 * total_equity, 2)


def calc_trade_qty_from_delta(delta_amount: float, price: float) -> int:
    if price <= 0:
        return 0
    raw_qty = int(abs(delta_amount) / price)
    return round_lot(raw_qty)


def normalize_position_action(item: Dict) -> str:
    action = str(item.get("action", "hold")).lower().strip()
    if action in {"add", "hold", "reduce", "exit"}:
        return action
    return "hold"


def parse_position_action(item: Dict) -> Dict:
    action = normalize_position_action(item)
    target_pct = float(item.get("target_pct", 0) or 0)
    change_pct = float(item.get("change_pct", 0) or 0)
    return {
        "symbol": normalize_symbol(item.get("symbol", "")),
        "action": action,
        "target_pct": round(max(0.0, target_pct), 2),
        "change_pct": round(change_pct, 2),
        "reason": str(item.get("reason", ""))[:120],
        "confidence": float(item.get("confidence", 0) or 0),
    }


def allow_add_action(pnl_pct: float, current_pct: float, target_pct: float,
                     max_position_pct: float, trend_ok: bool) -> bool:
    if not trend_ok:
        return False
    if pnl_pct < 0:
        return False
    if target_pct <= current_pct:
        return False
    if target_pct > max_position_pct:
        return False
    return True


def allow_reduce_action(current_pct: float, target_pct: float) -> bool:
    return target_pct < current_pct


def has_remaining_position_capacity(open_count: int, max_positions: int, remaining_capacity: int) -> bool:
    return open_count < max_positions and remaining_capacity > 0


def should_force_exit(pnl_pct: float, stop_loss_pct: float, trend_broken: bool = False) -> bool:
    if pnl_pct <= -abs(stop_loss_pct):
        return True
    if trend_broken:
        return True
    return False


def take_snapshot(db: Session, note: str = ""):
    """记录权益快照。注意：不负责 commit，由调用方统一提交。"""
    acct = get_account(db)
    positions = db.query(PositionModel).filter(PositionModel.qty > 0).all()
    pos_info = [(p.symbol, p.qty) for p in positions]
    equity, _ = calc_current_equity(db)
    print(f"[snapshot] note={note} cash={acct.cash:.2f} equity={equity:.2f} positions={pos_info}")
    snap = EquitySnapshotModel(cash=round(acct.cash, 2), equity=round(equity, 2), note=note)
    db.add(snap)

def log_decision(db: Session, action: str, symbol: str = "", name: str = "",
                 price: float = None, score: float = None, reason: str = "", detail: str = ""):
    log = DecisionLogModel(action=action, symbol=symbol, name=name,
                           price=price, score=score, reason=str(reason)[:500], detail=str(detail)[:1000])
    db.add(log)
    db.commit()

def exec_buy(db: Session, symbol: str, name: str, price: float, qty: int,
             stop_loss: float = None, reason: str = "", score: float = 0.0, is_etf: bool = False) -> Dict:
    with _trade_lock:
        return _exec_buy(db, symbol, name, price, qty, stop_loss, reason, score, is_etf)

def _exec_buy(db: Session, symbol: str, name: str, price: float, qty: int,
              stop_loss: float, reason: str, score: float, is_etf: bool) -> Dict:
    qty = round_lot(qty)
    if qty <= 0:
        return {"ok": False, "error": "数量不足100股"}
    gross = qty * price
    fee = fee_for_trade(gross, "buy", is_etf=is_etf)
    total = gross + fee
    acct = get_account(db)
    if total > acct.cash:
        return {"ok": False, "error": f"现金不足"}
    acct.cash -= total
    pos = db.query(PositionModel).filter(PositionModel.symbol == symbol).first()
    if not pos:
        pos = PositionModel(symbol=symbol, name=name, kind="etf" if is_etf else "stock")
        db.add(pos)
    pos.name = name
    if stop_loss:
        pos.stop_loss = stop_loss
    pos.buy_reason = reason[:128]
    pos.score = score
    old_qty = pos.qty or 0
    old_cost = (pos.avg_cost or 0) * old_qty
    pos.qty = old_qty + qty
    price_with_fee = round(price + fee / qty, 4)
    pos.avg_cost = round((old_cost + qty * price_with_fee) / pos.qty, 4)
    if not pos.last_price:
        pos.last_price = pos.avg_cost
    lot = LotModel(symbol=symbol, buy_date=beijing_now().date(), qty=qty, remaining=qty, price=price_with_fee, stop=stop_loss)
    db.add(lot)
    trade = TradeModel(side="buy", symbol=symbol, name=name, qty=qty, price=price,
                       gross=round(gross,2), fee=fee, cash_after=round(acct.cash,2),
                       reason=reason, is_auto=True)
    db.add(trade)
    db.flush()  # 确保数据可读，但不提交事务
    take_snapshot(db, f"buy {symbol}")
    log_decision(db, "buy", symbol, name, price, score, reason)
    db.commit()
    return {"ok": True, "symbol": symbol, "qty": qty, "price": price, "fee": fee, "cash_after": acct.cash}

def exec_sell(db: Session, symbol: str, price: float, qty: int, reason: str = "", is_etf: bool = False) -> Dict:
    with _trade_lock:
        return _exec_sell(db, symbol, price, qty, reason, is_etf)

def _exec_sell(db: Session, symbol: str, price: float, qty: int, reason: str, is_etf: bool) -> Dict:
    pos = db.query(PositionModel).filter(PositionModel.symbol == symbol).first()
    if not pos or pos.qty <= 0:
        return {"ok": False, "error": "没有持仓"}
    max_sell = calc_available_to_sell(db, symbol)
    qty = round_lot(min(qty, max_sell))
    if qty <= 0:
        return {"ok": False, "error": "无可卖数量（T+1限制）"}
    lots = db.query(LotModel).filter(
        LotModel.symbol == symbol, LotModel.remaining > 0, LotModel.buy_date < beijing_now().date()
    ).order_by(LotModel.buy_date).all()
    qty_left = qty
    cost_basis = 0.0
    for lot in lots:
        if qty_left <= 0:
            break
        take = min(lot.remaining, qty_left)
        lot.remaining -= take
        qty_left -= take
        cost_basis += take * lot.price
    gross = qty * price
    fee = fee_for_trade(gross, "sell", is_etf=is_etf)
    proceeds = gross - fee
    realized = proceeds - cost_basis
    acct = get_account(db)
    acct.cash += proceeds
    if qty >= pos.qty:
        db.delete(pos)
    else:
        pos.qty -= qty
        db.add(pos)
    trade = TradeModel(side="sell", symbol=symbol, name=pos.name, qty=qty, price=price,
                       gross=round(gross,2), fee=fee, cash_after=round(acct.cash,2),
                       realized_pnl=round(realized,2), reason=reason, is_auto=True)
    db.add(trade)
    db.flush()  # 确保数据可读，但不提交事务
    take_snapshot(db, f"sell {symbol}")
    log_decision(db, "sell", symbol, pos.name, price, reason=reason)
    db.commit()
    return {"ok": True, "symbol": symbol, "qty": qty, "price": price, "realized": round(realized,2)}

# ═════════════════════════════════════════════════════
#  AI 决策引擎（兼容 OpenAI 格式：阿里百炼 / DeepSeek 等）
# ═════════════════════════════════════════════════════

# 加载 API 配置（优先级：环境变量 > .env > config.json > 默认值）
CONFIG_PATH = Path(__file__).parent / "config.json"
_cfg = {}
if CONFIG_PATH.exists():
    try:
        _cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", _cfg.get("deepseek_api_key", ""))
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", _cfg.get("deepseek_model", "deepseek-chat"))
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", _cfg.get("deepseek_base_url", "https://api.deepseek.com/v1"))

def ai_call(messages: List[Dict], temperature: float = 0.3) -> str:
    """调用 AI API（兼容 OpenAI 格式，支持阿里百炼/DeepSeek 等）"""
    if not DEEPSEEK_API_KEY:
        return json.dumps({"error": "未配置 API Key，请在 .env 文件或环境变量中设置 DEEPSEEK_API_KEY"})
    try:
        import urllib.request, urllib.error
        url = f"{DEEPSEEK_BASE_URL}/chat/completions"
        payload_dict = {
            "model": DEEPSEEK_MODEL,
            "messages": messages,
            "max_tokens": 8000,
        }
        # deepseek-reasoner 不支持 temperature 参数
        if "reasoner" not in DEEPSEEK_MODEL:
            payload_dict["temperature"] = temperature
        payload = json.dumps(payload_dict).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        })
        # 推理模型响应较慢，超时设为 180 秒
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            choices = result.get("choices", [])
            if choices:
                msg = choices[0].get("message", {})
                # 推理模型会返回 reasoning_content（思维链）
                reasoning = msg.get("reasoning_content", "")
                if reasoning:
                    print(f"[AI 推理过程] {reasoning[:500]}...")
                return msg.get("content", "")
            return json.dumps({"error": "no response"})
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return json.dumps({"error": f"HTTP {e.code}: {body}"})
    except Exception as e:
        return json.dumps({"error": str(e)})

def ai_decide_trade(action_type: str, context: Dict) -> Dict:
    """
    让 AI 决定买卖/持仓
    action_type: "buy" | "sell" | "hold" | "scan"
    context: 当前市场数据、持仓、账户等上下文
    返回: {"action": "buy"/"sell"/"hold", "symbol": "...", "reason": "...", "confidence": 0-100, ...}
    """
    system_prompt = """你是一位A股资深短线交易员，拥有15年实盘经验，擅长技术分析和风险控制。
你的决策风格：稳健、纪律性强、严格止损。
每次交易前你都会分析：量价关系、趋势、支撑阻力位、市场情绪、风险收益比。

⚠️ 重要约束：用户资金有限，买入时必须确保 "suggested_price × 100（1手）" 不超过用户可用现金！

请根据提供的市场数据，输出JSON格式的交易决策：
{
  "action": "buy" | "sell" | "hold" | "skip",
  "symbol": "股票代码",
  "name": "股票名称",
  "reason": "详细的决策理由（中文）",
  "confidence": 0-100,
  "suggested_price": 0.00,
  "suggested_stop_loss": 0.00,
  "suggested_qty_pct": 0-20,  // 占总仓位百分比
  "analysis": "技术分析总结"
}

注意：
- 只输出JSON，不要包含其他文字
- 分析要具体，基于数据，不要泛泛而谈
- 如果市场条件不适合交易，action输出"hold"并说明原因
- 止损位必须合理，通常在支撑位下方2-5%
- 🚨 永远只推荐用户账户资金买得起的股票（suggested_price × 100 ≤ 可用现金）"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"请做出以下{action_type}决策。当前市场数据：\n{json.dumps(context, ensure_ascii=False, indent=2)}"}
    ]

    raw = ai_call(messages, temperature=0.4 if action_type == "buy" else 0.2)

    # 尝试解析 JSON
    try:
        # 尝试直接解析
        return json.loads(raw)
    except json.JSONDecodeError:
        # 尝试从 markdown 代码块中提取
        import re
        m = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        # 尝试提取 {} 包裹的内容
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return {"action": "hold", "reason": f"AI响应解析失败: {raw[:200]}", "confidence": 0}

def ai_daily_market_scan(all_stocks: List[Dict], portfolio: List[Dict], account_info: Dict) -> Dict:
    """
    让 AI 扫描全市场，选出最值得关注的股票/ETF
    返回: {"top_picks": [...], "market_analysis": "...", "risk_level": "high/mid/low"}
    """
    # 按成交额取前100只活跃股 + ETF
    candidates = sorted(all_stocks, key=lambda s: s.get("amount", 0), reverse=True)[:100]

    # 获取部分候选的历史数据供AI参考（优化：减少到10只，加快速度）
    add_realtime_log("info", "📊 正在获取候选股票历史数据+财务数据...")
    enriched = []
    fin_data = fetch_financial_batch()  # 获取全市场财务数据（有缓存）
    for i, s in enumerate(candidates[:10]):
        try:
            hist = fetch_history(s["symbol"], days=20)
            if hist:
                # 计算技术指标
                indicators = calculate_indicators(hist)
                s.update(indicators)
                closes = [h["close"] for h in hist[-5:]]
                s["ma5"] = round(float(np.mean(closes)), 2) if closes else s["price"]
                s["recent_high"] = max(h["high"] for h in hist[-5:])
                s["recent_low"] = min(h["low"] for h in hist[-5:])
                s["is_etf"] = is_etf_code(s["symbol"])

            # 获取估值指标（仅股票，ETF跳过）
            if not is_etf_code(s["symbol"]):
                try:
                    val = fetch_valuation(s["symbol"])
                    if val:
                        s["pe"] = val.get("pe")
                        s["pb"] = val.get("pb")
                        s["total_mv"] = val.get("total_mv")
                except Exception:
                    pass

            # 附加财务摘要
            fin = fin_data.get(s["symbol"], {})
            if fin:
                s["net_profit_yoy"] = fin.get("net_profit_yoy")
                s["revenue_yoy"] = fin.get("revenue_yoy")
                s["eps"] = fin.get("eps")

            enriched.append(s)
            if (i + 1) % 5 == 0:
                add_realtime_log("info", f"📊 已获取 {i+1}/10 只股票历史+财务数据...")
        except Exception as e:
            enriched.append(s)
            continue
    add_realtime_log("success", f"✅ 历史+财务数据获取完成，共 {len(enriched)} 只")

    # 计算市场情绪
    market_sentiment = calculate_market_sentiment(all_stocks)
    add_realtime_log("info", f"📈 市场情绪: {market_sentiment['sentiment']} (分数: {market_sentiment['score']})")

    system_prompt = f"""你是一位A股价值投资+量化专家，管理小资金账户。

## ⚠️ 最重要的约束（必须严格遵守）

**用户当前可用现金：¥{account_info['available_cash']:,.0f}**
**最大可买金额：¥{account_info['max_buy_amount']:,.0f}（保留¥1,000）**
**股票价格上限：¥{account_info['max_buy_price']:.0f}（确保买得起1手）**

### 价格硬约束
- **股票价格上限：¥{account_info['max_buy_price']:.0f}**（1手=100股，最多¥{account_info['max_buy_amount']:,.0f}）
- **ETF价格上限：¥5**（1手=1000股，最多¥5,000）
- **推荐价格区间：股票¥5-{account_info['max_buy_price']:.0f}，ETF¥0.5-5**

### 计算公式
- 股票：entry_price × 100 ≤ ¥{account_info['max_buy_amount']:,.0f}
- ETF：entry_price × 1000 ≤ ¥{account_info['max_buy_amount']:,.0f}

**如果推荐的价格超过¥{account_info['max_buy_price']:.0f}的股票，用户根本买不起，这是无效推荐！**

## 投资理念
- **价值为本**：选择基本面优质、估值合理的公司
- **技术择时**：在价值低估时，等待技术面确认买入
- **长期持有**：持有周期3-30天，不追涨杀跌
- **严格风控**：止损5%，止盈12%，追求2:1盈亏比

## 当前市场情绪
- 情绪状态: {market_sentiment['sentiment']}
- 情绪分数: {market_sentiment['score']}/100
- 涨跌比: {market_sentiment['up_down_ratio']}
- 涨停/跌停: {market_sentiment['limit_up']}/{market_sentiment['limit_down']}
- 平均涨跌: {market_sentiment['avg_change']}%

## 账户约束
- 初始资金: ¥10,000
- 单笔买入: ¥3,000-5,000
- 止损: 5%，止盈: 12%
- 最大持仓: 3只
- 持有周期: 3-30天

## 选股标准（价值投资+量化）

### 第一步：价格筛选（必须满足）
1. **股票价格：¥5-50**（确保能买100-1000股）
2. **ETF价格：¥0.5-5**（确保能买1000-10000股）
3. **排除价格>¥50的股票**（买不起1手）

### 第二步：基本面筛选（已自动排雷+财务数据参考）
系统已自动过滤亏损股和营收暴雷股，以下作为加分项：
1. **盈利增长**：优先选净利润同比正增长的股票（数据已在候选列表中提供）
2. **营收增长**：优先选营收同比正增长的股票
3. **估值参考**：PE/PB 数据已提供，作为估值高低的参考（短线交易不过度依赖估值）
4. **行业龙头**：市场份额大、品牌强的公司优先

### 第三步：技术面择时（量化）
在基本面优质的基础上，等待技术买点：
1. **趋势确认**：MA20向上，中期趋势向上
2. **回调买点**：股价回踩支撑位（MA20/MA60）
3. **MACD确认**：DIF上穿DEA，或柱状图转正
4. **RSI适中**：40-60区间，非超买
5. **成交量**：温和放量，资金认可

### 第四步：ETF配置（稳健底仓）
ETF作为稳健配置，降低整体风险：
- **大盘ETF**：510300沪深300、510500中证500（市场基准）
- **行业ETF**：512880证券、512690酒（行业配置）
- **跨境ETF**：159941纳指（全球配置）

## 选股优先级
1. **ETF配置**（权重50%）：价格低、风险分散、适合小资金
2. **低价价值股**（权重50%）：价格5-50元、基本面优质

## 风险控制
- **止损位**：买入价×0.95（-5%）
- **止盈位**：买入价×1.12（+12%）
- **持有周期**：3-30天，不频繁交易
- **仓位管理**：单只不超过50%，保留现金

## 输出JSON格式
{{
  "market_analysis": "市场整体分析（50字内）",
  "risk_level": "low/mid/high",
  "market_sentiment": "{market_sentiment['sentiment']}",
  "top_picks": [
    {{
      "symbol": "股票/ETF代码",
      "name": "名称",
      "kind": "stock/etf",
      "reason": "推荐理由（80字内，包含技术指标和新闻）",
      "entry_price": 买入价,
      "stop_loss": 止损价（买入价×0.95）,
      "target_price": 目标价（买入价×1.12）,
      "confidence": 70-95,
      "time_horizon": "3-30天"
    }}
  ]
}}

## ⚠️ 再次强调
1. **股票价格必须<¥50**，否则用户买不起1手
2. **ETF价格必须<¥5**，否则用户买不起1手
3. **优先推荐ETF**，价格低、风险分散、适合小资金
4. **不要推荐高价股**（如¥100、¥200、¥300的股票）"""

    # 获取实时新闻（带超时）
    add_realtime_log("info", "📰 正在获取最新财经新闻...")
    news = []
    try:
        import signal
        def timeout_handler(signum, frame):
            raise TimeoutError("新闻获取超时")
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(10)  # 10秒超时
        news = fetch_market_news()
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
        add_realtime_log("success", f"✅ 获取到 {len(news)} 条财经新闻")
    except (TimeoutError, Exception) as e:
        add_realtime_log("warning", f"⚠️ 新闻获取超时或失败，跳过新闻")
        news = []

    add_realtime_log("ai", "🤖 正在发送数据给AI分析...（这可能需要1-2分钟）")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"""当前账户状态：
{json.dumps(account_info, ensure_ascii=False)}

当前持仓：
{json.dumps(portfolio, ensure_ascii=False)}

📰 最新财经新闻（用于判断市场热点和驱动因素）：
{json.dumps(news, ensure_ascii=False, indent=2)}

📊 全市场活跃股前100只（已含技术指标+财务数据）：
{json.dumps(enriched[:50], ensure_ascii=False, default=str)}

说明：候选股票数据中可能包含以下财务字段：
- pe: 市盈率，pb: 市净率，total_mv: 总市值（万元）
- net_profit_yoy: 净利润同比增长率(%)，revenue_yoy: 营收同比增长率(%)
- eps: 每股收益
请结合财务数据、技术指标和新闻，分析推荐最值得买入的3-5只股票。优先选择财务数据健康的标的。"""}
    ]

    add_realtime_log("ai", "⏳ 等待AI响应中...")
    raw = ai_call(messages, temperature=0.3)

    if not raw or raw.startswith('{"error"'):
        add_realtime_log("error", f"❌ AI调用失败: {raw[:100]}")
    else:
        add_realtime_log("success", "✅ AI分析完成，正在解析结果...")

    try:
        import re
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            result = json.loads(m.group(0))
            return result
    except:
        pass
    return {"top_picks": [], "market_analysis": raw[:500], "risk_level": "mid"}


def ai_comprehensive_decision(positions_ctx: List[Dict], candidates_ctx: List[Dict],
                              account_info: Dict, market_sentiment: Dict) -> Dict:
    """
    一次 AI 调用同时管理持仓（卖/持有）+ 开仓（买/观望）。
    避免卖出后立刻又买回同一只股票的矛盾操作。

    返回:
    {
      "market_analysis": "...",
      "risk_level": "low/mid/high",
      "position_actions": [
        {"symbol": "...", "action": "add/hold/reduce/exit", "target_pct": 0, "change_pct": 0,
         "reason": "...", "confidence": 0-100}
      ],
      "buy_picks": [
        {"symbol": "...", "name": "...", "reason": "...", "entry_price": 0,
         "stop_loss": 0, "target_price": 0, "confidence": 0-100, "time_horizon": "..."}
      ]
    }
    """
    system_prompt = f"""你是一位A股资深短线交易员，管理小资金账户，拥有15年实盘经验。
你的决策风格：稳健、纪律性强、严格止损。

## ⚠️ 重要约束
- 用户可用现金：¥{account_info['available_cash']:,.0f}
- 最大可买金额：¥{account_info['max_buy_amount']:,.0f}（保留¥1,000）
- 股票价格上限：¥{account_info['max_buy_price']:.0f}（1手=100股）
- ETF价格上限：¥5（1手=1000股）
- 最大持仓：{account_info['max_positions']}只，当前已持有：{account_info['current_positions']}只

## 你的任务（一次完成）
1. **管理现有持仓**：对每只持仓决定「加仓 / 持有 / 减仓 / 退出」
   - 止盈原则：盈利达12%或短线涨幅过大（连续大涨后缩量）可部分减仓或退出
   - 止损原则：亏损达5%必须止损
   - 持有原则：趋势健康、未达止盈止损位则继续持有
2. **开新仓**：在持仓调整后释放资金的基础上，决定是否买入新标的
   - ⚠️ **关键**：如果某只持仓你决定退出，就不要再买入同一只股票！
   - 只推荐买得起的标的（entry_price × 100 ≤ 可用现金）
   - 优先ETF（低价、分散风险），其次低价价值股

## 持仓动作原则
- 你的首要目标是吃住主升浪。
- 盈利本身不是清仓理由，趋势破坏才是。
- 对短线过热但趋势未坏的持仓优先使用 reduce，而不是 exit。
- 只有趋势强化、仓位不高、且不是逆势补仓时才能使用 add。

## 市场情绪
- 情绪状态: {market_sentiment.get('sentiment', '未知')}
- 情绪分数: {market_sentiment.get('score', 0)}/100

## 输出JSON格式（严格）
{{
  "market_analysis": "市场整体分析（50字内）",
  "risk_level": "low/mid/high",
  "position_actions": [
    {{
      "symbol": "持仓股票代码",
      "action": "add" 或 "hold" 或 "reduce" 或 "exit",
      "target_pct": 0,
      "change_pct": 0,
      "reason": "决策理由（50字内）",
      "confidence": 60-95
    }}
  ],
  "buy_picks": [
    {{
      "symbol": "推荐买入代码",
      "name": "名称",
      "kind": "stock/etf",
      "reason": "推荐理由（80字内，含技术面）",
      "entry_price": 0.00,
      "stop_loss": 0.00,
      "target_price": 0.00,
      "confidence": 70-95,
      "time_horizon": "3-30天"
    }}
  ]
}}

## 注意
- 只输出JSON，不要其他文字
- position_actions 必须覆盖所有持仓
- 每个 position_action 都必须包含 target_pct 和 change_pct
- buy_picks 最多3只，可为空数组
- 不要推荐已在持仓中的股票
- exit 的股票不要再买回"""

    # 获取新闻
    add_realtime_log("info", "📰 正在获取最新财经新闻...")
    news = []
    try:
        import signal
        def timeout_handler(signum, frame):
            raise TimeoutError("新闻获取超时")
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(10)
        news = fetch_market_news()
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
        add_realtime_log("success", f"✅ 获取到 {len(news)} 条财经新闻")
    except (TimeoutError, Exception) as e:
        add_realtime_log("warning", f"⚠️ 新闻获取失败，跳过新闻")
        news = []

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"""## 账户状态
{json.dumps(account_info, ensure_ascii=False)}

## 当前持仓（含技术指标+盈亏）
{json.dumps(positions_ctx, ensure_ascii=False, default=str)}

## 全市场活跃候选股（含技术指标+财务数据）
{json.dumps(candidates_ctx, ensure_ascii=False, default=str)}

## 📰 最新财经新闻
{json.dumps(news, ensure_ascii=False, indent=2)}

请综合分析以上信息，一次完成：① 对每只持仓做出加仓/持有/减仓/退出决策 ② 决定是否开新仓。
注意：退出后的股票不要再买回；每个持仓动作都要给出 target_pct 和 change_pct。"""}
    ]

    add_realtime_log("ai", "🤖 AI正在综合分析持仓+市场，决定买卖...")
    raw = ai_call(messages, temperature=0.3)

    if not raw or raw.startswith('{"error"'):
        add_realtime_log("error", f"❌ AI综合决策调用失败: {raw[:100]}")
        return {"position_actions": [], "buy_picks": [], "market_analysis": raw[:200], "risk_level": "mid"}

    try:
        import re
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            result = json.loads(m.group(0))
            add_realtime_log("success", "✅ AI综合决策完成")
            return result
    except Exception as e:
        add_realtime_log("error", f"❌ AI响应解析失败: {e}")
    return {"position_actions": [], "buy_picks": [], "market_analysis": raw[:200], "risk_level": "mid"}


def ai_recommend_stocks(all_stocks: List[Dict], budget: Optional[float] = None) -> List[Dict]:
    """
    AI 智能推荐：基于质量分析推荐股票
    budget: 预算金额（元），None 表示不限资金
    返回推荐列表，每只股票附带详细推荐理由
    """
    # 按成交额取前50只活跃股
    candidates = sorted(all_stocks, key=lambda s: s.get("amount", 0), reverse=True)[:50]

    # 根据预算过滤候选（确保至少买得起1手）
    if budget is not None and budget > 0:
        filtered = []
        for s in candidates:
            price = s.get("price", 0)
            if price <= 0:
                continue
            if is_etf_code(s.get("symbol", "")):
                # ETF 1手=1000股（部分ETF是100股，但保守按1000算）
                if price * 100 <= budget:
                    filtered.append(s)
            else:
                # 股票 1手=100股
                if price * 100 <= budget:
                    filtered.append(s)
        if filtered:
            candidates = filtered
            add_realtime_log("info", f"💰 预算 ¥{budget:,.0f}，筛选出 {len(candidates)} 只可买标的")

    # 获取前15只候选的历史数据+财务数据
    budget_label = f"¥{budget:,.0f}" if budget else "不限"
    add_realtime_log("info", f"🌟 正在获取推荐候选数据（预算: {budget_label}）...")
    enriched = []
    fin_data = fetch_financial_batch()
    for i, s in enumerate(candidates[:15]):
        try:
            hist = fetch_history(s["symbol"], days=20)
            if hist:
                indicators = calculate_indicators(hist)
                s.update(indicators)
                closes = [h["close"] for h in hist[-5:]]
                s["ma5"] = round(float(np.mean(closes)), 2) if closes else s["price"]
                s["recent_high"] = max(h["high"] for h in hist[-5:])
                s["recent_low"] = min(h["low"] for h in hist[-5:])
                s["is_etf"] = is_etf_code(s["symbol"])

            # 获取估值指标（仅股票）
            if not is_etf_code(s["symbol"]):
                try:
                    val = fetch_valuation(s["symbol"])
                    if val:
                        s["pe"] = val.get("pe")
                        s["pb"] = val.get("pb")
                        s["total_mv"] = val.get("total_mv")
                except Exception:
                    pass

            # 附加财务摘要
            fin = fin_data.get(s["symbol"], {})
            if fin:
                s["net_profit_yoy"] = fin.get("net_profit_yoy")
                s["revenue_yoy"] = fin.get("revenue_yoy")
                s["eps"] = fin.get("eps")

            enriched.append(s)
            if (i + 1) % 5 == 0:
                add_realtime_log("info", f"🌟 已获取 {i+1}/15 只推荐候选数据...")
        except Exception:
            enriched.append(s)
            continue
    add_realtime_log("success", f"✅ 推荐候选数据获取完成，共 {len(enriched)} 只")

    # 计算市场情绪
    market_sentiment = calculate_market_sentiment(all_stocks)

    # 根据预算构建不同的 prompt 约束
    if budget is not None and budget > 0:
        max_stock_price = budget / 100  # 股票1手=100股
        max_etf_price = budget / 100    # ETF保守按100股算（实际很多ETF也是100股1手）
        budget_constraint = f"""
## ⚠️ 资金约束（必须严格遵守）
**用户可用资金：¥{budget:,.0f}**
- **股票价格上限：¥{max_stock_price:.0f}**（1手=100股，必须能买至少1手）
- **ETF价格上限：¥{max_etf_price:.0f}**（1手=100股）
- **推荐价格区间**：确保 entry_price × 100 ≤ ¥{budget:,.0f}
- 如果推荐的价格超过上限，用户根本买不起，这是无效推荐！
- 优先推荐用户"买得起"的标的，同时兼顾质量"""
    else:
        budget_constraint = """
## 推荐原则
- **不受资金限制**：可以推荐任意价格的股票，包括高价股如茅台、宁德时代等
- **纯质量导向**：只关注公司质量、行业地位、成长性和技术面"""

    # 构建推荐专用 prompt
    system_prompt = f"""你是一位资深A股投资专家，请基于纯质量分析推荐最值得关注的股票。
{budget_constraint}

## 当前市场情绪
- 情绪状态: {market_sentiment['sentiment']}
- 情绪分数: {market_sentiment['score']}/100
- 涨跌比: {market_sentiment['up_down_ratio']}
- 涨停/跌停: {market_sentiment['limit_up']}/{market_sentiment['limit_down']}

## 选股维度
1. **基本面**：行业龙头、盈利增长、财务健康（系统已过滤亏损股）
2. **技术面**：趋势向上、量价配合、关键支撑位
3. **估值**：PE/PB 参考，但不作为硬约束
4. **催化剂**：近期利好、政策利好、行业景气度

## 候选股票数据
候选股票包含以下字段：
- 基础: symbol, name, price, pct(涨跌幅)
- 技术: ma5, trend, macd_dif, macd_dea, rsi6, rsi14
- 财务: pe, pb, net_profit_yoy(净利润同比%), revenue_yoy(营收同比%), eps
- 估值: total_mv(总市值，万元)

## 输出JSON格式
{{
  "recommendations": [
    {{
      "symbol": "股票代码",
      "name": "股票名称",
      "kind": "stock/etf",
      "reason": "简要推荐理由（30字以内）",
      "reason_detail": "详细分析（150-200字，包含基本面、技术面、行业逻辑、催化剂等）",
      "confidence": 70-95,
      "entry_price": 当前价格或建议买入价,
      "target_price": 目标价（如有）,
      "stop_loss": 止损价（如有）
    }}
  ],
  "market_view": "当前市场观点（50字内）"
}}

请推荐5-8只最值得关注的股票/ETF，按推荐强度排序。"""

    add_realtime_log("ai", f"🤖 正在生成AI智能推荐（预算: {budget_label}）...")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"""📊 候选股票数据（已含技术指标+财务数据）：
{json.dumps(enriched, ensure_ascii=False, default=str)}

请基于以上数据，推荐最值得关注的5-8只股票。"""}
    ]

    raw = ai_call(messages, temperature=0.4)

    if not raw or raw.startswith('{"error"'):
        add_realtime_log("error", f"❌ AI推荐调用失败: {raw[:100] if raw else 'None'}")
        return []

    add_realtime_log("success", "✅ AI智能推荐生成完成")

    # 解析结果
    try:
        import re
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            result = json.loads(m.group(0))
            return result.get("recommendations", [])
    except Exception:
        pass
    return []


# ═════════════════════════════════════════════════════
#  全自动交易引擎
# ═════════════════════════════════════════════════════
class AutonomousTradingEngine:
    """
    全自主交易引擎 - 不需要任何人工干预
    ======================================
    工作流程（每分钟 tick 一次，交易时段才真正执行）：
    1. 扫描全市场，选取得分最高的候选股票
    2. 对每只持仓股票：检查止盈止损
    3. 如果现金充足 && 持仓数未达上限：开仓买入最优标的
    4. 决策记录全部入库，可在 Web 界面查看
    """

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        self._buy_amount_today = 0.0
        self._buy_date_today = ""

        # 策略参数 - 平衡激进型（适合新手+追求高收益）
        self.initial_cash = 10000.0              # 初始资金1万元
        self.target_annual_return = 0.28         # 目标年化28%（平衡激进）
        self.max_positions = 3                   # 最大持仓3只
        self.take_profit_pct = 12.0              # 止盈线12%（比15%低，更快落袋）
        self.stop_loss_pct = 5.0                 # 止损线5%（严格止损）
        self.trailing_stop_pct = 8.0             # 移动止损8%（保护盈利）
        self.max_position_pct = 50.0             # 单标的最大仓位50%
        self.risk_per_trade_pct = 2.0            # 单笔风险2%
        self.min_score_to_buy = 68.0             # 买入最低评分68（适中标准）
        self.max_buy_per_day = 8000.0            # 每日最大买入8000元
        self.top_picks_count = 25                # 选股池25只
        self.scan_interval = 180                 # 扫描间隔3分钟（适中频率）
        self.min_cash_reserve = 1000.0           # 最低保留现金1000元
        self.single_buy_min = 3000.0             # 单笔买入最低3000元
        self.single_buy_max = 5000.0             # 单笔买入最高5000元

    def start(self):
        if self._running:
            return
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[引擎] 全自动交易引擎已启动")

    def stop(self):
        self._stop_event.set()
        self._running = False
        print("[引擎] 全自动交易引擎已停止")

    @property
    def is_running(self) -> bool:
        return self._running

    def _is_trading_time(self) -> bool:
        """检查是否在A股交易时间内（9:30-11:30, 13:00-15:00）"""
        now = beijing_now()
        weekday = now.weekday()  # 0=周一, 6=周日
        if weekday >= 5:  # 周末不交易
            return False
        t = now.time()
        morning_start = dtime(9, 30)
        morning_end = dtime(11, 30)
        afternoon_start = dtime(13, 0)
        afternoon_end = dtime(15, 0)
        return (morning_start <= t <= morning_end) or (afternoon_start <= t <= afternoon_end)

    def _loop(self):
        """主循环"""
        while not self._stop_event.is_set():
            try:
                if self._is_trading_time():
                    self._tick()
                else:
                    # 非交易时段：跳过一切操作，10分钟检查一次
                    print("[引擎] 非交易时间，休眠等待")
                    self._stop_event.wait(600)  # 10分钟
                    continue
            except Exception as e:
                print(f"[引擎] tick error: {e}")
                traceback.print_exc()
            self._stop_event.wait(self.scan_interval)

    def _tick(self):
        """每次心跳执行 —— 一次 AI 调用综合决策买卖"""
        db = SessionLocal()
        try:
            db.rollback()  # 强制开启新事务，确保能看到其他 session 的提交
            acct = get_account(db)
            self.initial_cash = acct.initial_cash

            if self._buy_date_today != beijing_now().date().isoformat():
                self._buy_date_today = beijing_now().date().isoformat()
                self._buy_amount_today = 0.0

            if self._is_trading_time():
                self._comprehensive_trade(db)
            else:
                print(f"[引擎] 非交易时间，跳过 AI 决策")

            # 记录快照（任何时间都执行）
            take_snapshot(db, "auto_tick")
            db.commit()

        except Exception as e:
            print(f"[引擎] tick error: {e}")
            traceback.print_exc()
        finally:
            db.close()

    def _comprehensive_trade(self, db: Session):
        """一次 AI 调用综合决策：管理持仓 + 开新仓"""
        add_realtime_log("info", "🧠 开始综合决策（持仓管理+选股开仓）...")
        log_decision(db, "scan", reason="AI综合分析中: 持仓管理+选股开仓")

        acct = get_account(db)
        positions = db.query(PositionModel).filter(PositionModel.qty > 0).all()
        add_realtime_log("info", f"💰 可用现金: ¥{acct.cash:,.2f}, 持仓: {len(positions)}只")

        # ── 1. 准备持仓上下文（含实时行情+技术指标） ──
        positions_ctx = []
        for pos in positions:
            try:
                quote = fetch_quote(pos.symbol)
                price = quote["price"] if quote else (pos.last_price or pos.avg_cost)
                if quote:
                    pos.last_price = price
                avg_cost = pos.avg_cost
                pnl_pct = (price / avg_cost - 1) * 100 if avg_cost else 0
                avails = calc_available_to_sell(db, pos.symbol)

                pos_ctx = {
                    "symbol": pos.symbol, "name": pos.name,
                    "buy_price": avg_cost, "current_price": price,
                    "pnl_pct": round(pnl_pct, 2), "qty": pos.qty,
                    "available_to_sell": avails,
                    "stop_loss": pos.stop_loss, "buy_reason": pos.buy_reason,
                    "days_held": (beijing_now().date() - (db.query(LotModel).filter(
                        LotModel.symbol == pos.symbol, LotModel.remaining > 0
                    ).first().buy_date if db.query(LotModel).filter(
                        LotModel.symbol == pos.symbol, LotModel.remaining > 0
                    ).first() else beijing_now().date())).days,
                }
                hist = fetch_history(pos.symbol, days=20)
                if hist:
                    pos_ctx["recent_5d"] = hist[-5:]
                    pos_ctx["recent_high_10d"] = max(h["high"] for h in hist[-10:])
                    pos_ctx["recent_low_10d"] = min(h["low"] for h in hist[-10:])
                positions_ctx.append(pos_ctx)

                pnl_emoji = "🟢" if pnl_pct >= 0 else "🔴"
                add_realtime_log("info", f"{pnl_emoji} {pos.symbol} {pos.name}: ¥{price:.2f} ({pnl_pct:+.2f}%)")
            except Exception as e:
                print(f"[引擎] 准备持仓上下文异常 {pos.symbol}: {e}")

        # ── 2. 先执行硬性风控（止损/止盈线触发，不依赖AI） ──
        sold_symbols = set()
        remaining_positions = []
        for pos in positions:
            quote = fetch_quote(pos.symbol)
            price = quote["price"] if quote else (pos.last_price or pos.avg_cost)
            avg_cost = pos.avg_cost
            pnl_pct = (price / avg_cost - 1) * 100 if avg_cost else 0
            avails = calc_available_to_sell(db, pos.symbol)
            if avails <= 0:
                continue

            if should_force_exit(pnl_pct, self.stop_loss_pct):
                add_realtime_log("warning", f"🚨 止损触发: {pos.symbol} {pnl_pct:.1f}% <= -{self.stop_loss_pct:.1f}%")
                result = exec_sell(db, pos.symbol, price, avails,
                                   reason=f"止损线触发: {pnl_pct:.1f}% <= -{self.stop_loss_pct:.1f}%",
                                   is_etf=is_etf_code(pos.symbol))
                if result["ok"]:
                    add_realtime_log("success", f"✅ 止损卖出: {pos.symbol} @ ¥{price:.2f}")
                    sold_symbols.add(pos.symbol)
                continue

            if pnl_pct >= self.take_profit_pct:
                add_realtime_log("info", f"📌 利润管理区: {pos.symbol} {pnl_pct:.1f}% >= {self.take_profit_pct:.1f}%")

            remaining_positions.append(pos)

        # 刷新账户（卖出后现金增加）
        db.commit()
        acct = get_account(db)

        # ── 3. 准备市场候选数据 ──
        add_realtime_log("info", "📊 正在获取A股实时行情...")
        all_stocks = fetch_all_stocks()
        if not all_stocks:
            add_realtime_log("error", "❌ 无法获取市场数据")
            log_decision(db, "scan", reason="无法获取市场数据")
            return
        add_realtime_log("success", f"✅ 获取 {len(all_stocks)} 只股票行情")

        # 取成交额前10只活跃股，附加技术指标+财务数据
        candidates = sorted(all_stocks, key=lambda s: s.get("amount", 0), reverse=True)[:100]
        fin_data = fetch_financial_batch()
        candidates_ctx = []
        for i, s in enumerate(candidates[:10]):
            try:
                hist = fetch_history(s["symbol"], days=20)
                if hist:
                    indicators = calculate_indicators(hist)
                    s.update(indicators)
                    closes = [h["close"] for h in hist[-5:]]
                    s["ma5"] = round(float(np.mean(closes)), 2) if closes else s["price"]
                    s["recent_high"] = max(h["high"] for h in hist[-5:])
                    s["recent_low"] = min(h["low"] for h in hist[-5:])
                    s["is_etf"] = is_etf_code(s["symbol"])
                if not is_etf_code(s["symbol"]):
                    try:
                        val = fetch_valuation(s["symbol"])
                        if val:
                            s["pe"] = val.get("pe")
                            s["pb"] = val.get("pb")
                            s["total_mv"] = val.get("total_mv")
                    except Exception:
                        pass
                fin = fin_data.get(s["symbol"], {})
                if fin:
                    s["net_profit_yoy"] = fin.get("net_profit_yoy")
                    s["revenue_yoy"] = fin.get("revenue_yoy")
                    s["eps"] = fin.get("eps")
                candidates_ctx.append(s)
            except Exception:
                candidates_ctx.append(s)

        market_sentiment = calculate_market_sentiment(all_stocks)
        add_realtime_log("info", f"📈 市场情绪: {market_sentiment['sentiment']} (分数: {market_sentiment['score']})")

        # ── 4. 账户信息 ──
        max_buy_amount = min(acct.cash - 1000, 5000)
        max_buy_amount = max(0, max_buy_amount)
        account_info = {
            "initial_cash": acct.initial_cash,
            "available_cash": acct.cash,
            "max_buy_amount": max_buy_amount,
            "max_buy_price": max_buy_amount / 100 if max_buy_amount > 0 else 0,
            "current_positions": len(remaining_positions),
            "max_positions": self.max_positions,
            "remaining_capacity": self.max_positions - len(remaining_positions),
        }

        # ── 5. 调用 AI 综合决策 ──
        decision = ai_comprehensive_decision(positions_ctx, candidates_ctx, account_info, market_sentiment)

        market_analysis = decision.get("market_analysis", "")
        risk_level = decision.get("risk_level", "mid")
        if market_analysis:
            add_realtime_log("ai", f"📈 市场分析: {market_analysis[:150]}")
        add_realtime_log("info", f"⚡ 风险等级: {risk_level}")

        # ── 6. 执行 AI 的持仓决策（加/持/减/退） ──
        total_equity, _ = calc_current_equity(db)
        position_actions = decision.get("position_actions", [])
        for pa in position_actions:
            parsed = parse_position_action(pa)
            parsed["target_pct"] = cap_target_pct(parsed["target_pct"], self.max_position_pct)
            sym = parsed["symbol"]
            action = parsed["action"]
            reason = parsed["reason"]
            confidence = parsed["confidence"]
            target_pct = parsed["target_pct"]

            pos = db.query(PositionModel).filter(PositionModel.symbol == sym, PositionModel.qty > 0).first()
            if not pos or sym in sold_symbols:
                continue

            avails = calc_available_to_sell(db, sym)
            quote = fetch_quote(sym)
            price = quote["price"] if quote else (pos.last_price or pos.avg_cost)
            pnl_pct = (price / pos.avg_cost - 1) * 100 if pos.avg_cost else 0
            current_pct = calc_position_pct(price * pos.qty, total_equity)

            if action == "hold":
                add_realtime_log("info", f"🤖 AI建议继续持有 {sym} (信心: {confidence}%)")
                log_decision(db, "hold", sym, pos.name, price, score=confidence, reason=f"AI综合决策: 继续持有 - {reason[:100]}")
            elif action == "exit":
                if avails <= 0:
                    continue
                add_realtime_log("ai", f"🤖 AI建议退出 {sym} (信心: {confidence}%)")
                add_realtime_log("info", f"💡 理由: {reason[:80]}")
                result = exec_sell(db, sym, price, avails,
                                   reason=f"AI退出(信心{confidence}%): {reason[:100]}",
                                   is_etf=is_etf_code(sym))
                if result["ok"]:
                    add_realtime_log("success", f"✅ AI退出成功: {sym} @ ¥{price:.2f}")
                    sold_symbols.add(sym)
                    print(f"[AI] 退出 {sym} {avails}股 @ {price} {reason[:80]}")
            elif action == "reduce":
                if not allow_reduce_action(current_pct, target_pct):
                    log_decision(db, "skip", sym, pos.name, price, score=confidence, reason=f"减仓目标无效: 当前{current_pct:.2f}% 目标{target_pct:.2f}%")
                    continue
                delta_amount = calc_target_delta_amount(current_pct, target_pct, total_equity)
                if abs(delta_amount) < price * LOT_SIZE:
                    log_decision(db, "skip", sym, pos.name, price, score=confidence, reason="目标仓位变化不足一手")
                    continue
                qty = calc_trade_qty_from_delta(delta_amount, price)
                qty = round_lot(min(qty, avails))
                if qty <= 0:
                    log_decision(db, "skip", sym, pos.name, price, score=confidence, reason="目标仓位变化不足一手")
                    continue
                add_realtime_log("ai", f"🤖 AI建议减仓 {sym} {qty}股 (信心: {confidence}%)")
                add_realtime_log("info", f"💡 理由: {reason[:80]}")
                result = exec_sell(db, sym, price, qty,
                                   reason=f"AI减仓(信心{confidence}% 目标{target_pct}%): {reason[:100]}",
                                   is_etf=is_etf_code(sym))
                if result["ok"]:
                    add_realtime_log("success", f"✅ AI减仓成功: {sym} {qty}股 @ ¥{price:.2f}")
                    print(f"[AI] 减仓 {sym} {qty}股 @ {price} {reason[:80]}")
            elif action == "add":
                delta_amount = calc_target_delta_amount(current_pct, target_pct, total_equity)
                if abs(delta_amount) < price * LOT_SIZE:
                    log_decision(db, "skip", sym, pos.name, price, score=confidence, reason="目标仓位变化不足一手")
                    continue
                qty = calc_trade_qty_from_delta(delta_amount, price)
                if qty <= 0:
                    log_decision(db, "skip", sym, pos.name, price, score=confidence, reason="目标仓位变化不足一手")
                    continue
                if not allow_add_action(pnl_pct, current_pct, target_pct, self.max_position_pct, trend_ok=True):
                    log_decision(db, "skip", sym, pos.name, price, score=confidence, reason=f"不满足加仓条件: 当前{current_pct:.2f}% 目标{target_pct:.2f}%")
                    continue
                add_realtime_log("ai", f"🤖 AI建议加仓 {sym} {qty}股 (信心: {confidence}%)")
                add_realtime_log("info", f"💡 理由: {reason[:80]}")
                result = exec_buy(db, sym, pos.name, price, qty,
                                  stop_loss=pos.stop_loss, reason=f"AI加仓(信心{confidence}% 目标{target_pct}%): {reason[:100]}",
                                  score=confidence, is_etf=is_etf_code(sym))
                if result["ok"]:
                    gross = qty * price
                    self._buy_amount_today += gross
                    add_realtime_log("success", f"✅ AI加仓成功: {sym} {qty}股 @ ¥{price:.2f}")
                    print(f"[AI] 加仓 {sym} {qty}股 @ {price} {reason[:80]}")

        db.commit()
        acct = get_account(db)

        # ── 7. 执行 AI 的买入决策 ──
        existing_symbols = set(p.symbol for p in db.query(PositionModel).filter(PositionModel.qty > 0).all())
        # 已卖出的不再买回
        blocked_symbols = existing_symbols | sold_symbols

        buy_picks = decision.get("buy_picks", [])
        if not buy_picks:
            add_realtime_log("info", "⏸️ AI本轮不建议开新仓")
            log_decision(db, "hold", reason=f"AI综合决策: 本轮不开仓 - {market_analysis[:100]}")
            return

        add_realtime_log("success", f"🎯 AI建议买入 {len(buy_picks)} 只候选")
        bought_this_round = False
        open_count = len(existing_symbols)
        remaining_capacity = max(0, self.max_positions - open_count)
        for i, pick in enumerate(buy_picks):
            sym = normalize_symbol(pick.get("symbol", ""))
            if not sym or sym in blocked_symbols:
                if sym in sold_symbols:
                    add_realtime_log("info", f"⏭️ {sym} 刚卖出，本轮不买回")
                continue
            if not has_remaining_position_capacity(open_count, self.max_positions, remaining_capacity):
                log_decision(db, "skip", sym, pick.get("name", sym), 0, reason=f"开仓名额不足 ({open_count}/{self.max_positions})")
                add_realtime_log("warning", f"⚠️ 持仓名额已满，跳过新开仓 {sym}")
                break
            if self._buy_amount_today >= self.max_buy_per_day:
                add_realtime_log("warning", f"⚠️ 已达每日买入限额 ¥{self.max_buy_per_day:,.0f}")
                break

            name = pick.get("name", sym)
            sl = pick.get("stop_loss", 0) or 0
            confidence = pick.get("confidence", 0)
            reason = pick.get("reason", "AI推荐")

            quote = fetch_quote(sym)
            if not quote:
                add_realtime_log("warning", f"⚠️ 无法获取 {sym} 行情，跳过")
                log_decision(db, "skip", sym, name, 0, reason="无法获取实时行情")
                continue
            price = quote["price"]
            is_etf = is_etf_code(sym)
            if sl == 0:
                sl = round(price * 0.95, 3)

            # 买得起1手检查
            one_hand_cost = round(price * 100 * 1.01, 2)
            if one_hand_cost > acct.cash:
                add_realtime_log("warning", f"❌ {sym} 买不起1手: ¥{one_hand_cost:.0f} > 现金 ¥{acct.cash:.0f}")
                log_decision(db, "skip", sym, name, price, reason=f"买不起1手: ¥{one_hand_cost:.0f} > 现金¥{acct.cash:.0f}")
                continue

            # 计算仓位
            risk_per_share = price - sl
            if risk_per_share <= 0:
                log_decision(db, "skip", sym, name, price, reason=f"风险收益比不合理: 价格¥{price:.2f} 止损¥{sl:.2f}")
                continue
            risk_budget = self.initial_cash * (self.risk_per_trade_pct / 100)
            qty_by_risk = int(risk_budget / risk_per_share)
            qty_by_amount = int(self.single_buy_max / price)
            qty_by_cash = int((acct.cash - self.min_cash_reserve) / price)
            qty = round_lot(min(qty_by_risk, qty_by_amount, qty_by_cash))
            if qty <= 0:
                log_decision(db, "skip", sym, name, price, reason=f"计算股数为0")
                continue

            gross = qty * price
            if gross < self.single_buy_min:
                log_decision(db, "skip", sym, name, price, reason=f"买入金额不足: ¥{gross:.0f} < 最低¥{self.single_buy_min:.0f}")
                continue
            fee = fee_for_trade(gross, "buy", is_etf=is_etf)
            if gross + fee > acct.cash:
                log_decision(db, "skip", sym, name, price, reason=f"资金不足: 需¥{gross+fee:.0f} > 现金¥{acct.cash:.0f}")
                continue
            if self._buy_amount_today + gross > self.max_buy_per_day:
                log_decision(db, "skip", sym, name, price, reason=f"超每日限额: ¥{self._buy_amount_today:.0f}+¥{gross:.0f} > ¥{self.max_buy_per_day:.0f}")
                continue

            add_realtime_log("ai", f"🚀 AI综合决策买入 {sym} {name} (信心{confidence}%)")
            reason_str = f"AI决策(信心{confidence}%): {reason[:100]}"
            result = exec_buy(db, sym, name, price, qty, stop_loss=sl, reason=reason_str, score=confidence, is_etf=is_etf)
            if result["ok"]:
                self._buy_amount_today += gross
                bought_this_round = True
                add_realtime_log("success", f"✅ 买入成功: {sym} {name} {qty}股 @ ¥{price:.2f}")
                add_realtime_log("info", f"💡 AI理由: {reason[:80]}")
                print(f"[AI] 买入 {sym} {name} {qty}股 @ {price} 止损{sl} AI信心{confidence}%")
                break  # 每轮只开一笔

        if not bought_this_round:
            log_decision(db, "hold", reason=f"综合决策本轮未买入 ({len(buy_picks)}只候选均被过滤)")


    def _can_open_new_positions(self, db: Session) -> bool:
        """检查是否可以开新仓"""
        acct = get_account(db)
        open_count = db.query(PositionModel).filter(PositionModel.qty > 0).count()

        # 持仓数上限
        if open_count >= self.max_positions:
            log_decision(db, "hold", reason=f"持仓已满 ({open_count}/{self.max_positions})，等待平仓")
            return False

        # 现金充足（至少能买1手均价20块的股票）
        if acct.cash < 2000:
            log_decision(db, "hold", reason="现金不足")
            return False

        # 每日买入限额
        if self._buy_amount_today >= self.max_buy_per_day:
            log_decision(db, "hold", reason=f"今日买入已达限额 (已买: ¥{self._buy_amount_today:,.0f} / 限额: ¥{self.max_buy_per_day:,.0f})")
            add_realtime_log("warning", f"⚠️ 今日买入已达限额: ¥{self._buy_amount_today:,.0f} / ¥{self.max_buy_per_day:,.0f}")
            return False

        return True

    def _scan_and_buy(self, db: Session):
        """让 AI 扫描市场并决定买入"""
        add_realtime_log("info", "🔍 开始扫描全市场数据...")
        log_decision(db, "scan", reason="AI正在分析全市场数据...")

        # ★ 重要：先获取账户信息，显示可用现金
        acct = get_account(db)
        add_realtime_log("info", f"💰 当前可用现金: ¥{acct.cash:,.2f}")
        add_realtime_log("info", f"📊 最大可买金额: ¥{min(acct.cash - 1000, 5000):,.0f} (保留¥1,000)")

        existing_symbols = set()
        for p in db.query(PositionModel).filter(PositionModel.qty > 0).all():
            existing_symbols.add(p.symbol)

        add_realtime_log("info", "📊 正在获取A股实时行情...")
        all_stocks = fetch_all_stocks()
        if not all_stocks:
            add_realtime_log("error", "❌ 无法获取市场数据，请检查网络连接")
            log_decision(db, "scan", reason="无法获取市场数据")
            return
        add_realtime_log("success", f"✅ 成功获取 {len(all_stocks)} 只股票行情")

        portfolio_rows = []
        for pos in db.query(PositionModel).filter(PositionModel.qty > 0).all():
            q = fetch_quote(pos.symbol)
            price = q["price"] if q else pos.last_price
            portfolio_rows.append({
                "symbol": pos.symbol, "name": pos.name, "qty": pos.qty,
                "avg_cost": pos.avg_cost, "current_price": price,
                "pnl_pct": round((price / pos.avg_cost - 1) * 100, 2) if price and pos.avg_cost else 0,
                "stop_loss": pos.stop_loss, "buy_reason": pos.buy_reason,
            })

        # 计算可买金额范围
        max_buy_amount = min(acct.cash - 1000, 5000)  # 保留1000元，单笔最多5000
        max_buy_amount = max(0, max_buy_amount)

        account_info = {
            "initial_cash": acct.initial_cash,
            "available_cash": acct.cash,
            "max_buy_amount": max_buy_amount,
            "max_buy_price": max_buy_amount / 100,  # 股票最高价格
            "current_positions": len(portfolio_rows),
            "max_positions": self.max_positions,
            "remaining_capacity": self.max_positions - len(portfolio_rows),
        }

        # AI 扫描市场
        add_realtime_log("ai", "🤖 正在调用DeepSeek AI分析全市场数据...")
        add_realtime_log("info", f"📋 当前持仓: {len(portfolio_rows)}只")
        add_realtime_log("info", f"💰 可用资金: ¥{acct.cash:,.0f}, 最大可买: ¥{max_buy_amount:,.0f}")
        add_realtime_log("info", f"📊 股票价格上限: ¥{max_buy_amount/100:.0f} (确保买得起1手)")
        scan_result = ai_daily_market_scan(all_stocks, portfolio_rows, account_info)
        picks = scan_result.get("top_picks", [])
        market_analysis = scan_result.get("market_analysis", "")
        risk_level = scan_result.get("risk_level", "mid")

        if market_analysis:
            add_realtime_log("ai", f"📈 市场分析: {market_analysis[:150]}...")
        add_realtime_log("info", f"⚡ 市场风险等级: {risk_level}")

        if not picks:
            analysis = scan_result.get("market_analysis", "AI未找到合适标的")[:300]
            add_realtime_log("warning", f"⏸️ AI建议观望: {analysis[:100]}")
            log_decision(db, "scan", reason=f"AI建议观望: {analysis}")
            return
        add_realtime_log("success", f"🎯 AI选出 {len(picks)} 只候选股票")

        log_decision(db, "scan", reason=f"AI选出{len(picks)}只候选: {','.join(p['symbol'] for p in picks[:3])}",
                     detail=json.dumps(scan_result, ensure_ascii=False)[:500])

        # 对每只 AI 推荐逐一决策
        bought_this_round = False
        for i, pick in enumerate(picks):
            sym = normalize_symbol(pick.get("symbol", ""))
            if not sym or sym in existing_symbols:
                continue
            if self._buy_amount_today >= self.max_buy_per_day:
                add_realtime_log("warning", f"⚠️ 已达每日买入限额 ¥{self.max_buy_per_day:,.0f}")
                break

            name = pick.get("name", sym)
            entry = pick.get("entry_price", 0) or 0
            sl = pick.get("stop_loss", 0) or 0
            confidence = pick.get("confidence", 0)
            reason = pick.get("reason", "AI推荐")

            add_realtime_log("ai", f"🔍 正在分析第 {i+1} 只: {sym} {name} (AI信心: {confidence}%)")

            # 获取实时价格
            quote = fetch_quote(sym)
            if not quote:
                add_realtime_log("warning", f"⚠️ 无法获取 {sym} 行情，跳过")
                log_decision(db, "skip", sym, name, 0, reason=f"无法获取实时行情")
                continue
            price = quote["price"]
            is_etf = is_etf_code(sym)
            if sl == 0:
                sl = round(price * 0.95, 3)  # 默认止损5%（激进型）

            add_realtime_log("info", f"💰 {sym} 当前价: ¥{price:.2f}, 止损位: ¥{sl:.2f}, 类型: {'ETF' if is_etf else '股票'}")

            # ★ 硬性检查：买不买得起1手（100股+手续费）
            one_hand_cost = round(price * 100 * 1.01, 2)
            if one_hand_cost > acct.cash:
                add_realtime_log("warning", f"❌ {sym} 买不起1手: ¥{one_hand_cost:.0f} > 可用现金 ¥{acct.cash:.0f}")
                log_decision(db, "skip", sym, name, price,
                             reason=f"买不起1手: {price}×100≈¥{one_hand_cost:.0f} > 现金¥{acct.cash:.0f}")
                continue

            # 计算仓位（优化：适合1万元小资金，单笔3000-5000元）
            add_realtime_log("info", f"📐 正在计算仓位...")
            risk_per_share = price - sl
            if risk_per_share <= 0:
                add_realtime_log("warning", f"⚠️ {sym} 风险收益比不合理，跳过")
                log_decision(db, "skip", sym, name, price, reason=f"风险收益比不合理: 价格¥{price:.2f} 止损¥{sl:.2f} 价差≤0")
                continue

            # 风险预算（总资金的2%，即200元）
            risk_budget = self.initial_cash * (self.risk_per_trade_pct / 100)
            qty_by_risk = int(risk_budget / risk_per_share)

            # 按单笔金额限制（3000-5000元）
            qty_by_amount = int(self.single_buy_max / price)

            # 按可用现金计算（保留1000元）
            available = acct.cash - self.min_cash_reserve
            qty_by_cash = int(available / price)

            # 取最小值
            qty = round_lot(min(qty_by_risk, qty_by_amount, qty_by_cash))

            if qty <= 0:
                add_realtime_log("warning", f"⚠️ {sym} 计算股数为0，跳过")
                log_decision(db, "skip", sym, name, price,
                             reason=f"计算股数为0: 风险股数{qty_by_risk}/金额股数{qty_by_amount}/现金股数{qty_by_cash}")
                continue

            gross = qty * price

            # 检查单笔金额是否达到最低要求
            if gross < self.single_buy_min:
                add_realtime_log("warning", f"⚠️ {sym} 买入金额 ¥{gross:,.0f} < 最低 ¥{self.single_buy_min:,.0f}，跳过")
                log_decision(db, "skip", sym, name, price,
                             reason=f"买入金额不足: ¥{gross:,.0f} < 最低¥{self.single_buy_min:,.0f} ({qty}股×¥{price:.2f})")
                continue

            add_realtime_log("info", f"📊 计划买入: {qty}股 × ¥{price:.2f} = ¥{gross:,.0f}")

            # 计算手续费（ETF免印花税）
            fee = fee_for_trade(gross, "buy", is_etf=is_etf)
            if gross + fee > acct.cash:
                add_realtime_log("warning", f"❌ {sym} 资金不足，需要 ¥{gross:,.0f}，可用 ¥{acct.cash:.0f}")
                log_decision(db, "skip", sym, name, price,
                             reason=f"资金不足: 需¥{gross+fee:,.0f}(含手续费¥{fee:.0f}) > 现金¥{acct.cash:,.0f}")
                continue
            if self._buy_amount_today + gross > self.max_buy_per_day:
                add_realtime_log("warning", f"⚠️ 超过每日买入限额 (今日已买: ¥{self._buy_amount_today:,.0f} + 本次: ¥{gross:,.0f} > 限额: ¥{self.max_buy_per_day:,.0f})")
                log_decision(db, "skip", sym, name, price,
                             reason=f"超每日买入限额: 今日已买¥{self._buy_amount_today:,.0f}+本次¥{gross:,.0f} > 限额¥{self.max_buy_per_day:,.0f}")
                continue

            add_realtime_log("ai", f"🚀 AI决策买入 {sym} {name}...")
            reason_str = f"AI决策(信心{confidence}%): {reason[:100]}"
            result = exec_buy(db, sym, name, price, qty,
                              stop_loss=sl, reason=reason_str, score=confidence, is_etf=is_etf)
            if result["ok"]:
                self._buy_amount_today += gross
                bought_this_round = True
                add_realtime_log("success", f"✅ 买入成功: {sym} {name} {qty}股 @ ¥{price:.2f}")
                add_realtime_log("info", f"💡 AI理由: {reason[:80]}")
                print(f"[AI] 买入 {sym} {name} {qty}股 @ {price} 止损{sl} AI信心{confidence}%")
                print(f"    理由: {reason[:120]}")
                existing_symbols.add(sym)
                break  # 每轮只开一笔

        # 本轮扫描结束，未买入时记录原因
        if not bought_this_round and picks:
            log_decision(db, "hold", reason=f"本轮扫描{len(picks)}只候选均未买入（已被过滤或条件不满足，详见上方skip记录）")
            add_realtime_log("warning", f"⏸️ 本轮{len(picks)}只候选均未成功买入")

    def _manage_positions(self, db: Session):
        """AI 管理持仓：决定止盈、止损或继续持有"""
        positions = db.query(PositionModel).filter(PositionModel.qty > 0).all()
        if not positions:
            return

        add_realtime_log("info", f"📊 正在检查 {len(positions)} 只持仓...")
        for pos in positions:
            try:
                quote = fetch_quote(pos.symbol)
                if not quote:
                    add_realtime_log("warning", f"⚠️ 无法获取 {pos.symbol} 行情")
                    continue
                price = quote["price"]
                pos.last_price = price
                avg_cost = pos.avg_cost
                pnl_pct = (price / avg_cost - 1) * 100
                avails = calc_available_to_sell(db, pos.symbol)
                if avails <= 0:
                    continue

                pnl_emoji = "🟢" if pnl_pct >= 0 else "🔴"
                add_realtime_log("info", f"{pnl_emoji} {pos.symbol} {pos.name}: ¥{price:.2f} ({pnl_pct:+.2f}%)")

                # 先执行页面展示的硬性风控参数，保证模拟规则清晰一致
                if pnl_pct <= -self.stop_loss_pct:
                    add_realtime_log("warning", f"🚨 止损触发: {pos.symbol} {pnl_pct:.1f}% <= -{self.stop_loss_pct:.1f}%")
                    result = exec_sell(db, pos.symbol, price, avails,
                                       reason=f"止损线触发: {pnl_pct:.1f}% <= -{self.stop_loss_pct:.1f}%",
                                       is_etf=is_etf_code(pos.symbol))
                    if result["ok"]:
                        add_realtime_log("success", f"✅ 止损卖出成功: {pos.symbol} @ ¥{price:.2f}")
                        print(f"[规则] 止损卖出 {pos.symbol} @ {price}")
                    continue

                if pnl_pct >= self.take_profit_pct:
                    add_realtime_log("success", f"🎉 止盈触发: {pos.symbol} {pnl_pct:.1f}% >= {self.take_profit_pct:.1f}%")
                    result = exec_sell(db, pos.symbol, price, avails,
                                       reason=f"止盈线触发: {pnl_pct:.1f}% >= {self.take_profit_pct:.1f}%",
                                       is_etf=is_etf_code(pos.symbol))
                    if result["ok"]:
                        add_realtime_log("success", f"✅ 止盈卖出成功: {pos.symbol} @ ¥{price:.2f}")
                        print(f"[规则] 止盈卖出 {pos.symbol} @ {price}")
                    continue

                # 收集持仓上下文给 AI 决策
                pos_context = {
                    "symbol": pos.symbol,
                    "name": pos.name,
                    "buy_price": avg_cost,
                    "current_price": price,
                    "pnl_pct": round(pnl_pct, 2),
                    "qty": pos.qty,
                    "available_to_sell": avails,
                    "stop_loss": pos.stop_loss,
                    "buy_reason": pos.buy_reason,
                    "days_held": (beijing_now().date() - (db.query(LotModel).filter(
                        LotModel.symbol == pos.symbol, LotModel.remaining > 0
                    ).first().buy_date if db.query(LotModel).filter(
                        LotModel.symbol == pos.symbol, LotModel.remaining > 0
                    ).first() else beijing_now().date())).days,
                }

                # 获取历史数据
                hist = fetch_history(pos.symbol, days=20)
                if hist:
                    pos_context["recent_5d"] = hist[-5:]
                    pos_context["recent_high_10d"] = max(h["high"] for h in hist[-10:])
                    pos_context["recent_low_10d"] = min(h["low"] for h in hist[-10:])

                # AI 决策：是否卖出
                add_realtime_log("ai", f"🤖 AI正在分析 {pos.symbol} 是否卖出...")
                decision = ai_decide_trade("sell", {
                    "position": pos_context,
                    "account_cash": get_account(db).cash,
                    "total_positions": len(positions),
                })

                ai_action = decision.get("action", "hold")
                ai_reason = decision.get("reason", "")
                ai_confidence = decision.get("confidence", 0)

                if ai_action == "sell" and ai_confidence >= 60:
                    add_realtime_log("ai", f"🤖 AI建议卖出 {pos.symbol} (信心: {ai_confidence}%)")
                    add_realtime_log("info", f"💡 理由: {ai_reason[:80]}")
                    result = exec_sell(db, pos.symbol, price, avails,
                                       reason=f"AI卖出(信心{ai_confidence}%): {ai_reason[:100]}",
                                       is_etf=is_etf_code(pos.symbol))
                    if result["ok"]:
                        add_realtime_log("success", f"✅ AI卖出成功: {pos.symbol} @ ¥{price:.2f}")
                        print(f"[AI] 卖出 {pos.symbol} {avails}股 @ {price} {ai_reason[:80]}")
                    continue
                else:
                    add_realtime_log("info", f"🤖 AI建议继续持有 {pos.symbol} (信心: {ai_confidence}%)")

                # 回退：硬止损保护（AI 失效时的保险）
                if pnl_pct <= -self.stop_loss_pct:
                    result = exec_sell(db, pos.symbol, price, avails,
                                       reason=f"硬止损触发: {pnl_pct:.1f}% <= -{self.stop_loss_pct:.1f}% (AI决策回退)",
                                       is_etf=is_etf_code(pos.symbol))
                    if result["ok"]:
                        print(f"[AI] 硬止损 {pos.symbol} @ {price}")
                    continue

                # 记录 AI 的持有判断
                if pnl_pct >= 3 and ai_action == "hold":
                    log_decision(db, "hold", pos.symbol, pos.name, price,
                                 score=ai_confidence, reason=f"AI建议继续持有: {ai_reason[:150]}")

            except Exception as e:
                print(f"[AI] 持仓管理异常 {pos.symbol}: {e}")
        db.commit()

engine = AutonomousTradingEngine()

# ═════════════════════════════════════════════════════
#  FastAPI 应用
# ═════════════════════════════════════════════════════
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时自动运行引擎
    engine.start()
    yield
    engine.stop()

import pathlib
HTML_PATH = pathlib.Path(__file__).parent / "templates" / "index.html"
STATIC_DIR = pathlib.Path(__file__).parent / "static"
app = FastAPI(title="A股全自动智能交易系统", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(content=HTML_PATH.read_text(encoding="utf-8"))

# ── API: 账户 ──
@app.get("/api/account")
def api_account():
    try:
        with SessionLocal() as db:
            acct = get_account(db)
            equity, rows = calc_current_equity(db)
            return {
                "initial_cash": acct.initial_cash,
                "cash": round(acct.cash, 2),
                "equity": round(equity, 2),
                "return_pct": round((equity / acct.initial_cash - 1) * 100, 2) if acct.initial_cash else 0.0,
                "position_count": len(rows),
                "created_at": acct.created_at.isoformat() if acct.created_at else None,
            }
    except Exception as e:
        import traceback; traceback.print_exc()
        # 最低限度返回
        return {"initial_cash": 10000, "cash": 10000, "equity": 10000, "return_pct": 0, "position_count": 0, "created_at": None}

@app.post("/api/account/init")
def api_init_account(initial_cash: float = 100000.0, force: bool = False):
    try:
        with SessionLocal() as db:
            # 如果 force，清理所有数据
            if force:
                db.query(PositionModel).delete()
                db.query(LotModel).delete()
                db.query(TradeModel).delete()
                db.query(EquitySnapshotModel).delete()
                db.query(DecisionLogModel).delete()
            acct = get_account(db)
            acct.initial_cash = initial_cash
            acct.cash = initial_cash
            if force:
                db.query(PositionModel).delete()
                db.query(LotModel).delete()
                db.query(TradeModel).delete()
                db.query(EquitySnapshotModel).delete()
                db.query(DecisionLogModel).delete()
            db.commit()
            # 直接记录快照，避免取行情
            snap = EquitySnapshotModel(
                time=datetime.now(), cash=round(acct.cash, 2),
                equity=round(acct.cash, 2), note="init"
            )
            db.add(snap)
            db.commit()
            engine.initial_cash = initial_cash
            engine.start()
            return {"ok": True, "initial_cash": initial_cash, "engine_started": True}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"重置失败: {str(e)}")

# ── API: 引擎控制 ──
@app.get("/api/engine/status")
def api_engine_status():
    return {
        "running": engine.is_running,
        "max_positions": engine.max_positions,
        "take_profit_pct": engine.take_profit_pct,
        "stop_loss_pct": engine.stop_loss_pct,
        "trailing_stop_pct": engine.trailing_stop_pct,
        "target_annual_return": f"{engine.target_annual_return*100:.0f}%",
        "min_score_to_buy": engine.min_score_to_buy,
        "ai_model": "DeepSeek " + DEEPSEEK_MODEL,
        "ai_configured": bool(DEEPSEEK_API_KEY),
    }

@app.post("/api/engine/start")
def api_engine_start():
    engine.start()
    return {"ok": True}

@app.post("/api/engine/stop")
def api_engine_stop():
    engine.stop()
    return {"ok": True}

# ── API: 持仓 ──
@app.get("/api/portfolio")
def api_portfolio():
    with SessionLocal() as db:
        acct = get_account(db)
        equity, rows = calc_current_equity(db)
        return {
            "cash": acct.cash,
            "equity": round(equity, 2),
            "return_pct": round((equity / acct.initial_cash - 1) * 100, 2),
            "initial_cash": acct.initial_cash,
            "positions": rows,
        }

# ── API: 交易记录 ──
@app.get("/api/trades")
def api_trades(limit: int = 100):
    with SessionLocal() as db:
        rows = db.query(TradeModel).order_by(TradeModel.id.desc()).limit(limit).all()
        return [{
            "id": r.id, "time": r.time.strftime("%Y-%m-%d %H:%M:%S"),
            "side": r.side, "symbol": r.symbol, "name": r.name,
            "qty": r.qty, "price": r.price,
            "gross": r.gross, "fee": r.fee, "cash_after": r.cash_after,
            "reason": r.reason, "realized_pnl": r.realized_pnl,
        } for r in rows]

# ── API: 决策日志 ──
@app.get("/api/decisions")
def api_decisions(limit: int = 50):
    with SessionLocal() as db:
        rows = db.query(DecisionLogModel).order_by(DecisionLogModel.id.desc()).limit(limit).all()
        return [{
            "id": r.id, "time": r.time.strftime("%Y-%m-%d %H:%M:%S"),
            "action": r.action, "symbol": r.symbol, "name": r.name,
            "price": r.price, "score": r.score, "reason": r.reason,
        } for r in rows]

# ── API: 实时日志 ──
@app.get("/api/logs")
def api_realtime_logs(limit: int = 50):
    """获取实时日志"""
    with _log_lock:
        logs = list(_realtime_logs)[:limit]
    return logs

# ── API: 绩效 ──
@app.get("/api/metrics")
def api_metrics():
    with SessionLocal() as db:
        acct = get_account(db)
        equity, _ = calc_current_equity(db)
        sells = db.query(TradeModel).filter(
            TradeModel.side == "sell", TradeModel.realized_pnl != None
        ).all()
        pnls = [s.realized_pnl for s in sells if s.realized_pnl is not None]
        wins = [x for x in pnls if x > 0]
        losses = [x for x in pnls if x < 0]
        total_realized = sum(pnls)
        win_rate = len(wins) / len(pnls) * 100 if pnls else 0.0
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0
        payoff = abs(avg_win / avg_loss) if avg_loss else 0.0

        snaps = db.query(EquitySnapshotModel).order_by(EquitySnapshotModel.id).all()
        max_dd = 0.0
        peak = None
        for s in snaps:
            e = s.equity
            if peak is None or e > peak:
                peak = e
            if peak and peak > 0:
                dd = (peak - e) / peak
                max_dd = max(max_dd, dd)

        total_buys = db.query(TradeModel).filter(TradeModel.side == "buy").count()
        total_sells = db.query(TradeModel).filter(TradeModel.side == "sell").count()
        total_trades = total_buys + total_sells

        return {
            "initial_cash": acct.initial_cash,
            "equity": round(equity, 2),
            "total_return_pct": round((equity / acct.initial_cash - 1) * 100, 2),
            "total_realized": round(total_realized, 2),
            "total_trades": len(pnls),
            "win_count": len(wins), "loss_count": len(losses),
            "win_rate": round(win_rate, 2),
            "avg_win": round(avg_win, 2), "avg_loss": round(avg_loss, 2),
            "payoff_ratio": round(payoff, 2),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "buy_count": total_buys, "sell_count": total_sells,
            "total_trades": total_trades,
        }

# ── API: 净值曲线 ──
@app.get("/api/equity_curve")
def api_equity_curve(limit: int = 500):
    with SessionLocal() as db:
        snaps = db.query(EquitySnapshotModel).order_by(EquitySnapshotModel.id.desc()).limit(limit).all()
        snaps.reverse()
        return [{"time": s.time.strftime("%m-%d %H:%M"), "equity": s.equity} for s in snaps]

# ── API: 当前AI选股推荐（带缓存，非交易时间不调 AI） ──
@app.get("/api/picks")
def api_picks():
    global _picks_cache

    # 非交易时间：直接返回缓存（不调 AI）
    if not is_trading_hours():
        if _picks_cache["data"]:
            print("[picks] 非交易时间，返回缓存数据")
            return _picks_cache["data"]
        print("[picks] 非交易时间，无缓存，跳过 AI 调用")
        return []

    # 交易时间内：检查缓存是否新鲜（5分钟内）
    if _picks_cache["time"]:
        age = (beijing_now() - _picks_cache["time"]).total_seconds()
        if age < PICKS_CACHE_TTL:
            print(f"[picks] 缓存有效（{age:.0f}s 前），跳过 AI 调用")
            return _picks_cache["data"]

    try:
        all_stocks = fetch_all_stocks()
        if not all_stocks:
            return _picks_cache["data"] if _picks_cache["data"] else []
        candidates = sorted(all_stocks, key=lambda s: s.get("amount", 0), reverse=True)[:50]
        enriched = []
        fin_data = fetch_financial_batch()  # 获取全市场财务数据（有缓存）
        for s in candidates[:20]:
            hist = fetch_history(s["symbol"], days=15)
            if hist:
                s["ma5"] = round(float(np.mean([h["close"] for h in hist[-5:]])), 2)
                s["recent_high"] = max(h["high"] for h in hist[-10:])
                s["recent_low"] = min(h["low"] for h in hist[-10:])
            # 获取估值指标（仅股票）
            if not is_etf_code(s["symbol"]):
                try:
                    val = fetch_valuation(s["symbol"])
                    if val:
                        s["pe"] = val.get("pe")
                        s["pb"] = val.get("pb")
                        s["total_mv"] = val.get("total_mv")
                except Exception:
                    pass
            # 附加财务摘要
            fin = fin_data.get(s["symbol"], {})
            if fin:
                s["net_profit_yoy"] = fin.get("net_profit_yoy")
                s["revenue_yoy"] = fin.get("revenue_yoy")
                s["eps"] = fin.get("eps")
            enriched.append(s)
        result = ai_daily_market_scan(enriched, [], {
            "initial_cash": 100000,
            "available_cash": 100000,
            "current_positions": 0,
            "max_positions": 5,
            "max_buy_amount": 99000,
            "max_buy_price": 990
        })
        picks = result.get("top_picks", [])
        # 构建 picks 到 enriched 的索引，方便查找财务数据
        enriched_map = {s["symbol"]: s for s in enriched}
        data = [{
            "symbol": p.get("symbol", ""), "name": p.get("name", ""),
            "price": p.get("entry_price", 0),
            "confidence": p.get("confidence", 0),
            "score": p.get("confidence", 0),
            "reason": p.get("reason", "")[:100],
            "reasons": [p.get("reason", "")[:100]] if p.get("reason") else [],
            "pct": 0,
            "amount": 0,
            "stop_loss": p.get("stop_loss", ""), "target": p.get("target_price", ""),
            # 财务字段
            "pe": enriched_map.get(p.get("symbol", ""), {}).get("pe"),
            "pb": enriched_map.get(p.get("symbol", ""), {}).get("pb"),
            "net_profit_yoy": enriched_map.get(p.get("symbol", ""), {}).get("net_profit_yoy"),
            "revenue_yoy": enriched_map.get(p.get("symbol", ""), {}).get("revenue_yoy"),
        } for p in picks] if picks else []

        # 更新缓存
        _picks_cache = {"data": data, "time": beijing_now()}
        return data
    except Exception as e:
        # 出错时也返回缓存
        if _picks_cache["data"]:
            print(f"[picks] AI 调用失败 ({e})，返回缓存")
            return _picks_cache["data"]
        return [{"symbol": "error", "name": str(e), "price": 0, "confidence": 0, "reason": "AI选股临时不可用"}]


# ── API: AI 智能推荐（不受资金限制） ──
@app.get("/api/recommendations")
def api_recommendations(budget: Optional[float] = None):
    """AI 智能推荐：budget 为可用资金（元），None 表示不限"""
    try:
        all_stocks = fetch_all_stocks()
        if not all_stocks:
            return []
        recommendations = ai_recommend_stocks(all_stocks, budget=budget)
        if not recommendations:
            return []
        # 获取推荐股票的实时行情
        result = []
        for r in recommendations:
            symbol = r.get("symbol", "")
            quote = fetch_quote(symbol) if symbol else None
            result.append({
                "symbol": symbol,
                "name": r.get("name", ""),
                "price": quote["price"] if quote else r.get("entry_price", 0),
                "pct": quote.get("pct", 0) if quote else 0,
                "confidence": r.get("confidence", 0),
                "reason": r.get("reason", "")[:50],
                "reason_detail": r.get("reason_detail", ""),
                "kind": r.get("kind", "stock"),
                "stop_loss": r.get("stop_loss", ""),
                "target_price": r.get("target_price", ""),
                # 财务字段从 enriched 数据中获取（如果有）
                "pe": r.get("pe"),
                "pb": r.get("pb"),
                "net_profit_yoy": r.get("net_profit_yoy"),
                "revenue_yoy": r.get("revenue_yoy"),
            })
        return result
    except Exception as e:
        add_realtime_log("error", f"AI推荐接口异常: {e}")
        return []


# ── API: 宠物数据 ──
@app.get("/api/pet-stats")
def api_pet_stats():
    """返回仓鼠宠物所需的数据：当日盈亏、累计盈利、交易胜率"""
    try:
        with SessionLocal() as db:
            acct = get_account(db)
            equity, positions = calc_current_equity(db)

            # 累计已实现盈亏（所有已平仓交易）
            all_trades = db.query(TradeModel).all()
            realized_pnl = sum(t.realized_pnl or 0 for t in all_trades)

            # 累计未实现盈亏（当前持仓浮盈浮亏）
            unrealized_pnl = sum(p.get("unrealized", 0) for p in positions)

            # 累计总盈利
            total_pnl = equity - acct.initial_cash

            # 当日已实现盈亏（今天的交易）
            today = beijing_now().date()
            today_trades = [t for t in all_trades if t.time and t.time.date() == today]
            today_realized = sum(t.realized_pnl or 0 for t in today_trades)

            # 当日总盈亏 = 今日已实现 + 当前持仓浮盈
            today_pnl = today_realized + unrealized_pnl

            # 交易胜率
            sell_trades = [t for t in all_trades if t.side == "sell" and t.realized_pnl is not None]
            wins = sum(1 for t in sell_trades if t.realized_pnl > 0)
            win_rate = round(wins / len(sell_trades) * 100, 1) if sell_trades else 0

            return {
                "today_pnl": round(today_pnl, 2),
                "total_pnl": round(total_pnl, 2),
                "realized_pnl": round(realized_pnl, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "win_rate": win_rate,
                "total_trades": len(sell_trades),
                "wins": wins,
                "equity": round(equity, 2),
                "initial_cash": acct.initial_cash,
                "positions_count": len(positions),
            }
    except Exception as e:
        return {
            "today_pnl": 0, "total_pnl": 0, "realized_pnl": 0,
            "unrealized_pnl": 0, "win_rate": 0, "total_trades": 0,
            "wins": 0, "equity": 10000, "initial_cash": 10000,
            "positions_count": 0, "error": str(e)
        }


def main():
    port = int(os.environ.get("PORT", 8080))
    db_label = "SQLite" if DB_TYPE == "sqlite" else f"MySQL ({DB_HOST}:{DB_PORT}/{DB_NAME})"
    ai_label = "✅ 已配置" if DEEPSEEK_API_KEY else "❌ 未配置（AI功能不可用）"
    print(f"\n{'═'*50}")
    print(f"  A股全自动智能交易系统")
    print(f"  {'═'*50}")
    print(f"  地址: http://127.0.0.1:{port}")
    print(f"  数据库: {db_label}")
    print(f"  AI引擎: {ai_label}")
    print(f"")
    print(f"  ⚡ 启动后系统自动运行，无需任何操作")
    print(f"  你只需要打开浏览器查看交易情况即可")
    print(f"  {'═'*50}")
    print(f"")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

if __name__ == "__main__":
    main()
