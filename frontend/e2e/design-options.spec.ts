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
  await page.getByLabel('Thân nhà / mẫu hình học',{exact:true}).selectOption('gb_candy');
  await page.getByLabel('Hoạ tiết mái',{exact:true}).selectOption('stars');
  await page.getByLabel('Hoạ tiết thân nhà',{exact:true}).selectOption('brick');
  await expect(page.getByLabel('Mẫu cây thông',{exact:true}).locator('option')).toHaveCount(6);
  await expect(page.getByLabel('Mẫu hộp quà',{exact:true}).locator('option')).toHaveCount(6);
  await page.getByLabel('Mẫu cây thông',{exact:true}).selectOption('star');
  await page.getByLabel('Mẫu hộp quà',{exact:true}).selectOption('snowflake');
  await expect(page.locator('.design-preview img')).toHaveAttribute('src',/^blob:/,{timeout:15000});
  await page.locator('.settings').screenshot({path:'../test-results/workspace-design-controls.png'});
  await page.getByRole('button',{name:'✧ Generate',exact:true}).click();
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
  await expect(page.getByLabel('Mẫu cây thông',{exact:true})).toHaveValue('star');
  await expect(page.getByLabel('Hoạ tiết mái',{exact:true})).toHaveValue('stars');
  expect(errors).toEqual([]);
 }finally{await request.delete(`/api/projects/${p.id}`);}
});
