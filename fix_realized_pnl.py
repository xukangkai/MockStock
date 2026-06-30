#!/usr/bin/env python3
"""一次性彻底修复：按交易顺序正确匹配 lot → 加入买入手续费 → 重算 realized_pnl。"""
import sys
sys.path.insert(0, ".")
from web_app import TradeModel, LotModel, SessionLocal, fee_for_trade

INITIAL_CASH = 10000.0

def fix():
    with SessionLocal() as db:
        trades = db.query(TradeModel).order_by(TradeModel.id).all()
        lots = db.query(LotModel).order_by(LotModel.id).all()
        if not trades:
            print("没有交易记录"); return

        # ── 1. 按交易顺序给 buy 交易编号，与 lot 一一对应 ──
        # lot 按 id 排序，buy 交易按时间排序，同 symbol 的应该一一对应
        from collections import defaultdict
        buy_queue = defaultdict(list)  # symbol -> [trade, ...]
        for t in trades:
            if t.side == "buy":
                buy_queue[t.symbol].append(t)

        # 计算每个 lot 的含手续费价格
        lot_fee_price = {}
        lot_original_price = {}
        for lot in lots:
            queue = buy_queue[lot.symbol]
            # 找到与该 lot 匹配的 buy 交易（按顺序消耗）
            matched = None
            for i, bt in enumerate(queue):
                if bt.qty == lot.qty:
                    matched = queue.pop(i)
                    break
            if not matched:
                # 回退：取队列第一个
                matched = queue.pop(0) if queue else None

            if matched:
                is_etf = "ETF" in (matched.name or "")
                buy_fee = fee_for_trade(matched.gross, "buy", is_etf=is_etf)
                lot_original_price[lot.id] = matched.price
                lot_fee_price[lot.id] = round(matched.price + buy_fee / matched.qty, 4)
                if abs(lot.price - lot_fee_price[lot.id]) > 0.0001:
                    print(f"  lot #{lot.id} {lot.symbol} {lot.qty}股: {lot.price} → {lot_fee_price[lot.id]} (buy@{matched.price})")
                    lot.price = lot_fee_price[lot.id]
            else:
                lot_fee_price[lot.id] = lot.price
                lot_original_price[lot.id] = lot.price

        db.flush()

        # ── 2. 按 FIFO 重算 realized_pnl ──
        remaining = {lot.id: lot.qty for lot in lots}
        trade_fixed = 0

        for t in trades:
            if t.side != "sell":
                continue
            sym_lots = [l for l in lots if l.symbol == t.symbol]
            qty_left = t.qty
            cost_basis = 0.0
            for lot in sym_lots:
                if qty_left <= 0:
                    break
                rem = remaining.get(lot.id, 0)
                if rem <= 0:
                    continue
                take = min(rem, qty_left)
                remaining[lot.id] = rem - take
                qty_left -= take
                cost_basis += take * lot_fee_price[lot.id]

            proceeds = t.gross - t.fee
            new_pnl = round(proceeds - cost_basis, 2)

            if abs(new_pnl - (t.realized_pnl or 0)) > 0.01:
                old = t.realized_pnl
                print(f"  #{t.id} {t.name} {t.qty}股: {old} → {new_pnl}")
                t.realized_pnl = new_pnl
                trade_fixed += 1

        db.commit()
        print(f"\n✅ 已修复 {trade_fixed} 条 trade")

        # ── 3. 验证 ──
        all_trades = db.query(TradeModel).order_by(TradeModel.id).all()
        sell_trades = [t for t in all_trades if t.side == "sell" and t.realized_pnl is not None]
        total_pnl = sum(t.realized_pnl for t in sell_trades)
        cash_change = all_trades[-1].cash_after - INITIAL_CASH
        print(f"\n验证:")
        print(f"  累计已实现盈亏: ¥{total_pnl:.2f}")
        print(f"  实际现金变动:   ¥{cash_change:.2f}")
        if abs(total_pnl - cash_change) < 1:
            print("  ✅ 两者一致，修复成功！")
        else:
            print(f"  ⚠️ 差额: ¥{total_pnl - cash_change:.2f}")

if __name__ == "__main__":
    fix()
