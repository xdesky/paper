import {test,expect} from '@playwright/test';

test('continuous sheets, scroll navigation, zoom, layer controls and retry',async({page,request})=>{
 const name='Continuous preview '+Date.now();
 const p=await(await request.post('/api/projects',{data:{name,preset:'gb_classic',paper:'A4'}})).json();
 const job=await(await request.post(`/api/projects/${p.id}/generate`)).json();
 await expect.poll(async()=> (await(await request.get(`/api/jobs/${job.id}`)).json()).status,{timeout:45000}).toBe('SUCCEEDED');
 let failOnce=true;
 await page.route(`**/api/projects/${p.id}/artifacts/svg_pages/page_002.svg*`,async route=>{
  if(failOnce){failOnce=false;await route.fulfill({status:503,body:'Temporary error'});}else await route.continue();
 });
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto('/');
  await page.locator('.project-list button').filter({hasText:name}).click();
  await expect(page.getByRole('combobox',{name:'Chọn trang in'})).toHaveCount(0);
  await expect(page.locator('.preview-page')).toHaveCount(6);
  await expect(page.locator('.preview-page').last().locator('svg')).toBeVisible();
  await expect(page.getByRole('button',{name:'Tải lại trang 2',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Tải lại trang 2',exact:true}).click();
  await expect(page.locator('.svg-sheet svg')).toHaveCount(6);
  const surface=page.getByRole('region',{name:'Các trang in'});
  await surface.evaluate(e=>{e.scrollTop=0;});
  await expect(page.getByLabel('Vị trí xem',{exact:true})).toHaveText('1 / 6');
  await expect(page.getByRole('button',{name:'Trang trước',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'Trang sau',exact:true}).click();
  await expect(page.getByLabel('Vị trí xem',{exact:true})).toHaveText('2 / 6');
  await page.getByRole('button',{name:'Trang trước',exact:true}).click();
  await expect(page.getByLabel('Vị trí xem',{exact:true})).toHaveText('1 / 6');
  await surface.evaluate(e=>{e.scrollTop=e.scrollHeight;});
  await expect(page.getByLabel('Vị trí xem',{exact:true})).toHaveText('6 / 6');
  await expect(page.getByRole('button',{name:'Trang sau',exact:true})).toBeDisabled();
  await expect(page.locator('.preview-page').last()).toBeInViewport();
  await page.getByRole('combobox',{name:'Zoom trang',exact:true}).selectOption('200');
  await expect(page.getByLabel('Vị trí xem',{exact:true})).toHaveText('6 / 6');
  await page.getByLabel('Mã cạnh',{exact:true}).uncheck();
  await expect.poll(()=>page.locator('.seam-code').evaluateAll(nodes=>nodes.every(n=>getComputedStyle(n).opacity==='0'))).toBeTruthy();
  await expect(page.locator('.svg-sheet text').filter({hasText:/^A1$/})).toHaveCSS('opacity','0');
  await page.getByLabel('Mã cạnh',{exact:true}).check();
  await page.getByRole('combobox',{name:'Zoom trang',exact:true}).selectOption('100');
  await surface.evaluate(e=>{e.scrollTop=0;});
  const code=page.locator('.seam-code').first();await code.click();
  await expect(page.locator('.page-footer')).toContainText('Đang chọn:');
  await page.screenshot({path:'../test-results/continuous-preview-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await surface.scrollIntoViewIfNeeded();
  await surface.evaluate(e=>{e.scrollTop=e.scrollHeight;});
  await expect(page.locator('.preview-page').last()).toBeInViewport();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:'../test-results/continuous-preview-mobile.png',fullPage:true});
  await page.getByRole('button',{name:'↓ Xuất file',exact:true}).click();
  await page.getByRole('button',{name:'▧ Workspace',exact:true}).click();
  await expect(page.getByLabel('Vị trí xem',{exact:true})).toHaveText('1 / 6');
  await expect(page.locator('.svg-sheet svg')).toHaveCount(6);
  expect(errors).toEqual([]);
 }finally{await request.delete(`/api/projects/${p.id}`);}
});
