import {test,expect} from '@playwright/test';
test('empty project state keeps templates in the library',async({page})=>{
 await page.route('**/api/projects',route=>route.request().method()==='GET'?route.fulfill({json:[]}):route.continue());
 await page.goto('/');
 await expect(page.getByRole('heading',{name:'Chưa có dự án',exact:true})).toBeVisible();
 await expect(page.locator('.project-list')).toHaveCount(0);
 await page.getByRole('button',{name:'Chọn template →',exact:true}).click();
 await expect(page.locator('.template-card')).toHaveCount(38);
});
test('workspace composes body patterns and new accessories then persists printable design',async({page,request})=>{
 const p=await(await request.post('/api/projects',{data:{name:'Design QA '+Date.now(),preset:'gb_classic',paper:'A4'}})).json();
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto('/');
  await page.locator('.project-list button').filter({hasText:p.name}).click();
  await page.getByRole('group',{name:'Thân nhà',exact:true}).getByRole('button',{name:'Chọn Tiệm kẹo Giáng sinh',exact:true}).click();
  await page.getByRole('group',{name:'Hoạ tiết mái',exact:true}).getByRole('button',{name:'Chọn Đêm sao',exact:true}).click();
  await page.getByRole('group',{name:'Hoạ tiết thân nhà',exact:true}).getByRole('button',{name:'Chọn Gạch kem',exact:true}).click();
  await expect(page.getByRole('group',{name:'Mẫu cây thông',exact:true}).getByRole('button')).toHaveCount(6);
  await expect(page.getByRole('group',{name:'Mẫu hộp quà',exact:true}).getByRole('button')).toHaveCount(6);
  await page.getByRole('group',{name:'Mẫu cây thông',exact:true}).getByRole('button',{name:'Chọn Thông ngôi sao',exact:true}).click();
  await page.getByRole('group',{name:'Mẫu hộp quà',exact:true}).getByRole('button',{name:'Chọn Quà bông tuyết',exact:true}).click();
  await expect(page.locator('.design-preview img')).toHaveAttribute('src',/^blob:/,{timeout:15000});
  await page.locator('.settings').screenshot({path:'../test-results/workspace-design-controls.png'});
  await expect.poll(async()=>{const saved=await(await request.get(`/api/projects/${p.id}`)).json();return saved.status==='READY'&&saved.design.gift==='snowflake'&&saved.design.tree==='star';},{timeout:45000}).toBeTruthy();
  await expect(page.locator('.svg-sheet svg').first()).toBeVisible({timeout:45000});
  const saved=await(await request.get(`/api/projects/${p.id}`)).json();
  expect(saved.preset).toBe('gb_candy');
  expect(saved.design).toEqual({roof:'stars',wall:'brick',tree:'star',gift:'snowflake'});
  const manifest=await(await request.get(`/api/projects/${p.id}/artifacts/generation_manifest.json`)).json();
  expect(manifest.template.design).toEqual(saved.design);
  await page.getByRole('combobox',{name:'Kiểu bản in'}).selectOption('coloring');
  await expect(page.locator('.svg-sheet svg').last()).toHaveAttribute('data-print-style','coloring');
  await page.reload();
  await page.locator('.project-list button').filter({hasText:p.name}).click();
  await expect(page.getByRole('group',{name:'Mẫu cây thông',exact:true}).getByRole('button',{name:'Chọn Thông ngôi sao',exact:true})).toHaveAttribute('aria-pressed','true');
  await expect(page.getByRole('group',{name:'Hoạ tiết mái',exact:true}).getByRole('button',{name:'Chọn Đêm sao',exact:true})).toHaveAttribute('aria-pressed','true');
  await expect(page.locator('.model-view canvas')).toBeVisible({timeout:15000});
  await expect(page.locator('.svg-sheet svg').first()).toBeVisible({timeout:15000});
  await page.locator('.thumbnail-choice img').first().scrollIntoViewIfNeeded();
  await expect.poll(()=>page.locator('.thumbnail-choice img').first().evaluate((img:HTMLImageElement)=>img.complete&&img.naturalWidth>0)).toBeTruthy();
  await page.locator('.workspace').screenshot({path:'../test-results/workspace-thumbnails-live.png'});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  expect(errors).toEqual([]);
 }finally{await request.delete(`/api/projects/${p.id}`);}
});
