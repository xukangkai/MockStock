// ═════════════════════════════════════════════════════
//  交易仓鼠宠物 🐹
//  SVG 绘制 + 表情系统 + 装备系统 + 进化等级
// ═════════════════════════════════════════════════════

const PetWidget = (() => {
  // ── 配置 ──
  const CONFIG = {
    // 进化等级阈值（累计盈利）
    levels: [
      { name: '普通', threshold: 0, bodyColor: '#f59e0b', bellyColor: '#fde68a', earColor: '#d97706', nose: '#92400e' },
      { name: '黄金', threshold: 1000, bodyColor: '#fbbf24', bellyColor: '#fef3c7', earColor: '#f59e0b', nose: '#b45309' },
      { name: '火焰', threshold: 5000, bodyColor: '#f97316', bellyColor: '#fed7aa', earColor: '#ea580c', nose: '#c2410c' },
      { name: '钻石', threshold: 20000, bodyColor: '#60a5fa', bellyColor: '#dbeafe', earColor: '#3b82f6', nose: '#1d4ed8' },
    ],
    // 装备解锁阈值（累计盈利）
    equipment: [
      { name: '礼帽', icon: '🎩', threshold: 500, svgId: 'hat' },
      { name: '西装', icon: '👔', threshold: 2000, svgId: 'suit' },
      { name: '奖杯', icon: '🏆', threshold: 10000, svgId: 'trophy' },
      { name: '皇冠', icon: '👑', threshold: 50000, svgId: 'crown' },
    ],
    // 胖瘦阈值（当日盈亏）
    sizes: [
      { name: 'very-thin', threshold: -500, label: '暴瘦' },
      { name: 'thin', threshold: -100, label: '瘦了' },
      { name: 'normal', threshold: 100, label: '正常' },
      { name: 'fat', threshold: 500, label: '胖了' },
      { name: 'very-fat', threshold: 999999, label: '巨胖' },
    ],
    fetchInterval: 30000,    // 30秒拉一次数据
    lifeExprMin: 25000,      // 生活表情最小间隔 25秒
    lifeExprMax: 50000,      // 生活表情最大间隔 50秒
    lifeExprDuration: 5000,  // 生活表情持续 5秒
    chatterInterval: 5000,   // 碎碎念间隔 5秒
  };

  // ── 状态 ──
  let state = {
    todayPnl: 0,
    totalPnl: 0,
    realizedPnl: 0,
    winRate: 0,
    totalTrades: 0,
    wins: 0,
    equity: 10000,
    initialCash: 10000,
    positionsCount: 0,
    currentLevel: 0,
    currentSize: 'normal',
    currentExpr: 'neutral',
    lifeExpr: null,
    unlockedEquip: [],
    showDetail: false,
    initialized: false,
    // 拖拽状态
    isDragging: false,
    dragStartX: 0,
    dragStartY: 0,
    dragOffsetX: 0,
    dragOffsetY: 0,
    hasMoved: false,
  };

  let fetchTimer = null;
  let lifeTimer = null;
  let bubbleTimer = null;
  let chatterTimer = null;

  // ── SVG 仓鼠绘制 ──
  function buildSvgHamster(level, expr, lifeExpr, equipIds) {
    const lv = CONFIG.levels[level] || CONFIG.levels[0];

    // 表情映射到眼睛和嘴巴的 SVG 路径
    const expressions = getExpression(expr, lifeExpr);

    return `
    <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;">
      <!-- 大耳朵（米老鼠风格） -->
      <circle cx="55" cy="45" r="28" fill="${lv.earColor}"/>
      <circle cx="55" cy="45" r="18" fill="${lv.bellyColor}" opacity="0.4"/>
      <circle cx="145" cy="45" r="28" fill="${lv.earColor}"/>
      <circle cx="145" cy="45" r="18" fill="${lv.bellyColor}" opacity="0.4"/>

      <!-- 身体（圆润） -->
      <ellipse cx="100" cy="135" rx="52" ry="50" fill="${lv.bodyColor}"/>
      <!-- 肚皮（浅色） -->
      <ellipse cx="100" cy="145" rx="38" ry="35" fill="${lv.bellyColor}"/>

      <!-- 大头（占 2/3） -->
      <ellipse cx="100" cy="90" rx="62" ry="55" fill="${lv.bodyColor}"/>

      <!-- 脸部区域（浅色） -->
      <ellipse cx="100" cy="100" rx="42" ry="35" fill="${lv.bellyColor}" opacity="0.6"/>

      <!-- 腮红（大圆） -->
      ${expressions.cheeks}

      <!-- 眼睛 -->
      ${expressions.eyes}

      <!-- 鼻子（小巧） -->
      <ellipse cx="100" cy="98" rx="4" ry="3" fill="${lv.nose}"/>
      <ellipse cx="99" cy="97" rx="1.5" ry="1" fill="#fff" opacity="0.6"/>

      <!-- 嘴巴 -->
      ${expressions.mouth}

      <!-- 胡须（细线） -->
      <line x1="62" y1="95" x2="42" y2="92" stroke="${lv.nose}" stroke-width="0.8" opacity="0.5" stroke-linecap="round"/>
      <line x1="62" y1="99" x2="40" y2="100" stroke="${lv.nose}" stroke-width="0.8" opacity="0.5" stroke-linecap="round"/>
      <line x1="138" y1="95" x2="158" y2="92" stroke="${lv.nose}" stroke-width="0.8" opacity="0.5" stroke-linecap="round"/>
      <line x1="138" y1="99" x2="160" y2="100" stroke="${lv.nose}" stroke-width="0.8" opacity="0.5" stroke-linecap="round"/>

      <!-- 前爪（圆润） -->
      <ellipse cx="65" cy="175" rx="12" ry="10" fill="${lv.earColor}"/>
      <ellipse cx="135" cy="175" rx="12" ry="10" fill="${lv.earColor}"/>
      <!-- 爪子细节 -->
      <circle cx="60" cy="172" r="2" fill="${lv.nose}" opacity="0.3"/>
      <circle cx="65" cy="170" r="2" fill="${lv.nose}" opacity="0.3"/>
      <circle cx="70" cy="172" r="2" fill="${lv.nose}" opacity="0.3"/>
      <circle cx="130" cy="172" r="2" fill="${lv.nose}" opacity="0.3"/>
      <circle cx="135" cy="170" r="2" fill="${lv.nose}" opacity="0.3"/>
      <circle cx="140" cy="172" r="2" fill="${lv.nose}" opacity="0.3"/>

      <!-- 装备层 -->
      ${renderEquipment(equipIds, lv)}

      <!-- 生活表情附加元素 -->
      ${renderLifeExprExtras(lifeExpr, lv)}
    </svg>`;
  }

  function getExpression(expr, lifeExpr) {
    // 生活表情优先（如果有）
    if (lifeExpr) {
      return getLifeExpression(lifeExpr);
    }
    return getMoodExpression(expr);
  }

  function getMoodExpression(expr) {
    switch (expr) {
      case 'ecstatic': // 狂喜 - 星星眼
        return {
          eyes: `
            <text x="72" y="85" font-size="22" text-anchor="middle" fill="#fbbf24">★</text>
            <text x="128" y="85" font-size="22" text-anchor="middle" fill="#fbbf24">★</text>
            <text x="72" y="85" font-size="22" text-anchor="middle" fill="#92400e" opacity="0.3">★</text>
            <text x="128" y="85" font-size="22" text-anchor="middle" fill="#92400e" opacity="0.3">★</text>`,
          mouth: `<path d="M85 105 Q100 118 115 105" fill="${CONFIG.levels[0].bellyColor}" stroke="#92400e" stroke-width="2" stroke-linecap="round"/>`,
          cheeks: `
            <circle cx="60" cy="98" r="12" fill="#fda4af" opacity="0.6"/>
            <circle cx="140" cy="98" r="12" fill="#fda4af" opacity="0.6"/>`,
        };
      case 'happy': // 开心 - 弯弯眼
        return {
          eyes: `
            <path d="M65 82 Q72 74 79 82" fill="none" stroke="#92400e" stroke-width="3" stroke-linecap="round"/>
            <path d="M121 82 Q128 74 135 82" fill="none" stroke="#92400e" stroke-width="3" stroke-linecap="round"/>`,
          mouth: `<path d="M88 105 Q100 114 112 105" fill="none" stroke="#92400e" stroke-width="2.5" stroke-linecap="round"/>`,
          cheeks: `
            <circle cx="60" cy="96" r="10" fill="#fda4af" opacity="0.5"/>
            <circle cx="140" cy="96" r="10" fill="#fda4af" opacity="0.5"/>`,
        };
      case 'angry': // 生气 - 斜眼 + 嘟嘴
        return {
          eyes: `
            <ellipse cx="72" cy="82" rx="7" ry="8" fill="#92400e"/>
            <ellipse cx="72" cy="80" rx="3" ry="3.5" fill="#fff"/>
            <line x1="62" y1="70" x2="80" y2="74" stroke="#92400e" stroke-width="3" stroke-linecap="round"/>
            <ellipse cx="128" cy="82" rx="7" ry="8" fill="#92400e"/>
            <ellipse cx="128" cy="80" rx="3" ry="3.5" fill="#fff"/>
            <line x1="138" y1="70" x2="120" y2="74" stroke="#92400e" stroke-width="3" stroke-linecap="round"/>`,
          mouth: `<ellipse cx="100" cy="108" rx="6" ry="4" fill="#92400e" opacity="0.7"/>`,
          cheeks: `
            <circle cx="60" cy="96" r="10" fill="#ef4444" opacity="0.4"/>
            <circle cx="140" cy="96" r="10" fill="#ef4444" opacity="0.4"/>`,
        };
      case 'furious': // 暴怒 - 红眼 + 大嘴
        return {
          eyes: `
            <ellipse cx="72" cy="82" rx="8" ry="9" fill="#dc2626"/>
            <ellipse cx="72" cy="80" rx="3" ry="3.5" fill="#fff"/>
            <line x1="60" y1="68" x2="82" y2="72" stroke="#dc2626" stroke-width="3.5" stroke-linecap="round"/>
            <ellipse cx="128" cy="82" rx="8" ry="9" fill="#dc2626"/>
            <ellipse cx="128" cy="80" rx="3" ry="3.5" fill="#fff"/>
            <line x1="140" y1="68" x2="118" y2="72" stroke="#dc2626" stroke-width="3.5" stroke-linecap="round"/>`,
          mouth: `<path d="M82 110 Q100 100 118 110" fill="#dc2626" opacity="0.3" stroke="#dc2626" stroke-width="2.5" stroke-linecap="round"/>`,
          cheeks: `
            <circle cx="60" cy="96" r="12" fill="#ef4444" opacity="0.6"/>
            <circle cx="140" cy="96" r="12" fill="#ef4444" opacity="0.6"/>`,
        };
      default: // neutral 平淡 - 大圆眼
        return {
          eyes: `
            <ellipse cx="72" cy="82" rx="7" ry="8" fill="#92400e"/>
            <ellipse cx="72" cy="80" rx="3" ry="3.5" fill="#fff"/>
            <ellipse cx="128" cy="82" rx="7" ry="8" fill="#92400e"/>
            <ellipse cx="128" cy="80" rx="3" ry="3.5" fill="#fff"/>`,
          mouth: `<line x1="92" y1="106" x2="108" y2="106" stroke="#92400e" stroke-width="2" stroke-linecap="round"/>`,
          cheeks: `
            <circle cx="60" cy="96" r="9" fill="#fda4af" opacity="0.3"/>
            <circle cx="140" cy="96" r="9" fill="#fda4af" opacity="0.3"/>`,
        };
    }
  }

  function getLifeExpression(life) {
    switch (life) {
      case 'sleeping': // 打瞌睡 - 闭眼微笑
        return {
          eyes: `
            <path d="M65 84 Q72 80 79 84" fill="none" stroke="#92400e" stroke-width="2.5" stroke-linecap="round"/>
            <path d="M121 84 Q128 80 135 84" fill="none" stroke="#92400e" stroke-width="2.5" stroke-linecap="round"/>`,
          mouth: `<path d="M92 106 Q100 110 108 106" fill="none" stroke="#92400e" stroke-width="2" stroke-linecap="round"/>`,
          cheeks: `
            <circle cx="60" cy="96" r="10" fill="#fda4af" opacity="0.4"/>
            <circle cx="140" cy="96" r="10" fill="#fda4af" opacity="0.4"/>`,
        };
      case 'eating': // 吃瓜子 - 眯眼 + 鼓腮
        return {
          eyes: `
            <path d="M65 82 Q72 76 79 82" fill="none" stroke="#92400e" stroke-width="2.5" stroke-linecap="round"/>
            <path d="M121 82 Q128 76 135 82" fill="none" stroke="#92400e" stroke-width="2.5" stroke-linecap="round"/>`,
          mouth: `<circle cx="100" cy="107" r="5" fill="#92400e" opacity="0.8"/>`,
          cheeks: `
            <circle cx="56" cy="96" r="16" fill="${CONFIG.levels[state.currentLevel].bellyColor}" opacity="0.6"/>
            <circle cx="144" cy="96" r="16" fill="${CONFIG.levels[state.currentLevel].bellyColor}" opacity="0.6"/>
            <circle cx="56" cy="96" r="11" fill="#fda4af" opacity="0.4"/>
            <circle cx="144" cy="96" r="11" fill="#fda4af" opacity="0.4"/>`,
        };
      case 'exercising': // 举哑铃 - 专注眼 + 咬牙
        return {
          eyes: `
            <ellipse cx="72" cy="82" rx="6" ry="7" fill="#92400e"/>
            <ellipse cx="72" cy="80" rx="2.5" ry="3" fill="#fff"/>
            <ellipse cx="128" cy="82" rx="6" ry="7" fill="#92400e"/>
            <ellipse cx="128" cy="80" rx="2.5" ry="3" fill="#fff"/>
            <line x1="62" y1="72" x2="80" y2="72" stroke="#92400e" stroke-width="2.5" stroke-linecap="round"/>
            <line x1="120" y1="72" x2="138" y2="72" stroke="#92400e" stroke-width="2.5" stroke-linecap="round"/>`,
          mouth: `<path d="M90 106 Q100 102 110 106" fill="none" stroke="#92400e" stroke-width="2" stroke-linecap="round"/>`,
          cheeks: `
            <circle cx="60" cy="96" r="10" fill="#fda4af" opacity="0.5"/>
            <circle cx="140" cy="96" r="10" fill="#fda4af" opacity="0.5"/>`,
        };
      case 'bathing': // 洗澡 - 享受眼
        return {
          eyes: `
            <path d="M65 82 Q72 76 79 82" fill="none" stroke="#92400e" stroke-width="3" stroke-linecap="round"/>
            <path d="M121 82 Q128 76 135 82" fill="none" stroke="#92400e" stroke-width="3" stroke-linecap="round"/>`,
          mouth: `<path d="M90 106 Q100 112 110 106" fill="none" stroke="#92400e" stroke-width="2.5" stroke-linecap="round"/>`,
          cheeks: `
            <circle cx="60" cy="96" r="11" fill="#fda4af" opacity="0.5"/>
            <circle cx="140" cy="96" r="11" fill="#fda4af" opacity="0.5"/>`,
        };
      case 'reading': // 看K线 - 专注眼 + 眼镜
        return {
          eyes: `
            <ellipse cx="72" cy="82" rx="5.5" ry="6.5" fill="#92400e"/>
            <ellipse cx="72" cy="80.5" rx="2.2" ry="2.5" fill="#fff"/>
            <ellipse cx="128" cy="82" rx="5.5" ry="6.5" fill="#92400e"/>
            <ellipse cx="128" cy="80.5" rx="2.2" ry="2.5" fill="#fff"/>
            <rect x="62" y="74" width="20" height="16" rx="3" fill="none" stroke="#92400e" stroke-width="1.8" opacity="0.6"/>
            <rect x="118" y="74" width="20" height="16" rx="3" fill="none" stroke="#92400e" stroke-width="1.8" opacity="0.6"/>
            <line x1="82" y1="82" x2="118" y2="82" stroke="#92400e" stroke-width="1.5" opacity="0.5"/>`,
          mouth: `<line x1="94" y1="106" x2="106" y2="106" stroke="#92400e" stroke-width="1.8" stroke-linecap="round"/>`,
          cheeks: `
            <circle cx="60" cy="96" r="8" fill="#fda4af" opacity="0.25"/>
            <circle cx="140" cy="96" r="8" fill="#fda4af" opacity="0.25"/>`,
        };
      default:
        return getMoodExpression('neutral');
    }
  }

  function renderLifeExprExtras(life, lv) {
    if (!life) return '';
    switch (life) {
      case 'sleeping':
        return `
          <text x="150" y="58" font-size="16" fill="#94a3b8" font-weight="bold" opacity="0.7">Z</text>
          <text x="162" y="44" font-size="12" fill="#94a3b8" font-weight="bold" opacity="0.5">z</text>
          <text x="170" y="33" font-size="9" fill="#94a3b8" font-weight="bold" opacity="0.3">z</text>`;
      case 'eating':
        return `<text x="95" y="115" font-size="11" fill="#92400e" opacity="0.8">🌻</text>`;
      case 'exercising':
        return `
          <text x="35" y="155" font-size="18">🏋️</text>
          <circle cx="155" y="65" r="5" fill="#60a5fa" opacity="0.5"/>
          <text x="148" y="56" font-size="9" fill="#60a5fa" opacity="0.7">💧</text>`;
      case 'bathing':
        return `
          <circle cx="50" cy="60" r="6" fill="#e2e8f0" opacity="0.4"/>
          <circle cx="150" cy="55" r="5" fill="#e2e8f0" opacity="0.3"/>
          <circle cx="45" cy="48" r="4" fill="#e2e8f0" opacity="0.3"/>
          <circle cx="155" cy="46" r="7" fill="#e2e8f0" opacity="0.25"/>
          <circle cx="40" cy="65" r="4.5" fill="#e2e8f0" opacity="0.35"/>`;
      case 'reading':
        return `
          <rect x="75" y="155" width="50" height="38" rx="3" fill="#1e3a5f" opacity="0.7"/>
          <line x1="80" y1="165" x2="120" y2="165" stroke="#4ade80" stroke-width="1.2" opacity="0.6"/>
          <line x1="80" y1="171" x2="115" y2="171" stroke="#ef4444" stroke-width="1.2" opacity="0.6"/>
          <line x1="80" y1="177" x2="110" y2="177" stroke="#4ade80" stroke-width="1.2" opacity="0.6"/>
          <line x1="80" y1="183" x2="118" y2="183" stroke="#60a5fa" stroke-width="1.2" opacity="0.6"/>`;
      default:
        return '';
    }
  }

  function renderEquipment(equipIds, lv) {
    let svg = '';
    if (equipIds.includes('hat')) {
      svg += `
        <rect x="78" y="38" width="44" height="7" rx="2.5" fill="#1f2937"/>
        <rect x="85" y="15" width="30" height="25" rx="4" fill="#1f2937"/>
        <rect x="88" y="18" width="24" height="2.5" rx="1" fill="#fbbf24"/>`;
    }
    if (equipIds.includes('suit')) {
      svg += `
        <polygon points="100,130 90,145 110,145" fill="#1e3a5f"/>
        <circle cx="100" cy="135" r="3" fill="#fbbf24"/>`;
    }
    if (equipIds.includes('trophy')) {
      svg += `
        <rect x="155" y="135" width="18" height="20" rx="3" fill="#fbbf24"/>
        <rect x="159" y="155" width="10" height="4" rx="1" fill="#d97706"/>
        <rect x="155" y="159" width="18" height="3" rx="1" fill="#d97706"/>
        <rect x="170" y="139" width="7" height="12" rx="3" fill="#fbbf24" opacity="0.7"/>`;
    }
    if (equipIds.includes('crown')) {
      svg += `
        <polygon points="75,42 82,22 90,36 100,16 110,36 118,22 125,42" fill="#fbbf24"/>
        <rect x="75" y="40" width="50" height="7" rx="2" fill="#fbbf24"/>
        <circle cx="90" cy="32" r="2.5" fill="#ef4444"/>
        <circle cx="100" cy="22" r="2.5" fill="#3b82f6"/>
        <circle cx="110" cy="32" r="2.5" fill="#22c55e"/>`;
    }
    return svg;
  }

  // ── 计算状态 ──
  function calcLevel(totalPnl) {
    let level = 0;
    for (let i = CONFIG.levels.length - 1; i >= 0; i--) {
      if (totalPnl >= CONFIG.levels[i].threshold) { level = i; break; }
    }
    return level;
  }

  function calcSize(todayPnl) {
    for (let i = CONFIG.sizes.length - 1; i >= 0; i--) {
      if (todayPnl >= CONFIG.sizes[i].threshold && (i === 0 || todayPnl < CONFIG.sizes[i + 1]?.threshold)) {
        // Simple threshold logic
      }
    }
    if (todayPnl > 500) return 'very-fat';
    if (todayPnl > 100) return 'fat';
    if (todayPnl > -100) return 'normal';
    if (todayPnl > -500) return 'thin';
    return 'very-thin';
  }

  function calcMoodExpr(todayPnl) {
    if (todayPnl > 500) return 'ecstatic';
    if (todayPnl > 100) return 'happy';
    if (todayPnl > -100) return 'neutral';
    if (todayPnl > -500) return 'angry';
    return 'furious';
  }

  function calcUnlockedEquip(totalPnl) {
    return CONFIG.equipment
      .filter(e => totalPnl >= e.threshold)
      .map(e => e.svgId);
  }

  function getAnimClass(expr, lifeExpr) {
    if (lifeExpr) {
      switch (lifeExpr) {
        case 'sleeping': return 'sleeping';
        case 'eating': return 'eating';
        case 'exercising': return 'exercising';
        case 'bathing': return 'bathing';
        case 'reading': return 'reading';
      }
    }
    switch (expr) {
      case 'ecstatic': return 'bouncing';
      case 'happy': return 'bouncing';
      case 'angry': return 'shaking';
      case 'furious': return 'shaking';
      default: return 'idle';
    }
  }

  // ── 气泡文字 ──
  const BUBBLES = {
    ecstatic: ['卧槽牛逼！', '赚麻了草！', '妈的暴富！', '我靠起飞了！', '牛逼牛逼！', '他妈的赚翻！'],
    happy: ['靠！小赚一笔', '他妈的开心', '牛逼！继续干！', '嘿嘿妈的~', '卧槽还行'],
    neutral: ['妈的磨叽...', '他妈的无聊', '卧槽等啥呢', '靠...真没劲', '奶奶的观望中'],
    angry: ['妈的又亏了！', '操！气死鼠了！', '他妈的不爽！', '靠靠靠！', '卧槽又跌了！'],
    furious: ['操他妈的血亏！', '老子要暴走了！', '他妈的退钱！', '我不活了你大爷的！', '卧槽崩盘了草！'],
    sleeping: ['妈的别吵...', '困死了滚...', '卧槽做梦呢...', '他妈的zzZ...'],
    eating: ['靠真香！', '妈的吃饱了', '卧槽好吃！', '他妈的嘎嘣脆'],
    exercising: ['妈的举铁！', '操！变强！', '他妈的加油！', '靠一二一！'],
    bathing: ['妈的舒服~', '卧槽洗白白', '他妈的搓搓', '靠香喷喷'],
    reading: ['妈的看K线...', '卧槽这阳线！', '他妈的分析中', '靠看盘...'],
  };

  function randomBubble(expr) {
    const arr = BUBBLES[expr] || BUBBLES.neutral;
    return arr[Math.floor(Math.random() * arr.length)];
  }

  // ── 渲染 ──
  function render() {
    const container = document.getElementById('petContainer');
    if (!container) return;

    const hamsterEl = document.getElementById('petHamster');
    const bubbleEl = document.getElementById('petBubble');
    const levelEl = document.getElementById('petLevel');
    const detailEl = document.getElementById('petDetail');

    // 计算状态
    const level = calcLevel(state.totalPnl);
    const size = calcSize(state.todayPnl);
    const expr = calcMoodExpr(state.todayPnl);
    const equip = calcUnlockedEquip(state.totalPnl);

    state.currentLevel = level;
    state.currentSize = size;
    state.currentExpr = expr;
    state.unlockedEquip = equip;

    // 渲染 SVG
    hamsterEl.innerHTML = buildSvgHamster(level, expr, state.lifeExpr, equip);

    // 动画 class
    const animClass = getAnimClass(expr, state.lifeExpr);
    hamsterEl.className = 'pet-hamster ' + size + ' ' + animClass;

    // 等级标签
    const lvNames = ['普通', '黄金', '火焰', '钻石'];
    const lvClasses = ['lv-normal', 'lv-gold', 'lv-fire', 'lv-diamond'];
    levelEl.className = 'pet-level ' + lvClasses[level];
    levelEl.textContent = lvNames[level] + '仓鼠';

    // 详情面板
    renderDetail();
    detailEl.className = 'pet-detail' + (state.showDetail ? ' show' : '');
  }

  function renderDetail() {
    const el = document.getElementById('petDetailContent');
    if (!el) return;

    const pnlClass = state.todayPnl >= 0 ? 'positive' : 'negative';
    const pnlSign = state.todayPnl >= 0 ? '+' : '';
    const totalClass = state.totalPnl >= 0 ? 'positive' : 'negative';
    const totalSign = state.totalPnl >= 0 ? '+' : '';

    let equipHtml = '';
    CONFIG.equipment.forEach(eq => {
      const unlocked = state.totalPnl >= eq.threshold;
      const pct = Math.min(100, Math.max(0, (state.totalPnl / eq.threshold) * 100));
      equipHtml += `
        <div class="pet-equip-item">
          <span class="equip-icon">${eq.icon}</span>
          <span class="equip-name">${eq.name}</span>
          <span class="equip-status ${unlocked ? 'equip-unlocked' : 'equip-locked'}">
            ${unlocked ? '已解锁' : '¥' + eq.threshold.toLocaleString()}
          </span>
        </div>
        ${!unlocked ? `<div class="pet-progress-bar"><div class="pet-progress-fill" style="width:${pct}%;background:${pct > 50 ? '#60a5fa' : '#475569'}"></div></div>` : ''}`;
    });

    // 进化进度
    let levelProgress = '';
    const nextLevel = CONFIG.levels[state.currentLevel + 1];
    if (nextLevel) {
      const currentThreshold = CONFIG.levels[state.currentLevel].threshold;
      const pct = Math.min(100, ((state.totalPnl - currentThreshold) / (nextLevel.threshold - currentThreshold)) * 100);
      levelProgress = `
        <div style="margin-top:8px;">
          <div style="font-size:11px;color:#64748b;margin-bottom:4px;">下一级: ${nextLevel.name}仓鼠 (¥${nextLevel.threshold.toLocaleString()})</div>
          <div class="pet-progress-bar" style="height:5px;">
            <div class="pet-progress-fill" style="width:${pct}%;background:linear-gradient(90deg,#fbbf24,#f97316)"></div>
          </div>
        </div>`;
    } else {
      levelProgress = '<div style="font-size:11px;color:#fbbf24;margin-top:8px;">🏆 已达最高等级！</div>';
    }

    el.innerHTML = `
      <h4>🐹 我的交易仓鼠</h4>
      <div class="stat-row">
        <span class="stat-label">今日盈亏</span>
        <span class="stat-value ${pnlClass}">${pnlSign}¥${state.todayPnl.toFixed(2)}</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">累计盈亏</span>
        <span class="stat-value ${totalClass}">${totalSign}¥${state.totalPnl.toFixed(2)}</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">交易胜率</span>
        <span class="stat-value">${state.winRate}% (${state.wins}/${state.totalTrades})</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">当前权益</span>
        <span class="stat-value">¥${state.equity.toFixed(2)}</span>
      </div>
      ${levelProgress}
      <div class="pet-equip-progress">
        <div style="font-size:11px;color:#64748b;margin-bottom:6px;">装备解锁</div>
        ${equipHtml}
      </div>
    `;
  }

  function showBubble(text, duration) {
    const bubbleEl = document.getElementById('petBubble');
    if (!bubbleEl) return;
    bubbleEl.textContent = text;
    bubbleEl.classList.add('show');
    clearTimeout(bubbleTimer);
    bubbleTimer = setTimeout(() => bubbleEl.classList.remove('show'), duration || 3000);
  }

  // ── 数据获取 ──
  async function fetchData() {
    try {
      const resp = await fetch('/api/pet-stats');
      const data = await resp.json();
      state.todayPnl = data.today_pnl || 0;
      state.totalPnl = data.total_pnl || 0;
      state.realizedPnl = data.realized_pnl || 0;
      state.winRate = data.win_rate || 0;
      state.totalTrades = data.total_trades || 0;
      state.wins = data.wins || 0;
      state.equity = data.equity || 10000;
      state.initialCash = data.initial_cash || 10000;
      state.positionsCount = data.positions_count || 0;
      render();
    } catch (e) {
      console.error('[Pet] 数据获取失败:', e);
    }
  }

  // ── 生活表情定时器 ──
  function scheduleLifeExpr() {
    const delay = CONFIG.lifeExprMin + Math.random() * (CONFIG.lifeExprMax - CONFIG.lifeExprMin);
    lifeTimer = setTimeout(() => {
      const lifeExprs = ['sleeping', 'eating', 'exercising', 'bathing', 'reading'];
      state.lifeExpr = lifeExprs[Math.floor(Math.random() * lifeExprs.length)];
      render();
      showBubble(randomBubble(state.lifeExpr), CONFIG.lifeExprDuration);

      // 持续一段时间后恢复
      setTimeout(() => {
        state.lifeExpr = null;
        render();
        scheduleLifeExpr(); // 安排下一次
      }, CONFIG.lifeExprDuration);
    }, delay);
  }

  // ── 碎碎念定时器：每5秒骂一句 ──
  function startChatter() {
    chatterTimer = setInterval(() => {
      // 如果有生活表情正在播放，用生活表情的台词
      const expr = state.lifeExpr || state.currentExpr;
      showBubble(randomBubble(expr), 2500);
    }, CONFIG.chatterInterval);
  }

  // ── 初始化 ──
  function init() {
    if (state.initialized) return;
    state.initialized = true;

    // 注入 HTML
    const html = `
      <div class="pet-container" id="petContainer">
        <div class="pet-bubble" id="petBubble">你好呀~</div>
        <div class="pet-detail" id="petDetail">
          <div id="petDetailContent"></div>
        </div>
        <div class="pet-hamster idle" id="petHamster"></div>
        <div class="pet-level lv-normal" id="petLevel">普通仓鼠</div>
      </div>`;

    document.body.insertAdjacentHTML('beforeend', html);

    const container = document.getElementById('petContainer');
    
    // 恢复保存的位置
    const savedPos = localStorage.getItem('petPosition');
    if (savedPos) {
      try {
        const pos = JSON.parse(savedPos);
        container.style.left = pos.left + 'px';
        container.style.top = pos.top + 'px';
        container.style.bottom = 'auto';
        container.style.right = 'auto';
      } catch (e) {
        console.error('[Pet] 位置恢复失败:', e);
      }
    }

    // 拖拽：鼠标
    container.addEventListener('mousedown', onDragStart);
    document.addEventListener('mousemove', onDragMove);
    document.addEventListener('mouseup', onDragEnd);

    // 拖拽：触摸
    container.addEventListener('touchstart', onTouchStart, { passive: false });
    document.addEventListener('touchmove', onTouchMove, { passive: false });
    document.addEventListener('touchend', onTouchEnd);

    // 点击事件（仅在非拖拽时触发）
    container.addEventListener('click', (e) => {
      // 如果发生了拖拽，不触发点击
      if (state.hasMoved) {
        state.hasMoved = false;
        return;
      }
      // 如果点击的是详情面板内部，不处理
      if (e.target.closest('.pet-detail')) return;
      state.showDetail = !state.showDetail;
      render();
    });

    // 点击外部关闭详情
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.pet-container') && state.showDetail) {
        state.showDetail = false;
        render();
      }
    });

    // 首次加载
    fetchData().then(() => {
      showBubble(randomBubble(state.currentExpr), 4000);
    });

    // 定时拉数据
    fetchTimer = setInterval(fetchData, CONFIG.fetchInterval);

    // 启动生活表情
    scheduleLifeExpr();

    // 启动碎碎念（5秒一句）
    startChatter();
  }

  // ── 拖拽处理 ──
  function onDragStart(e) {
    if (e.target.closest('.pet-detail')) return;
    state.isDragging = true;
    state.hasMoved = false;
    state.dragStartX = e.clientX;
    state.dragStartY = e.clientY;
    const rect = document.getElementById('petContainer').getBoundingClientRect();
    state.dragOffsetX = e.clientX - rect.left;
    state.dragOffsetY = e.clientY - rect.top;
    document.getElementById('petContainer').classList.add('dragging');
    e.preventDefault();
  }

  function onDragMove(e) {
    if (!state.isDragging) return;
    const container = document.getElementById('petContainer');
    const newX = e.clientX - state.dragOffsetX;
    const newY = e.clientY - state.dragOffsetY;
    
    // 限制在窗口内
    const maxX = window.innerWidth - container.offsetWidth;
    const maxY = window.innerHeight - container.offsetHeight;
    const clampedX = Math.max(0, Math.min(maxX, newX));
    const clampedY = Math.max(0, Math.min(maxY, newY));
    
    container.style.left = clampedX + 'px';
    container.style.top = clampedY + 'px';
    container.style.bottom = 'auto';
    container.style.right = 'auto';
    
    // 判断是否移动超过阈值（区分拖拽和点击）
    const dx = e.clientX - state.dragStartX;
    const dy = e.clientY - state.dragStartY;
    if (Math.sqrt(dx * dx + dy * dy) > 5) {
      state.hasMoved = true;
    }
    
    e.preventDefault();
  }

  function onDragEnd(e) {
    if (!state.isDragging) return;
    state.isDragging = false;
    document.getElementById('petContainer').classList.remove('dragging');
    
    // 保存位置
    if (state.hasMoved) {
      const container = document.getElementById('petContainer');
      const rect = container.getBoundingClientRect();
      localStorage.setItem('petPosition', JSON.stringify({
        left: Math.round(rect.left),
        top: Math.round(rect.top),
      }));
    }
  }

  // ── 触摸拖拽 ──
  function onTouchStart(e) {
    if (e.target.closest('.pet-detail')) return;
    const touch = e.touches[0];
    state.isDragging = true;
    state.hasMoved = false;
    state.dragStartX = touch.clientX;
    state.dragStartY = touch.clientY;
    const rect = document.getElementById('petContainer').getBoundingClientRect();
    state.dragOffsetX = touch.clientX - rect.left;
    state.dragOffsetY = touch.clientY - rect.top;
    document.getElementById('petContainer').classList.add('dragging');
    e.preventDefault();
  }

  function onTouchMove(e) {
    if (!state.isDragging) return;
    const touch = e.touches[0];
    const container = document.getElementById('petContainer');
    const newX = touch.clientX - state.dragOffsetX;
    const newY = touch.clientY - state.dragOffsetY;
    
    const maxX = window.innerWidth - container.offsetWidth;
    const maxY = window.innerHeight - container.offsetHeight;
    const clampedX = Math.max(0, Math.min(maxX, newX));
    const clampedY = Math.max(0, Math.min(maxY, newY));
    
    container.style.left = clampedX + 'px';
    container.style.top = clampedY + 'px';
    container.style.bottom = 'auto';
    container.style.right = 'auto';
    
    const dx = touch.clientX - state.dragStartX;
    const dy = touch.clientY - state.dragStartY;
    if (Math.sqrt(dx * dx + dy * dy) > 5) {
      state.hasMoved = true;
    }
    
    e.preventDefault();
  }

  function onTouchEnd(e) {
    if (!state.isDragging) return;
    state.isDragging = false;
    document.getElementById('petContainer').classList.remove('dragging');
    if (state.hasMoved) {
      const container = document.getElementById('petContainer');
      const rect = container.getBoundingClientRect();
      localStorage.setItem('petPosition', JSON.stringify({
        left: Math.round(rect.left),
        top: Math.round(rect.top),
      }));
    }
  }

  // ── 清理 ──
  function destroy() {
    clearInterval(fetchTimer);
    clearInterval(chatterTimer);
    clearTimeout(lifeTimer);
    clearTimeout(bubbleTimer);
    const el = document.getElementById('petContainer');
    if (el) el.remove();
    state.initialized = false;
  }

  return { init, destroy };
})();

// DOM ready 后初始化
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', PetWidget.init);
} else {
  PetWidget.init();
}
