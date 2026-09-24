// Offline browser styling checks against the disposable Agent Zero instance.
// PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs node dev/browser-polish.mjs
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({headless:true});
const page = await browser.newPage({viewport:{width:1280,height:1000}});
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const luminance = rgb => rgb.match(/[\d.]+/g).slice(0,3).map(Number).map(n=>n/255)
  .map(n=>n<=.04045?n/12.92:((n+.055)/1.055)**2.4)
  .reduce((sum,n,i)=>sum+n*[.2126,.7152,.0722][i],0);
try {
  await mkdir('dev/out',{recursive:true});
  await page.goto('http://localhost:50090');
  await page.locator('#realtime-voice-button').waitFor();
  for (const dark of [true,false]) {
    const theme = dark ? 'dark' : 'light';
    await page.evaluate(async dark => {
      const {store}=await import('/components/sidebar/bottom/preferences/preferences-store.js');
      store.darkMode=dark;
    }, dark);
    // Wait for the framework's theme/background transition before measuring.
    await page.waitForTimeout(500);
    const button = await page.locator('#realtime-voice-button').evaluate(el=>{
      const s=getComputedStyle(el); return {color:s.color,background:s.backgroundColor};
    });
    const a=luminance(button.color), b=luminance(button.background);
    const contrast=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
    assert.ok(contrast>=4.5, `${theme} icon contrast ${contrast}`);
    await page.evaluate(()=>{void Alpine.store('realtimeVoice').openConfig();});
    await page.locator('#rtv-model').waitFor();
    const fields=await page.locator('.plugin-config-page input, .plugin-config-page textarea, .plugin-config-page select').evaluateAll(elements=>elements.map(el=>{
      const s=getComputedStyle(el);
      return {id:el.id,background:s.backgroundColor,color:s.color,border:s.borderRadius,padding:s.padding,font:s.fontFamily};
    }));
    assert.equal(fields.length,9);
    const reference=fields.find(f=>f.id==='rtv-history');
    for (const field of fields) {
      assert.equal(field.background,reference.background,`${theme}: ${field.id} background`);
      assert.equal(field.color,reference.color,`${theme}: ${field.id} text`);
      assert.equal(field.border,reference.border,`${theme}: ${field.id} border`);
      assert.equal(field.padding,reference.padding,`${theme}: ${field.id} padding`);
    }
    await page.screenshot({path:`dev/out/settings-${theme}.png`});
    await page.getByRole('button',{name:'Cancel',exact:true}).click();
    console.log(`PASS ${theme}: icon contrast ${contrast.toFixed(2)}:1; all 9 fields use native styles`);
  }
  assert.deepEqual(errors,[]);
} finally {await browser.close();}
