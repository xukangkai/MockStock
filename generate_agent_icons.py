#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股交易Agent拟人化图标生成器
生成3种风格 × 7个Agent = 21套 SVG矢量图标 + PNG位图(64/128/256)
"""
import os
import math

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "agents")
STYLES = ["styleA_cartoon", "styleB_professional", "styleC_cyberpunk"]

# ── 7个Agent的核心定义 ──────────────────────────────────────────────────
AGENTS = [
    {"key": "commander",   "name": "总指挥",    "primary": "#6366f1", "secondary": "#8b5cf6",
     "feature": "target",   "pose": "pointing",  "emotion": "confident"},
    {"key": "memory",      "name": "记忆检索",  "primary": "#6366f1", "secondary": "#8b5cf6",
     "feature": "book",     "pose": "thinking",  "emotion": "wise"},
    {"key": "market",      "name": "市场分析",  "primary": "#3b82f6", "secondary": "#06b6d4",
     "feature": "chart",    "pose": "presenting","emotion": "focused"},
    {"key": "position",    "name": "持仓审查",  "primary": "#f59e0b", "secondary": "#ef4444",
     "feature": "briefcase","pose": "holding",   "emotion": "serious"},
    {"key": "researcher",  "name": "候选筛选",  "primary": "#10b981", "secondary": "#14b8a6",
     "feature": "magnifier","pose": "searching", "emotion": "curious"},
    {"key": "risk",        "name": "风险评估",  "primary": "#ef4444", "secondary": "#f97316",
     "feature": "shield",   "pose": "protecting","emotion": "stern"},
    {"key": "synthesizer", "name": "决策合成",  "primary": "#8b5cf6", "secondary": "#ec4899",
     "feature": "sparkles", "pose": "creating",  "emotion": "inspired"},
]

# ═══════════════════════════════════════════════════════════════════════
#  风格 A：Q版卡通风 —— 大头圆脸、可爱表情、柔和色彩
# ═══════════════════════════════════════════════════════════════════════
def svg_styleA(a):
    p, s = a["primary"], a["secondary"]
    feat = a["feature"]
    emo  = a["emotion"]

    # 表情曲线
    if emo in ("confident", "inspired", "focused"):
        mouth = '<path d="M88 122 Q100 132 112 122" stroke="#1e293b" stroke-width="3" fill="none" stroke-linecap="round"/>'
        eyes  = '<ellipse cx="88" cy="102" rx="5" ry="7" fill="#1e293b"/><ellipse cx="112" cy="102" rx="5" ry="7" fill="#1e293b"/><circle cx="90" cy="100" r="1.8" fill="#fff"/><circle cx="114" cy="100" r="1.8" fill="#fff"/>'
    elif emo in ("wise", "curious"):
        mouth = '<path d="M90 124 Q100 130 110 124" stroke="#1e293b" stroke-width="2.5" fill="none" stroke-linecap="round"/>'
        eyes  = '<path d="M83 102 Q88 98 93 102" stroke="#1e293b" stroke-width="3" fill="none" stroke-linecap="round"/><path d="M107 102 Q112 98 117 102" stroke="#1e293b" stroke-width="3" fill="none" stroke-linecap="round"/>'
    elif emo in ("serious", "stern"):
        mouth = '<path d="M88 125 L112 125" stroke="#1e293b" stroke-width="3" fill="none" stroke-linecap="round"/>'
        eyes  = '<path d="M82 99 L94 104" stroke="#1e293b" stroke-width="2.5" stroke-linecap="round"/><path d="M118 99 L106 104" stroke="#1e293b" stroke-width="2.5" stroke-linecap="round"/><ellipse cx="88" cy="108" rx="4" ry="5" fill="#1e293b"/><ellipse cx="112" cy="108" rx="4" ry="5" fill="#1e293b"/>'
    else:
        mouth = '<path d="M90 124 Q100 130 110 124" stroke="#1e293b" stroke-width="2.5" fill="none" stroke-linecap="round"/>'
        eyes  = '<ellipse cx="88" cy="104" rx="4" ry="5" fill="#1e293b"/><ellipse cx="112" cy="104" rx="4" ry="5" fill="#1e293b"/>'

    # 腮红（Q版特征）
    blush = '<circle cx="78" cy="118" r="6" fill="#fca5a5" opacity="0.55"/><circle cx="122" cy="118" r="6" fill="#fca5a5" opacity="0.55"/>'

    # 特征道具
    if feat == "target":
        feature_item = '''
        <g transform="translate(140,40) rotate(12)">
          <circle cx="0" cy="0" r="22" fill="#fff" stroke="{}" stroke-width="3"/>
          <circle cx="0" cy="0" r="15" fill="none" stroke="{}" stroke-width="2.5"/>
          <circle cx="0" cy="0" r="8" fill="{}"/>
          <path d="M0 -22 L0 -32 M22 0 L32 0 M0 22 L0 32 M-22 0 L-32 0" stroke="{}" stroke-width="3" stroke-linecap="round"/>
        </g>'''.format(p, p, s, p)
    elif feat == "book":
        feature_item = '''
        <g transform="translate(38,150) rotate(-8)">
          <rect x="0" y="0" width="36" height="28" rx="3" fill="{}"/>
          <rect x="3" y="3" width="30" height="22" rx="1" fill="#fff8e7"/>
          <line x1="18" y1="3" x2="18" y2="25" stroke="{}" stroke-width="1.5" opacity="0.4"/>
          <line x1="5" y1="9" x2="16" y2="9" stroke="{}" stroke-width="1.2" opacity="0.4"/>
          <line x1="5" y1="14" x2="16" y2="14" stroke="{}" stroke-width="1.2" opacity="0.4"/>
          <line x1="20" y1="9" x2="31" y2="9" stroke="{}" stroke-width="1.2" opacity="0.4"/>
          <line x1="20" y1="14" x2="31" y2="14" stroke="{}" stroke-width="1.2" opacity="0.4"/>
        </g>'''.format(p, p, p, p, p, p)
    elif feat == "chart":
        feature_item = '''
        <g transform="translate(140,152) rotate(6)">
          <rect x="0" y="0" width="36" height="28" rx="3" fill="#fff" stroke="{}" stroke-width="2"/>
          <polyline points="4,22 11,14 17,18 24,7 32,11" stroke="{}" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="4" cy="22" r="1.8" fill="{}"/>
          <circle cx="11" cy="14" r="1.8" fill="{}"/>
          <circle cx="17" cy="18" r="1.8" fill="{}"/>
          <circle cx="24" cy="7"  r="1.8" fill="{}"/>
          <circle cx="32" cy="11" r="1.8" fill="{}"/>
        </g>'''.format(p, s, s, s, s, s, s)
    elif feat == "briefcase":
        feature_item = '''
        <g transform="translate(38,148) rotate(-10)">
          <rect x="4" y="8" width="36" height="26" rx="3" fill="{}"/>
          <rect x="4" y="8" width="36" height="6" rx="2" fill="{}"/>
          <path d="M16 8 V3 H28 V8" stroke="{}" stroke-width="3" fill="none" stroke-linecap="round"/>
          <rect x="19" y="17" width="6" height="6" rx="1" fill="#fff2cc"/>
        </g>'''.format(p, s, p)
    elif feat == "magnifier":
        feature_item = '''
        <g transform="translate(138,44) rotate(25)">
          <circle cx="0" cy="0" r="16" fill="#fff" stroke="{}" stroke-width="3.5"/>
          <circle cx="0" cy="0" r="11" fill="{}" opacity="0.15"/>
          <line x1="11" y1="11" x2="23" y2="23" stroke="{}" stroke-width="4" stroke-linecap="round"/>
          <circle cx="-3" cy="-3" r="4" fill="#fff" opacity="0.7"/>
        </g>'''.format(p, s, p)
    elif feat == "shield":
        feature_item = '''
        <g transform="translate(35,44) rotate(-10)">
          <path d="M0 0 L30 0 L30 18 Q30 34 15 42 Q0 34 0 18 Z" fill="{}"/>
          <path d="M5 4 L25 4 L25 18 Q25 30 15 37 Q5 30 5 18 Z" fill="{}" opacity="0.35"/>
          <path d="M8 16 L14 22 L24 10" stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
        </g>'''.format(p, s)
    else:  # sparkles
        feature_item = '''
        <g transform="translate(142,38)">
          <path d="M0 0 L3 -9 L6 0 L15 3 L6 6 L3 15 L0 6 L-9 3 Z" fill="{}"/>
          <g transform="translate(-18,20) scale(0.6)">
            <path d="M0 0 L3 -9 L6 0 L15 3 L6 6 L3 15 L0 6 L-9 3 Z" fill="{}"/>
          </g>
          <g transform="translate(10,24) scale(0.45)">
            <path d="M0 0 L3 -9 L6 0 L15 3 L6 6 L3 15 L0 6 L-9 3 Z" fill="{}"/>
          </g>
        </g>'''.format(p, s, p)

    # 头发（Q版短发）
    hair = '<path d="M60 72 Q60 42 100 42 Q140 42 140 72 Q140 62 130 58 Q118 52 100 52 Q82 52 70 58 Q60 62 60 72 Z" fill="{}"/>'.format(p)

    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">
  <defs>
    <linearGradient id="bg{key}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{p}"/>
      <stop offset="100%" stop-color="{s}"/>
    </linearGradient>
    <radialGradient id="face{key}" cx="0.5" cy="0.4" r="0.6">
      <stop offset="0%" stop-color="#ffe8d6"/>
      <stop offset="100%" stop-color="#ffd4b8"/>
    </radialGradient>
  </defs>
  <!-- 背景圆 -->
  <circle cx="100" cy="100" r="96" fill="url(#bg{key})" opacity="0.14"/>
  <circle cx="100" cy="100" r="90" fill="url(#bg{key})" opacity="0.08"/>
  <!-- 身体（Q版小身子） -->
  <path d="M68 158 Q66 180 100 180 Q134 180 132 158 Q126 164 100 166 Q74 164 68 158 Z" fill="url(#bg{key})"/>
  <path d="M76 158 Q76 172 100 172 Q124 172 124 158 Q120 162 100 163 Q80 162 76 158 Z" fill="#fff" opacity="0.2"/>
  <!-- 脖子 -->
  <rect x="92" y="140" width="16" height="18" rx="5" fill="#ffd4b8"/>
  <!-- 头 -->
  <ellipse cx="100" cy="100" rx="44" ry="46" fill="url(#face{key})" stroke="{p}" stroke-width="2.5"/>
  <!-- 头发 -->
  {hair}
  <!-- 耳朵 -->
  <ellipse cx="57" cy="106" rx="6" ry="9" fill="#ffd4b8" stroke="{p}" stroke-width="1.5"/>
  <ellipse cx="143" cy="106" rx="6" ry="9" fill="#ffd4b8" stroke="{p}" stroke-width="1.5"/>
  <!-- 腮红 -->
  {blush}
  <!-- 眼睛 -->
  {eyes}
  <!-- 嘴巴 -->
  {mouth}
  <!-- 特征道具 -->
  {feature_item}
</svg>'''.format(key=a["key"], p=p, s=s, hair=hair, blush=blush, eyes=eyes, mouth=mouth, feature_item=feature_item)


# ═══════════════════════════════════════════════════════════════════════
#  风格 B：专业商务风 —— 西装领结、职业姿态、稳健比例
# ═══════════════════════════════════════════════════════════════════════
def svg_styleB(a):
    p, s = a["primary"], a["secondary"]
    feat = a["feature"]
    emo  = a["emotion"]

    # 表情
    if emo in ("confident", "inspired"):
        mouth = '<path d="M84 120 Q100 132 116 120" stroke="#1e293b" stroke-width="2.5" fill="none" stroke-linecap="round"/>'
        eyes  = '<path d="M78 99 Q85 95 92 99" stroke="#1e293b" stroke-width="2.2" fill="none" stroke-linecap="round"/><path d="M108 99 Q115 95 122 99" stroke="#1e293b" stroke-width="2.2" fill="none" stroke-linecap="round"/>'
    elif emo in ("wise", "focused"):
        mouth = '<path d="M86 121 Q100 128 114 121" stroke="#1e293b" stroke-width="2" fill="none" stroke-linecap="round"/>'
        eyes  = '<ellipse cx="85" cy="100" rx="3.5" ry="4.5" fill="#1e293b"/><ellipse cx="115" cy="100" rx="3.5" ry="4.5" fill="#1e293b"/><rect x="76" y="90" width="18" height="3" rx="1" fill="#334155" opacity="0.8"/><rect x="106" y="90" width="18" height="3" rx="1" fill="#334155" opacity="0.8"/><line x1="94" y1="91.5" x2="106" y2="91.5" stroke="#334155" stroke-width="1.5" opacity="0.6"/>'
    elif emo in ("serious", "stern"):
        mouth = '<path d="M86 123 L114 123" stroke="#1e293b" stroke-width="2.5" fill="none" stroke-linecap="round"/>'
        eyes  = '<path d="M77 92 L92 97" stroke="#1e293b" stroke-width="2" stroke-linecap="round"/><path d="M123 92 L108 97" stroke="#1e293b" stroke-width="2" stroke-linecap="round"/><ellipse cx="85" cy="104" rx="3" ry="4" fill="#1e293b"/><ellipse cx="115" cy="104" rx="3" ry="4" fill="#1e293b"/>'
    else:  # curious
        mouth = '<path d="M92 122 Q100 128 108 122" stroke="#1e293b" stroke-width="2" fill="none" stroke-linecap="round"/>'
        eyes  = '<circle cx="85" cy="101" r="4" fill="#1e293b"/><circle cx="115" cy="101" r="4" fill="#1e293b"/><circle cx="86" cy="99.5" r="1.2" fill="#fff"/><circle cx="116" cy="99.5" r="1.2" fill="#fff"/>'

    # 头发（商务发型）
    hair = '''<path d="M58 74 Q58 48 100 46 Q142 48 142 74 Q142 64 132 60 Q118 54 100 54 Q82 54 68 60 Q58 64 58 74 Z" fill="#1e293b"/>
             <path d="M62 66 Q84 56 128 58 L136 54 Q120 48 100 50 Q76 50 62 66 Z" fill="#334155" opacity="0.6"/>'''

    # 西装+领带
    suit = '''
    <!-- 西装外套 -->
    <path d="M56 160 L48 192 L90 192 L80 170 L100 158 L120 170 L110 192 L152 192 L144 160 Z" fill="{}"/>
    <!-- 衬衫领 -->
    <path d="M82 158 L100 172 L118 158 L114 170 L100 177 L86 170 Z" fill="#f8fafc"/>
    <!-- 领带 -->
    <path d="M96 172 L104 172 L108 188 L100 196 L92 188 Z" fill="{}"/>
    <rect x="95.5" y="168" width="9" height="8" rx="1" fill="{}"/>
    <!-- 西装翻领 -->
    <path d="M56 160 L82 158 L76 186 L50 192 Z" fill="{}" opacity="0.35"/>
    <path d="M144 160 L118 158 L124 186 L150 192 Z" fill="{}" opacity="0.35"/>
    <!-- 西装扣 -->
    <circle cx="100" cy="184" r="1.8" fill="#1e293b" opacity="0.6"/>
    '''.format(p, s, s, p, p)

    # 特征道具（更精致商务版）
    if feat == "target":
        feature_item = '''
        <g transform="translate(150,52) scale(0.78)">
          <circle cx="0" cy="0" r="26" fill="#fff" stroke="{}" stroke-width="3.5"/>
          <circle cx="0" cy="0" r="18" fill="none" stroke="{}" stroke-width="2.5"/>
          <circle cx="0" cy="0" r="10" fill="none" stroke="{}" stroke-width="2.5"/>
          <circle cx="0" cy="0" r="4" fill="{}"/>
          <path d="M0 -26 L0 -36 M26 0 L36 0 M0 26 L0 36 M-26 0 L-36 0" stroke="{}" stroke-width="3" stroke-linecap="round"/>
        </g>'''.format(p, p, p, s, p)
    elif feat == "book":
        feature_item = '''
        <g transform="translate(30,158) scale(0.9)">
          <rect x="0" y="0" width="32" height="28" rx="2" fill="{}"/>
          <rect x="3" y="3" width="26" height="22" fill="#fefcf7"/>
          <line x1="16" y1="3" x2="16" y2="25" stroke="{}" stroke-width="1" opacity="0.5"/>
          <path d="M6 10 L13 10 M6 14 L13 14 M19 10 L26 10 M19 14 L26 14" stroke="{}" stroke-width="1" opacity="0.5"/>
          <path d="M28 2 L32 6 V28 H28 Z" fill="{}" opacity="0.8"/>
        </g>'''.format(p, p, p, s)
    elif feat == "chart":
        feature_item = '''
        <g transform="translate(148,154) scale(0.85)">
          <rect x="0" y="0" width="44" height="32" rx="3" fill="#fff" stroke="{}" stroke-width="2"/>
          <line x1="4" y1="26" x2="40" y2="26" stroke="#cbd5e1" stroke-width="1"/>
          <line x1="4" y1="18" x2="40" y2="18" stroke="#e2e8f0" stroke-width="1"/>
          <line x1="4" y1="10" x2="40" y2="10" stroke="#e2e8f0" stroke-width="1"/>
          <polyline points="5,24 12,17 19,20 26,8 33,13 39,5" stroke="{}" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
          <polygon points="33,13 39,5 39,13" fill="{}" opacity="0.3"/>
        </g>'''.format(p, s, s)
    elif feat == "briefcase":
        feature_item = '''
        <g transform="translate(26,150) scale(0.85)">
          <rect x="4" y="10" width="44" height="32" rx="3" fill="{}"/>
          <rect x="4" y="10" width="44" height="8" rx="2" fill="{}"/>
          <path d="M18 10 V3 H34 V10" stroke="{}" stroke-width="3" fill="none" stroke-linecap="round"/>
          <rect x="22" y="22" width="8" height="8" rx="1" fill="#f1e3b8"/>
          <rect x="24.5" y="24.5" width="3" height="3" rx="0.5" fill="{}"/>
        </g>'''.format(p, s, p, s)
    elif feat == "magnifier":
        feature_item = '''
        <g transform="translate(150,52) scale(0.85) rotate(18)">
          <circle cx="0" cy="0" r="18" fill="#fff" stroke="{}" stroke-width="3.5"/>
          <circle cx="0" cy="0" r="12" fill="{}" opacity="0.22"/>
          <line x1="12.5" y1="12.5" x2="28" y2="28" stroke="{}" stroke-width="5" stroke-linecap="round"/>
          <line x1="12.5" y1="12.5" x2="28" y2="28" stroke="#f1e3b8" stroke-width="2" stroke-linecap="round"/>
        </g>'''.format(p, s, p)
    elif feat == "shield":
        feature_item = '''
        <g transform="translate(26,52) scale(0.85)">
          <path d="M0 0 L34 0 L34 22 Q34 42 17 52 Q0 42 0 22 Z" fill="{}"/>
          <path d="M5 5 L29 5 L29 22 Q29 37 17 46 Q5 37 5 22 Z" fill="{}" opacity="0.4"/>
          <path d="M10 15 L15 22 L26 10" stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M15 22 L15 36" stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round"/>
        </g>'''.format(p, s)
    else:  # sparkles
        feature_item = '''
        <g transform="translate(150,48) scale(0.9)">
          <path d="M0 0 L3 -11 L6 0 L16 3.5 L6 7 L3 18 L0 7 L-10 3.5 Z" fill="{}"/>
          <g transform="translate(-18,22) scale(0.65)">
            <path d="M0 0 L3 -11 L6 0 L16 3.5 L6 7 L3 18 L0 7 L-10 3.5 Z" fill="{}"/>
          </g>
          <g transform="translate(12,28) scale(0.5)">
            <path d="M0 0 L3 -11 L6 0 L16 3.5 L6 7 L3 18 L0 7 L-10 3.5 Z" fill="{}"/>
          </g>
        </g>'''.format(p, s, s)

    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">
  <defs>
    <linearGradient id="bbg{key}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{p}"/>
      <stop offset="100%" stop-color="{s}"/>
    </linearGradient>
    <radialGradient id="bface{key}" cx="0.5" cy="0.4" r="0.6">
      <stop offset="0%" stop-color="#fde8d2"/>
      <stop offset="100%" stop-color="#f1c9a5"/>
    </radialGradient>
  </defs>
  <!-- 背景 -->
  <rect x="2" y="2" width="196" height="196" rx="18" fill="url(#bbg{key})" opacity="0.1"/>
  <rect x="6" y="6" width="188" height="188" rx="15" fill="url(#bbg{key})" opacity="0.06"/>
  <!-- 西装 -->
  {suit}
  <!-- 脖子 -->
  <rect x="93" y="140" width="14" height="20" rx="4" fill="#f1c9a5"/>
  <!-- 头部 -->
  <ellipse cx="100" cy="100" rx="42" ry="44" fill="url(#bface{key})" stroke="{p}" stroke-width="2.2" opacity="0.85"/>
  <!-- 头发 -->
  {hair}
  <!-- 耳朵 -->
  <ellipse cx="59" cy="105" rx="5" ry="8" fill="#f1c9a5"/>
  <ellipse cx="141" cy="105" rx="5" ry="8" fill="#f1c9a5"/>
  <!-- 眼睛 -->
  {eyes}
  <!-- 嘴巴 -->
  {mouth}
  <!-- 特征道具 -->
  {feature_item}
</svg>'''.format(key=a["key"], p=p, s=s, hair=hair, eyes=eyes, mouth=mouth, suit=suit, feature_item=feature_item)


# ═══════════════════════════════════════════════════════════════════════
#  风格 C：赛博科技风 —— 霓虹光晕、电路纹路、机械部件
#  使用 __P__ / __S__ / __K__ 三重 token 替换，避免 format 索引越界
# ═══════════════════════════════════════════════════════════════════════
def _cyber_replace(text, p, s, k):
    return text.replace("__P__", p).replace("__S__", s).replace("__K__", k)

def svg_styleC(a):
    p, s, k = a["primary"], a["secondary"], a["key"]
    feat = a["feature"]
    emo  = a["emotion"]

    # 发光眼睛（赛博风）
    if emo in ("confident", "inspired"):
        mouth = '<path d="M84 120 Q100 130 116 120" stroke="__P__" stroke-width="2.5" fill="none" stroke-linecap="round" filter="url(#glow__K__)"/>'
        eyes  = '<ellipse cx="86" cy="100" rx="8" ry="4" fill="none" stroke="__P__" stroke-width="1.5" opacity="0.5"/><ellipse cx="114" cy="100" rx="8" ry="4" fill="none" stroke="__S__" stroke-width="1.5" opacity="0.5"/><ellipse cx="86" cy="100" rx="4" ry="3" fill="__P__" filter="url(#glow__K__)"/><ellipse cx="114" cy="100" rx="4" ry="3" fill="__P__" filter="url(#glow__K__)"/>'
    elif emo in ("wise", "focused"):
        mouth = '<path d="M86 122 Q100 128 114 122" stroke="__P__" stroke-width="2" fill="none" stroke-linecap="round"/>'
        eyes  = '<rect x="76" y="94" width="22" height="14" rx="3" fill="none" stroke="__P__" stroke-width="1.8"/><rect x="102" y="94" width="22" height="14" rx="3" fill="none" stroke="__P__" stroke-width="1.8"/><line x1="98" y1="94" x2="102" y2="94" stroke="__P__" stroke-width="1.2"/><ellipse cx="87" cy="101" rx="3.5" ry="3" fill="__P__" filter="url(#glow__K__)"/><ellipse cx="113" cy="101" rx="3.5" ry="3" fill="__P__" filter="url(#glow__K__)"/>'
    elif emo in ("serious", "stern"):
        mouth = '<path d="M86 124 L114 124" stroke="__P__" stroke-width="2.5" fill="none" stroke-linecap="round"/>'
        eyes  = '<path d="M76 93 L93 98" stroke="__P__" stroke-width="2" stroke-linecap="round"/><path d="M124 93 L107 98" stroke="__P__" stroke-width="2" stroke-linecap="round"/><rect x="78" y="100" width="16" height="10" rx="2" fill="none" stroke="__S__" stroke-width="1.5"/><rect x="106" y="100" width="16" height="10" rx="2" fill="none" stroke="__S__" stroke-width="1.5"/><ellipse cx="86" cy="105" rx="3" ry="2.5" fill="__P__" filter="url(#glow__K__)"/><ellipse cx="114" cy="105" rx="3" ry="2.5" fill="__P__" filter="url(#glow__K__)"/>'
    else:
        mouth = '<path d="M92 122 Q100 128 108 122" stroke="__P__" stroke-width="2" fill="none"/>'
        eyes  = '<circle cx="86" cy="101" r="5" fill="none" stroke="__P__" stroke-width="1.5" opacity="0.5"/><circle cx="114" cy="101" r="5" fill="none" stroke="__S__" stroke-width="1.5" opacity="0.5"/><circle cx="86" cy="101" r="3" fill="__P__" filter="url(#glow__K__)"/><circle cx="114" cy="101" r="3" fill="__P__" filter="url(#glow__K__)"/>'

    # 赛博机械头发/头盔
    hair = '''
    <path d="M58 74 Q58 44 100 42 Q142 44 142 74 Q142 62 128 58 Q118 52 100 52 Q82 52 72 58 Q58 62 58 74 Z" fill="#0f172a" stroke="__P__" stroke-width="2"/>
    <path d="M70 58 Q82 50 100 50 Q118 50 130 58" stroke="__S__" stroke-width="1.5" fill="none" opacity="0.7"/>
    <path d="M60 70 L68 62 M140 70 L132 62" stroke="__P__" stroke-width="1" opacity="0.8"/>
    <circle cx="64" cy="66" r="1.2" fill="__S__" filter="url(#glow__K__)"/>
    <circle cx="136" cy="66" r="1.2" fill="__S__" filter="url(#glow__K__)"/>
    <rect x="96" y="46" width="8" height="4" rx="1" fill="__P__" opacity="0.9"/>'''

    # 机械身体
    body = '''
    <path d="M58 158 Q50 180 50 196 L78 196 L74 174 L100 162 L126 174 L122 196 L150 196 Q150 180 142 158 Q128 166 100 168 Q72 166 58 158 Z" fill="#0f172a" stroke="__P__" stroke-width="2"/>
    <path d="M68 160 Q70 180 100 184 Q130 180 132 160 Q120 168 100 170 Q80 168 68 160 Z" fill="__S__" opacity="0.35" stroke="__P__" stroke-width="1.2"/>
    <circle cx="100" cy="176" r="5" fill="__S__" filter="url(#glow__K__)"/>
    <circle cx="100" cy="176" r="9" fill="none" stroke="__P__" stroke-width="1" opacity="0.6"/>
    <path d="M60 168 L72 168 L72 180 M140 168 L128 168 L128 180" stroke="__P__" stroke-width="1" fill="none" opacity="0.7"/>
    <circle cx="60" cy="168" r="1" fill="__P__" filter="url(#glow__K__)"/>
    <circle cx="140" cy="168" r="1" fill="__P__" filter="url(#glow__K__)"/>
    <rect x="90" y="140" width="20" height="20" rx="3" fill="#1e293b" stroke="__P__" stroke-width="1.5"/>
    <line x1="100" y1="140" x2="100" y2="160" stroke="__P__" stroke-width="1" opacity="0.5"/>'''

    # 赛博道具（机械+发光版）
    if feat == "target":
        feature_item = '''
        <g transform="translate(150,54) scale(0.8) rotate(10)">
          <circle cx="0" cy="0" r="24" fill="#0f172a" stroke="__P__" stroke-width="3"/>
          <circle cx="0" cy="0" r="16" fill="none" stroke="__S__" stroke-width="2.5"/>
          <circle cx="0" cy="0" r="8" fill="__S__" filter="url(#glow__K__)"/>
          <path d="M0 -24 L0 -34 M24 0 L34 0 M0 24 L0 34 M-24 0 L-34 0" stroke="__P__" stroke-width="2.5" stroke-linecap="round"/>
          <circle cx="0" cy="-34" r="1.8" fill="__S__" filter="url(#glow__K__)"/>
          <circle cx="34" cy="0" r="1.8" fill="__S__" filter="url(#glow__K__)"/>
        </g>'''
    elif feat == "book":
        feature_item = '''
        <g transform="translate(32,158) scale(0.85) rotate(-8)">
          <rect x="0" y="0" width="34" height="28" rx="2" fill="#0f172a" stroke="__P__" stroke-width="2"/>
          <rect x="3" y="3" width="28" height="22" fill="#0b1220"/>
          <line x1="6" y1="10" x2="15" y2="10" stroke="__S__" stroke-width="1.5" filter="url(#glow__K__)"/>
          <line x1="6" y1="15" x2="18" y2="15" stroke="__S__" stroke-width="1.5" filter="url(#glow__K__)"/>
          <line x1="19" y1="10" x2="28" y2="10" stroke="__S__" stroke-width="1.5" filter="url(#glow__K__)"/>
          <line x1="19" y1="15" x2="25" y2="15" stroke="__S__" stroke-width="1.5" filter="url(#glow__K__)"/>
          <rect x="15.5" y="1" width="3" height="26" fill="__P__" opacity="0.7"/>
        </g>'''
    elif feat == "chart":
        feature_item = '''
        <g transform="translate(148,154) scale(0.82)">
          <rect x="0" y="0" width="46" height="32" rx="3" fill="#0f172a" stroke="__P__" stroke-width="2"/>
          <line x1="6"  y1="24" x2="6"  y2="14" stroke="__S__" stroke-width="2" filter="url(#glow__K__)"/>
          <line x1="15" y1="22" x2="15" y2="18" stroke="__S__" stroke-width="2"/>
          <line x1="24" y1="26" x2="24" y2="10" stroke="__S__" stroke-width="2" filter="url(#glow__K__)"/>
          <line x1="33" y1="18" x2="33" y2="6"  stroke="__S__" stroke-width="2" filter="url(#glow__K__)"/>
          <line x1="42" y1="12" x2="42" y2="20" stroke="#ef4444" stroke-width="2" filter="url(#glow__K__)"/>
          <rect x="3"  y1="18" width="6"  height="6" fill="__P__" opacity="0.4"/>
          <rect x="21" y1="18" width="6"  height="8" fill="__P__" opacity="0.4"/>
          <rect x="30" y1="12" width="6"  height="6" fill="__S__" opacity="0.5" filter="url(#glow__K__)"/>
        </g>'''
    elif feat == "briefcase":
        feature_item = '''
        <g transform="translate(28,152) scale(0.82) rotate(-6)">
          <rect x="4" y="10" width="44" height="32" rx="3" fill="#0f172a" stroke="__P__" stroke-width="2"/>
          <rect x="4" y="10" width="44" height="8" rx="2" fill="#1e293b" stroke="__P__" stroke-width="1.5"/>
          <path d="M18 10 V4 H34 V10" stroke="__P__" stroke-width="3" fill="none" stroke-linecap="round"/>
          <rect x="22" y="22" width="8" height="8" rx="1" fill="none" stroke="__S__" stroke-width="1.5"/>
          <circle cx="26" cy="26" r="1.5" fill="__S__" filter="url(#glow__K__)"/>
          <line x1="10" y1="30" x2="42" y2="30" stroke="__P__" stroke-width="1" opacity="0.5"/>
        </g>'''
    elif feat == "magnifier":
        feature_item = '''
        <g transform="translate(150,52) scale(0.85) rotate(20)">
          <circle cx="0" cy="0" r="18" fill="#0f172a" stroke="__P__" stroke-width="3.5"/>
          <circle cx="0" cy="0" r="12" fill="__S__" opacity="0.2"/>
          <path d="M-11 5 A12 12 0 0 1 11 -5" stroke="__P__" stroke-width="2" fill="none" filter="url(#glow__K__)"/>
          <line x1="13" y1="13" x2="30" y2="30" stroke="__P__" stroke-width="5" stroke-linecap="round"/>
          <line x1="13" y1="13" x2="30" y2="30" stroke="__S__" stroke-width="2" stroke-linecap="round" opacity="0.7"/>
        </g>'''
    elif feat == "shield":
        feature_item = '''
        <g transform="translate(26,52) scale(0.85)">
          <path d="M0 0 L34 0 L34 22 Q34 42 17 52 Q0 42 0 22 Z" fill="#0f172a" stroke="__P__" stroke-width="2.5"/>
          <path d="M5 5 L29 5 L29 22 Q29 37 17 46 Q5 37 5 22 Z" fill="none" stroke="__P__" stroke-width="1.2" opacity="0.7"/>
          <path d="M10 15 L15 22 L26 10" stroke="__S__" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round" filter="url(#glow__K__)"/>
          <path d="M15 22 L15 36" stroke="__S__" stroke-width="3" fill="none" stroke-linecap="round" filter="url(#glow__K__)"/>
          <circle cx="17" cy="8" r="1.5" fill="__S__" filter="url(#glow__K__)"/>
          <circle cx="8" cy="30" r="1.2" fill="__S__" filter="url(#glow__K__)"/>
          <circle cx="26" cy="30" r="1.2" fill="__S__" filter="url(#glow__K__)"/>
        </g>'''
    else:  # sparkles（赛博能量水晶）
        feature_item = '''
        <g transform="translate(150,50) scale(0.9)">
          <path d="M0 0 L4 -12 L8 0 L18 4 L8 8 L4 20 L0 8 L-12 4 Z" fill="__P__" opacity="0.9" stroke="__S__" stroke-width="1.5" filter="url(#glow__K__)"/>
          <path d="M0 0 L4 -12 L8 0 L0 -3 Z" fill="#fff" opacity="0.35"/>
          <g transform="translate(-20,22) scale(0.65)">
            <path d="M0 0 L4 -12 L8 0 L18 4 L8 8 L4 20 L0 8 L-12 4 Z" fill="__S__" opacity="0.85" stroke="__P__" stroke-width="1.5"/>
          </g>
          <g transform="translate(14,28) scale(0.5)">
            <path d="M0 0 L4 -12 L8 0 L18 4 L8 8 L4 20 L0 8 L-12 4 Z" fill="__S__" opacity="0.75" stroke="__P__" stroke-width="1.2"/>
          </g>
        </g>'''

    # 脸部机械纹路
    face_cyber = '''
    <path d="M62 82 L56 96 L62 110" stroke="__P__" stroke-width="1" fill="none" opacity="0.6"/>
    <path d="M138 82 L144 96 L138 110" stroke="__P__" stroke-width="1" fill="none" opacity="0.6"/>
    <circle cx="58" cy="90" r="1" fill="__S__" filter="url(#glow__K__)"/>
    <circle cx="142" cy="90" r="1" fill="__S__" filter="url(#glow__K__)"/>
    <circle cx="56" cy="114" r="1.4" fill="__S__" filter="url(#glow__K__)"/>
    <circle cx="144" cy="114" r="1.4" fill="__S__" filter="url(#glow__K__)"/>'''

    # 先替换所有子组件中的 token
    mouth = _cyber_replace(mouth, p, s, k)
    eyes  = _cyber_replace(eyes, p, s, k)
    hair  = _cyber_replace(hair, p, s, k)
    body  = _cyber_replace(body, p, s, k)
    feature_item = _cyber_replace(feature_item, p, s, k)
    face_cyber   = _cyber_replace(face_cyber, p, s, k)

    # 主模板
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">
  <defs>
    <linearGradient id="cbg{k}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0b1220"/>
      <stop offset="100%" stop-color="#020617"/>
    </linearGradient>
    <linearGradient id="cface{k}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#e2c4ad"/>
      <stop offset="100%" stop-color="#c79b7a"/>
    </linearGradient>
    <filter id="glow{k}" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="2" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  <!-- 赛博背景 -->
  <rect x="0" y="0" width="200" height="200" rx="18" fill="url(#cbg{k})"/>
  <rect x="4" y="4" width="192" height="192" rx="15" fill="none" stroke="{p}" stroke-width="2" opacity="0.5"/>
  <rect x="8" y="8" width="184" height="184" rx="12" fill="none" stroke="{s}" stroke-width="1" opacity="0.2"/>
  <!-- 四角装饰 -->
  <path d="M14 22 L14 14 L22 14" stroke="{p}" stroke-width="2" fill="none" opacity="0.7"/>
  <path d="M186 22 L186 14 L178 14" stroke="{p}" stroke-width="2" fill="none" opacity="0.7"/>
  <path d="M14 178 L14 186 L22 186" stroke="{p}" stroke-width="2" fill="none" opacity="0.7"/>
  <path d="M186 178 L186 186 L178 186" stroke="{p}" stroke-width="2" fill="none" opacity="0.7"/>
  <!-- 机械身体 -->
  {body}
  <!-- 头部 -->
  <ellipse cx="100" cy="100" rx="42" ry="44" fill="url(#cface{k})" stroke="{p}" stroke-width="2.2"/>
  <!-- 头发/头盔 -->
  {hair}
  <!-- 脸部机械纹路 -->
  {face_cyber}
  <!-- 耳朵（机械） -->
  <ellipse cx="59" cy="105" rx="5" ry="8" fill="none" stroke="{p}" stroke-width="1.5"/>
  <ellipse cx="141" cy="105" rx="5" ry="8" fill="none" stroke="{p}" stroke-width="1.5"/>
  <!-- 眼睛 -->
  {eyes}
  <!-- 嘴巴 -->
  {mouth}
  <!-- 特征道具 -->
  {feature_item}
</svg>'''


# ═══════════════════════════════════════════════════════════════════════
#  主生成流程
# ═══════════════════════════════════════════════════════════════════════
def write_svg(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  ✅ SVG: {os.path.basename(path)}")

def generate_all_svgs():
    print("\n📐 生成 SVG 矢量图标...")
    for a in AGENTS:
        # 风格 A
        p = os.path.join(BASE_DIR, "styleA_cartoon", "svg", f"{a['key']}.svg")
        write_svg(p, svg_styleA(a))
        # 风格 B
        p = os.path.join(BASE_DIR, "styleB_professional", "svg", f"{a['key']}.svg")
        write_svg(p, svg_styleB(a))
        # 风格 C
        p = os.path.join(BASE_DIR, "styleC_cyberpunk", "svg", f"{a['key']}.svg")
        write_svg(p, svg_styleC(a))

def generate_pngs():
    """使用 cairosvg 生成 PNG；如果不可用则回退到 Pillow 占位方案."""
    print("\n🖼️  生成 PNG 位图图标...")
    cairo_ok = False
    try:
        import cairosvg
        for style in STYLES:
            svg_dir = os.path.join(BASE_DIR, style, "svg")
            for a in AGENTS:
                svg_path = os.path.join(svg_dir, f"{a['key']}.svg")
                with open(svg_path, "rb") as f:
                    data = f.read()
                for size, sub in [(64,"png_64"), (128,"png_128"), (256,"png_256")]:
                    out = os.path.join(BASE_DIR, style, sub, f"{a['key']}.png")
                    cairosvg.svg2png(bytestring=data, write_to=out, output_width=size, output_height=size)
        print("  ✅ PNG 图标生成完成 (64/128/256 三种分辨率)")
        cairo_ok = True
        return True
    except Exception as e:
        print(f"  ⚠️  cairosvg 不可用（{type(e).__name__}），尝试 rsvg-convert...")

    if not cairo_ok:
        try:
            import subprocess
            for style in STYLES:
                svg_dir = os.path.join(BASE_DIR, style, "svg")
                for a in AGENTS:
                    svg_path = os.path.join(svg_dir, f"{a['key']}.svg")
                    for size, sub in [(64,"png_64"), (128,"png_128"), (256,"png_256")]:
                        out = os.path.join(BASE_DIR, style, sub, f"{a['key']}.png")
                        subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size),
                                        "-o", out, svg_path], check=True,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("  ✅ PNG 图标生成完成 (64/128/256 三种分辨率)")
            return True
        except Exception as e:
            print(f"  ⚠️  rsvg-convert 不可用（{type(e).__name__}），使用 Pillow 占位方案...")

    try:
        from PIL import Image, ImageDraw
        for style in STYLES:
            for a in AGENTS:
                for size, sub in [(64,"png_64"), (128,"png_128"), (256,"png_256")]:
                    out = os.path.join(BASE_DIR, style, sub, f"{a['key']}.png")
                    # 生成占位渐变图标
                    img = Image.new("RGBA", (size, size), (0,0,0,0))
                    d = ImageDraw.Draw(img)
                    # 背景圆渐变近似
                    p_color = tuple(int(a["primary"].lstrip('#')[i:i+2], 16) for i in (0,2,4))
                    s_color = tuple(int(a["secondary"].lstrip('#')[i:i+2], 16) for i in (0,2,4))
                    for r in range(size//2, 0, -1):
                        t = r/(size/2)
                        col = tuple(int(p_color[i]*(1-t) + s_color[i]*t) for i in range(3)) + (int(255*0.14),)
                        d.ellipse([size//2-r, size//2-r, size//2+r-1, size//2+r-1], fill=col)
                    # 内圆
                    inner = int(size*0.4)
                    d.ellipse([size//2-inner, size//2-inner, size//2+inner, size//2+inner],
                              fill=(255,232,214,255), outline=p_color+(255,), width=max(1,size//80))
                    # 初始文字
                    from PIL import ImageFont
                    try:
                        font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", size//4)
                    except Exception:
                        font = ImageFont.load_default()
                    label = a["name"][:2]
                    bbox = d.textbbox((0,0), label, font=font)
                    tx = size//2 - (bbox[2]-bbox[0])//2
                    ty = size//2 - (bbox[3]-bbox[1])//2 - (size//40)
                    d.text((tx, ty), label, fill=(30,41,59,255), font=font)
                    img.save(out, "PNG")
        print("  ✅ Pillow 占位 PNG 生成完成（建议安装 cairosvg: pip install cairosvg 获得高清渲染）")
        return True
    except ImportError:
        print("  ❌ 未找到可用的 SVG 转 PNG 工具")
        print("  💡 安装 cairosvg 后重新运行此脚本: pip install cairosvg")
        print("  💡 或者直接使用 SVG 矢量文件（推荐，浏览器原生支持）")
        return False

def main():
    print("═══ A股交易Agent拟人化图标生成器 ═══")
    print(f"Agent 数量: {len(AGENTS)}")
    print(f"风格数量: 3 (Q版卡通 / 专业商务 / 赛博科技)")
    print(f"SVG 路径: static/agents/<style>/svg/")
    print(f"PNG 路径: static/agents/<style>/png_<size>/")

    generate_all_svgs()
    ok = generate_pngs()

    print("\n📊 生成统计:")
    for style in STYLES:
        style_name = {"styleA_cartoon":"Q版卡通","styleB_professional":"专业商务","styleC_cyberpunk":"赛博科技"}[style]
        svg_count = len(os.listdir(os.path.join(BASE_DIR, style, "svg")))
        png_total = 0
        for sub in ["png_64","png_128","png_256"]:
            d = os.path.join(BASE_DIR, style, sub)
            png_total += len([f for f in os.listdir(d) if f.endswith('.png')])
        print(f"  • {style_name}: {svg_count} SVG + {png_total} PNG")

    if not ok:
        print("\n⚠️  注意：SVG 已生成，可直接在浏览器中使用。如需 PNG，请安装 cairosvg。")
    print("\n✅ 完成！")

if __name__ == "__main__":
    main()
