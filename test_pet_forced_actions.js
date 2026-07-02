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

    // Wait for initial action to settle
    await sleep(3000);

    // Now force-trigger each action by manipulating the internal state
    // We need to access the PetWidget's internal functions
    // Since it's an IIFE, we need to find another way
    // Let's directly manipulate the DOM and trigger actions via the exposed API

    // The PetWidget exposes init and destroy, but the action functions are internal.
    // We need to directly set the state and call render.
    // Let's inject code that finds and calls the internal action system.

    // Actually, looking at the code, PetWidget is a module with only init/destroy exposed.
    // The actions are triggered by the internal actionTimer.
    // Let's try a different approach: directly manipulate the DOM classes and take screenshots.

    const allActions = [
      { name: 'idle', duration: 2000, desc: '闲置呼吸' },
      { name: 'walking', duration: 3000, desc: '行走' },
      { name: 'running', duration: 2000, desc: '跑步' },
      { name: 'jumping', duration: 1500, desc: '跳跃' },
      { name: 'spinning', duration: 1500, desc: '转圈' },
      { name: 'tumbling', duration: 1500, desc: '翻跟头' },
      { name: 'dashing', duration: 1500, desc: '冲刺' },
      { name: 'wiggling', duration: 1500, desc: '摇屁股' },
      { name: 'shaking', duration: 1500, desc: '抖动' },
      { name: 'jumprope', duration: 2000, desc: '跳绳' },
      { name: 'run-circle-right', duration: 3000, desc: '跑圈-右' },
      { name: 'run-circle-left', duration: 3000, desc: '跑圈-左' },
      { name: 'singing', duration: 2000, desc: '唱歌' },
      { name: 'dance-disco', duration: 2000, desc: '迪斯科舞蹈' },
      { name: 'dance-ballet', duration: 2000, desc: '芭蕾舞蹈' },
      { name: 'dance-robot', duration: 2000, desc: '机械舞蹈' },
      { name: 'eat-ready', duration: 1500, desc: '吃饭-准备' },
      { name: 'eat-chew', duration: 1500, desc: '吃饭-咀嚼' },
      { name: 'eat-satisfied', duration: 1500, desc: '吃饭-满足' },
      { name: 'fall-asleep', duration: 2000, desc: '睡觉-入睡' },
      { name: 'deep-sleep', duration: 2000, desc: '睡觉-深度' },
      { name: 'wake-up', duration: 2000, desc: '睡觉-醒来' },
      // Life expressions
      { name: 'sleeping', duration: 2000, desc: '生活-打瞌睡' },
      { name: 'eating', duration: 2000, desc: '生活-吃瓜子' },
      { name: 'exercising', duration: 2000, desc: '生活-举哑铃' },
      { name: 'bathing', duration: 2000, desc: '生活-洗澡' },
      { name: 'reading', duration: 2000, desc: '生活-看K线' },
    ];

    console.log('开始逐个测试所有动作动画...\n');
    const results = [];

    for (const action of allActions) {
      // Set the class directly on the hamster element
      await page.evaluate((actionName) => {
        const el = document.getElementById('petHamster');
        if (el) {
          // Remove all existing action/state classes
          el.className = 'pet-hamster normal ' + actionName;
        }
      }, action.name);

      // Wait for animation to render
      await sleep(800);

      // Take screenshot
      const filename = `pet_action_${action.name}.png`;
      await page.screenshot({ path: `${SCREENSHOT_DIR}/${filename}` });

      // Verify the CSS animation is actually applied
      const animInfo = await page.evaluate((actionName) => {
        const el = document.getElementById('petHamster');
        if (!el) return { found: false };
        const style = window.getComputedStyle(el);
        return {
          found: true,
          className: el.className,
          animationName: style.animationName,
          animationDuration: style.animationDuration,
          animationIterationCount: style.animationIterationCount,
          display: style.display,
          width: style.width,
          height: style.height,
        };
      }, action.name);

      const hasAnimation = animInfo.animationName && animInfo.animationName !== 'none';
      const status = hasAnimation ? '✅' : '❌';
      results.push({ ...action, hasAnimation, animName: animInfo.animationName, animDur: animInfo.animationDuration });
      console.log(`  ${status} ${action.name.padEnd(20)} ${action.desc.padEnd(12)} 动画: ${animInfo.animationName || 'none'} (${animInfo.animationDuration})`);
    }

    // Summary
    console.log('\n═══════════════════════════════════════════════════');
    console.log('  动画测试总结');
    console.log('═══════════════════════════════════════════════════');

    const newActions = results.filter(r =>
      ['jumprope', 'run-circle-right', 'run-circle-left', 'singing',
       'dance-disco', 'dance-ballet', 'dance-robot',
       'eat-ready', 'eat-chew', 'eat-satisfied',
       'fall-asleep', 'deep-sleep', 'wake-up'].includes(r.name)
    );
    const origActions = results.filter(r =>
      ['idle', 'walking', 'running', 'jumping', 'spinning', 'tumbling',
       'dashing', 'wiggling', 'shaking'].includes(r.name)
    );
    const lifeExprs = results.filter(r =>
      ['sleeping', 'eating', 'exercising', 'bathing', 'reading'].includes(r.name)
    );

    console.log(`\n新增动作 (${newActions.filter(r=>r.hasAnimation).length}/${newActions.length} 有动画):`);
    newActions.forEach(r => console.log(`  ${r.hasAnimation ? '✅' : '❌'} ${r.name.padEnd(20)} → ${r.animName || 'NO ANIMATION'}`));

    console.log(`\n原有动作 (${origActions.filter(r=>r.hasAnimation).length}/${origActions.length} 有动画):`);
    origActions.forEach(r => console.log(`  ${r.hasAnimation ? '✅' : '❌'} ${r.name.padEnd(20)} → ${r.animName || 'NO ANIMATION'}`));

    console.log(`\n生活表情 (${lifeExprs.filter(r=>r.hasAnimation).length}/${lifeExprs.length} 有动画):`);
    lifeExprs.forEach(r => console.log(`  ${r.hasAnimation ? '✅' : '❌'} ${r.name.padEnd(20)} → ${r.animName || 'NO ANIMATION'}`));

    console.log('\n═══════════════════════════════════════════════════');

  } catch (err) {
    console.error('测试出错:', err.message);
    console.error(err.stack);
  } finally {
    await browser.close();
  }
})();
