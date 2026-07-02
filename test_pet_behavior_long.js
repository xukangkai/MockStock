const puppeteer = require('puppeteer-core');

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
const SCREENSHOT_DIR = '/Users/a1234/Desktop/A股模拟短线交易训练器';

(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1280,800'],
    defaultViewport: { width: 1280, height: 800 },
  });

  try {
    const page = await browser.newPage();
    page.setDefaultTimeout(30000);

    console.log('[1] 打开页面...');
    await page.goto('http://127.0.0.1:8080', { waitUntil: 'networkidle2', timeout: 15000 });
    await page.waitForSelector('#petHamster', { timeout: 10000 });
    console.log('[1] 页面加载完成，宠物元素已找到');

    // Take initial screenshot
    await page.screenshot({ path: `${SCREENSHOT_DIR}/pet_long_initial.png` });

    // Inject monitoring script immediately
    console.log('[2] 注入监控脚本...');
    await page.evaluate(() => {
      window.__petActionLog = [];
      window.__petActionSet = new Set();
      window.__petLifeExprSet = new Set();
      window.__petMonitor = setInterval(() => {
        const el = document.getElementById('petHamster');
        const container = document.getElementById('petContainer');
        if (el && container) {
          const classes = el.className;
          const pos = `left:${container.style.left}, top:${container.style.top}`;
          const entry = { time: Date.now(), class: classes, pos };
          window.__petActionLog.push(entry);

          // Extract action classes
          const classList = classes.split(' ');
          const actionClasses = classList.filter(c =>
            !['pet-hamster', 'fat', 'normal', 'thin', 'very-thin', 'very-fat'].includes(c)
          );
          actionClasses.forEach(c => {
            window.__petActionSet.add(c);
            // Also track life expressions separately
            if (['sleeping', 'eating', 'exercising', 'bathing', 'reading'].includes(c)) {
              window.__petLifeExprSet.add(c);
            }
          });
        }
      }, 300); // 300ms for higher resolution
    });

    // Wait 90 seconds to collect more data
    console.log('[3] 监控中，等待90秒...');
    // Take periodic screenshots every 15 seconds
    for (let i = 1; i <= 6; i++) {
      await sleep(15000);
      const snap = await page.evaluate(() => {
        const el = document.getElementById('petHamster');
        return el ? el.className : 'N/A';
      });
      console.log(`  [${i * 15}s] 当前状态: ${snap}`);
      await page.screenshot({ path: `${SCREENSHOT_DIR}/pet_long_${i * 15}s.png` });
    }

    // Stop monitoring and get results
    const results = await page.evaluate(() => {
      if (window.__petMonitor) clearInterval(window.__petMonitor);
      return {
        uniqueActions: Array.from(window.__petActionSet),
        lifeExprs: Array.from(window.__petLifeExprSet),
        totalSamples: window.__petActionLog.length,
        // Show distinct class transitions
        transitions: (() => {
          const log = window.__petActionLog;
          const trans = [];
          let lastClass = '';
          for (const entry of log) {
            if (entry.class !== lastClass) {
              trans.push({ class: entry.class, time: new Date(entry.time).toLocaleTimeString() });
              lastClass = entry.class;
            }
          }
          return trans;
        })(),
      };
    });

    console.log('\n═══════════════════════════════════════════════════');
    console.log('  宠物行为系统测试结果 (90秒长时间监控)');
    console.log('═══════════════════════════════════════════════════');
    console.log(`总采样数: ${results.totalSamples}`);
    console.log(`\n唯一动作/状态类名 (${results.uniqueActions.length}个):`);
    results.uniqueActions.forEach(a => console.log(`  - ${a}`));
    console.log(`\n生活表情类名 (${results.lifeExprs.length}个):`);
    results.lifeExprs.forEach(a => console.log(`  - ${a}`));
    console.log(`\n状态转换序列 (${results.transitions.length}次变化):`);
    results.transitions.forEach((t, i) => {
      console.log(`  [${i}] ${t.time} → ${t.class}`);
    });

    // Check against expected actions
    const expectedNewActions = {
      'jumprope': '跳绳',
      'run-circle-right': '跑圈-右',
      'run-circle-left': '跑圈-左',
      'singing': '唱歌',
      'dance-disco': '迪斯科舞蹈',
      'dance-ballet': '芭蕾舞蹈',
      'dance-robot': '机械舞蹈',
      'eat-ready': '吃饭-准备',
      'eat-chew': '吃饭-咀嚼',
      'eat-satisfied': '吃饭-满足',
      'fall-asleep': '睡觉-入睡',
      'deep-sleep': '睡觉-深度',
      'wake-up': '睡觉-醒来',
    };

    const expectedOrigActions = {
      'walking': '行走',
      'running': '跑步',
      'jumping': '跳跃',
      'spinning': '转圈',
      'tumbling': '翻跟头',
      'dashing': '冲刺',
      'wiggling': '摇屁股',
      'shaking': '抖动',
      'idle': '闲置',
    };

    console.log('\n═══════════════════════════════════════');
    console.log('  新增动作检测');
    console.log('═══════════════════════════════════════');
    let newFound = 0;
    for (const [action, label] of Object.entries(expectedNewActions)) {
      const found = results.uniqueActions.includes(action);
      if (found) newFound++;
      console.log(`  ${found ? '✅' : '❌'} ${action} (${label})`);
    }
    console.log(`  → 发现 ${newFound}/${Object.keys(expectedNewActions).length} 个新动作`);

    console.log('\n═══════════════════════════════════════');
    console.log('  原有动作检测');
    console.log('═══════════════════════════════════════');
    let origFound = 0;
    for (const [action, label] of Object.entries(expectedOrigActions)) {
      const found = results.uniqueActions.includes(action);
      if (found) origFound++;
      console.log(`  ${found ? '✅' : '❌'} ${action} (${label})`);
    }
    console.log(`  → 发现 ${origFound}/${Object.keys(expectedOrigActions).length} 个原有动作`);
    console.log('═══════════════════════════════════════\n');

    // Final screenshot
    await page.screenshot({ path: `${SCREENSHOT_DIR}/pet_long_final.png` });
    console.log('[4] 最终截图已保存');

  } catch (err) {
    console.error('测试出错:', err.message);
  } finally {
    await browser.close();
  }
})();
