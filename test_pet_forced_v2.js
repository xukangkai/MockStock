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

    console.log('打开页面...');
    await page.goto('http://127.0.0.1:8080', { waitUntil: 'networkidle2', timeout: 15000 });
    await page.waitForSelector('#petHamster', { timeout: 10000 });
    console.log('页面加载完成\n');

    // Wait for initial load
    await sleep(2000);

    // Destroy the PetWidget to stop all internal timers
    console.log('销毁PetWidget内部定时器...');
    await page.evaluate(() => {
      PetWidget.destroy();
    });
    await sleep(500);

    // Verify widget is destroyed
    const destroyed = await page.evaluate(() => {
      return !document.getElementById('petHamster');
    });
    console.log(`PetWidget销毁: ${destroyed ? '成功' : '失败(元素仍存在)'}\n`);

    // Re-create the container manually for testing
    await page.evaluate(() => {
      const html = `
        <div class="pet-container" id="petContainer" style="position:fixed;bottom:20px;right:20px;z-index:1000;">
          <div class="pet-hamster normal" id="petHamster"></div>
        </div>`;
      document.body.insertAdjacentHTML('beforeend', html);
    });

    const allActions = [
      // New actions
      { name: 'jumprope', duration: 2000, desc: '跳绳', expectedAnim: 'pet-jumprope', category: 'new' },
      { name: 'run-circle-right', duration: 3000, desc: '跑圈-右', expectedAnim: 'pet-run-circle-out', category: 'new' },
      { name: 'run-circle-left', duration: 3000, desc: '跑圈-左', expectedAnim: 'pet-run-circle-back', category: 'new' },
      { name: 'singing', duration: 2000, desc: '唱歌', expectedAnim: 'pet-sing', category: 'new' },
      { name: 'dance-disco', duration: 2000, desc: '迪斯科', expectedAnim: 'pet-dance-disco', category: 'new' },
      { name: 'dance-ballet', duration: 2000, desc: '芭蕾', expectedAnim: 'pet-dance-ballet', category: 'new' },
      { name: 'dance-robot', duration: 2000, desc: '机械舞', expectedAnim: 'pet-dance-robot', category: 'new' },
      { name: 'eat-ready', duration: 1500, desc: '吃饭-准备', expectedAnim: 'pet-eat-ready', category: 'new' },
      { name: 'eat-chew', duration: 1500, desc: '吃饭-咀嚼', expectedAnim: 'pet-eat-chew', category: 'new' },
      { name: 'eat-satisfied', duration: 1500, desc: '吃饭-满足', expectedAnim: 'pet-eat-satisfied', category: 'new' },
      { name: 'fall-asleep', duration: 2000, desc: '睡觉-入睡', expectedAnim: 'pet-fall-asleep', category: 'new' },
      { name: 'deep-sleep', duration: 2000, desc: '睡觉-深度', expectedAnim: 'pet-deep-sleep', category: 'new' },
      { name: 'wake-up', duration: 2000, desc: '睡觉-醒来', expectedAnim: 'pet-wake-up', category: 'new' },
      // Original actions
      { name: 'idle', duration: 2000, desc: '闲置', expectedAnim: 'pet-breathe', category: 'orig' },
      { name: 'walking', duration: 3000, desc: '行走', expectedAnim: 'pet-walk', category: 'orig' },
      { name: 'running', duration: 2000, desc: '跑步', expectedAnim: 'pet-run', category: 'orig' },
      { name: 'jumping', duration: 1500, desc: '跳跃', expectedAnim: 'pet-jump', category: 'orig' },
      { name: 'spinning', duration: 1500, desc: '转圈', expectedAnim: 'pet-spin', category: 'orig' },
      { name: 'tumbling', duration: 1500, desc: '翻跟头', expectedAnim: 'pet-tumble', category: 'orig' },
      { name: 'dashing', duration: 1500, desc: '冲刺', expectedAnim: 'pet-dash', category: 'orig' },
      { name: 'wiggling', duration: 1500, desc: '摇屁股', expectedAnim: 'pet-wiggle', category: 'orig' },
      { name: 'shaking', duration: 1500, desc: '抖动', expectedAnim: 'pet-shake', category: 'orig' },
      // Life expressions
      { name: 'sleeping', duration: 2000, desc: '打瞌睡', expectedAnim: 'pet-sleep', category: 'life' },
      { name: 'eating', duration: 2000, desc: '吃瓜子', expectedAnim: 'pet-eat', category: 'life' },
      { name: 'exercising', duration: 2000, desc: '举哑铃', expectedAnim: 'pet-exercise', category: 'life' },
      { name: 'bathing', duration: 2000, desc: '洗澡', expectedAnim: 'pet-bath', category: 'life' },
      { name: 'reading', duration: 2000, desc: '看K线', expectedAnim: 'pet-read', category: 'life' },
    ];

    console.log('逐个测试所有动作动画（已停用内部定时器）...\n');
    const results = [];

    for (const action of allActions) {
      // Set the class
      await page.evaluate((actionName) => {
        const el = document.getElementById('petHamster');
        if (el) {
          el.className = 'pet-hamster normal ' + actionName;
        }
      }, action.name);

      await sleep(600);

      // Get computed animation
      const animInfo = await page.evaluate(() => {
        const el = document.getElementById('petHamster');
        if (!el) return null;
        const style = window.getComputedStyle(el);
        return {
          className: el.className,
          animationName: style.animationName,
          animationDuration: style.animationDuration,
          animationIterationCount: style.animationIterationCount,
        };
      });

      // Take screenshot
      await page.screenshot({ path: `${SCREENSHOT_DIR}/pet_v2_${action.name}.png` });

      const match = animInfo.animationName === action.expectedAnim;
      const hasAnim = animInfo.animationName && animInfo.animationName !== 'none';
      const status = match ? '✅' : (hasAnim ? '⚠️' : '❌');

      results.push({
        ...action,
        actualAnim: animInfo.animationName,
        match,
        hasAnim,
      });

      console.log(`  ${status} ${action.name.padEnd(20)} ${action.desc.padEnd(8)} 期望: ${action.expectedAnim.padEnd(22)} 实际: ${animInfo.animationName || 'none'} (${animInfo.animationDuration})`);
    }

    // Summary
    console.log('\n═══════════════════════════════════════════════════');
    console.log('  动画测试总结');
    console.log('═══════════════════════════════════════════════════');

    const categories = {
      'new': '新增动作',
      'orig': '原有动作',
      'life': '生活表情',
    };

    for (const [cat, label] of Object.entries(categories)) {
      const items = results.filter(r => r.category === cat);
      const matched = items.filter(r => r.match).length;
      const hasAnim = items.filter(r => r.hasAnim).length;
      console.log(`\n${label} (${matched}/${items.length} 完全匹配, ${hasAnim}/${items.length} 有动画):`);
      items.forEach(r => {
        const icon = r.match ? '✅' : (r.hasAnim ? '⚠️' : '❌');
        console.log(`  ${icon} ${r.name.padEnd(20)} → ${r.actualAnim || 'NO ANIMATION'}`);
      });
    }

    const totalMatch = results.filter(r => r.match).length;
    const totalHasAnim = results.filter(r => r.hasAnim).length;
    console.log(`\n总计: ${totalMatch}/${results.length} 完全匹配, ${totalHasAnim}/${results.length} 有动画`);
    console.log('═══════════════════════════════════════════════════\n');

  } catch (err) {
    console.error('测试出错:', err.message);
    console.error(err.stack);
  } finally {
    await browser.close();
  }
})();
