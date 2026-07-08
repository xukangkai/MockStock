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

    // Navigate to the page
    console.log('[1] 打开页面 http://127.0.0.1:8080 ...');
    await page.goto('http://127.0.0.1:8080', { waitUntil: 'networkidle2', timeout: 15000 });
    console.log('[1] 页面加载完成');

    // Wait for pet to appear
    await page.waitForSelector('#petHamster', { timeout: 10000 });
    console.log('[1] 宠物仓鼠元素已找到');

    // Screenshot 1: initial state
    await page.screenshot({ path: `${SCREENSHOT_DIR}/pet_test_initial.png`, fullPage: false });
    console.log('[1] 初始截图已保存: pet_test_initial.png');

    // Get initial state
    const initialState = await page.evaluate(() => {
      const el = document.getElementById('petHamster');
      const container = document.getElementById('petContainer');
      return {
        className: el ? el.className : 'NOT FOUND',
        containerLeft: container ? container.style.left : 'N/A',
        containerTop: container ? container.style.top : 'N/A',
      };
    });
    console.log('[1] 初始状态:', JSON.stringify(initialState));

    // Step 2: Wait 10 seconds for first action
    console.log('[2] 等待10秒，让第一个动作触发...');
    await sleep(10000);

    // Step 3: Screenshot after 10 seconds
    const state10s = await page.evaluate(() => {
      const el = document.getElementById('petHamster');
      const container = document.getElementById('petContainer');
      return {
        className: el ? el.className : 'NOT FOUND',
        containerLeft: container ? container.style.left : 'N/A',
        containerTop: container ? container.style.top : 'N/A',
      };
    });
    console.log('[3] 10秒后状态:', JSON.stringify(state10s));
    await page.screenshot({ path: `${SCREENSHOT_DIR}/pet_test_after_10s.png`, fullPage: false });
    console.log('[3] 10秒后截图已保存: pet_test_after_10s.png');

    // Step 4: Inject monitoring script
    console.log('[4] 注入监控脚本...');
    await page.evaluate(() => {
      window.__petActionLog = [];
      window.__petActionSet = new Set();
      window.__petMonitor = setInterval(() => {
        const el = document.getElementById('petHamster');
        const container = document.getElementById('petContainer');
        if (el && container) {
          const classes = el.className;
          const pos = `left:${container.style.left}, top:${container.style.top}`;
          const entry = { time: Date.now(), class: classes, pos };
          window.__petActionLog.push(entry);

          // Extract the animation class (after 'pet-hamster ' and size class)
          const classList = classes.split(' ');
          // Classes are like "pet-hamster normal idle" or "pet-hamster normal jumprope"
          const actionClasses = classList.filter(c =>
            !['pet-hamster', 'fat', 'normal', 'thin', 'very-thin', 'very-fat'].includes(c)
          );
          actionClasses.forEach(c => window.__petActionSet.add(c));
        }
      }, 500);
    });
    console.log('[4] 监控脚本已注入，每500ms采集一次');

    // Step 5: Wait 30 seconds collecting data
    console.log('[5] 等待30秒，收集行为数据...');
    await sleep(30000);

    // Stop monitoring and get results
    const results = await page.evaluate(() => {
      if (window.__petMonitor) clearInterval(window.__petMonitor);
      return {
        uniqueActions: Array.from(window.__petActionSet),
        totalSamples: window.__petActionLog.length,
        lastFewSamples: window.__petActionLog.slice(-20).map(e => ({
          class: e.class,
          pos: e.pos,
        })),
      };
    });

    console.log('\n═══════════════════════════════════════');
    console.log('  宠物行为系统测试结果');
    console.log('═══════════════════════════════════════');
    console.log(`总采样数: ${results.totalSamples}`);
    console.log(`唯一动作类名 (${results.uniqueActions.length}个):`);
    results.uniqueActions.forEach(a => console.log(`  - ${a}`));
    console.log('\n最后20个采样:');
    results.lastFewSamples.forEach((s, i) => {
      console.log(`  [${i}] class: ${s.class} | ${s.pos}`);
    });
    console.log('═══════════════════════════════════════\n');

    // Step 6: Final screenshot
    await page.screenshot({ path: `${SCREENSHOT_DIR}/pet_test_final.png`, fullPage: false });
    console.log('[6] 最终截图已保存: pet_test_final.png');

    // Check against expected actions
    const expectedActions = {
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
      // Original actions
      'walking': '行走',
      'running': '跑步',
      'jumping': '跳跃',
      'spinning': '转圈',
      'tumbling': '翻跟头',
      'dashing': '冲刺',
      'wiggling': '摇屁股',
      'shaking': '抖动',
      'idle': '闲置',
      'bouncing': '弹跳',
      'bouncing-joy': '狂喜弹跳',
    };

    console.log('═══════════════════════════════════════');
    console.log('  动作检测对比');
    console.log('═══════════════════════════════════════');
    for (const [action, label] of Object.entries(expectedActions)) {
      const found = results.uniqueActions.includes(action);
      console.log(`  ${found ? '✅' : '❌'} ${action} (${label})`);
    }
    console.log('═══════════════════════════════════════');

  } catch (err) {
    console.error('测试出错:', err.message);
  } finally {
    await browser.close();
  }
})();
