import {test,expect} from '@playwright/test';
test('Christmas catalog filters, favorites, details, real house and ZIP',async({page,request,context})=>{
 await context.addInitScript(()=>{window.print=()=>{document.documentElement.dataset.printRequested='yes';};});
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 const before=await(await request.get('/api/projects')).json();
 await page.goto('/');
 await page.getByRole('button',{name:'⌂ Kho template Noel',exact:true}).click();
 await expect(page.locator('.template-card')).toHaveCount(38);
 await page.getByRole('button',{name:'Thiên nhiên',exact:true}).click();
 await expect(page.locator('.template-card')).toHaveCount(2);
 await page.getByRole('button',{name:'Tất cả',exact:true}).click();
 await page.getByRole('searchbox',{name:'Tìm template'}).fill('băng đường');
 await expect(page.locator('.template-card')).toHaveCount(1);
 await page.getByRole('button',{name:'Lưu Ngôi nhà băng đường',exact:true}).click();
 await page.getByRole('searchbox',{name:'Tìm template'}).fill('');
 await page.getByRole('button',{name:'♡ Đã lưu (1)',exact:true}).click();
 await expect(page.locator('.template-card')).toHaveCount(1);
 await page.getByRole('button',{name:'♡ Đã lưu (1)',exact:true}).click();
 await page.getByRole('button',{name:'Xem Ngôi nhà bánh gừng',exact:true}).click();
 await expect(page.getByRole('dialog')).toContainText('3 gấp liền · 8 mối dán');
 await page.getByRole('button',{name:'Đóng chi tiết'}).click();
 await page.screenshot({path:'../test-results/christmas-library-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 await page.screenshot({path:'../test-results/christmas-library-mobile.png',fullPage:true});
 await page.setViewportSize({width:1440,height:1000});
 await page.locator('.template-card').filter({has:page.getByRole('heading',{name:'Ngôi nhà bánh gừng',exact:true})}).getByRole('button',{name:'Dùng mẫu này ↗',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Ngôi nhà bánh gừng',exact:true})).toBeVisible();
 await expect(page.locator('.svg-sheet svg').first()).toBeVisible({timeout:45000});
 await expect(page.locator('.model-view canvas')).toBeVisible();
 await expect(page.locator('.dimension-card')).toContainText('90 × 70 × 130');

 await expect(page.locator('.svg-sheet svg').first()).not.toContainText('ROOF_RIGHT');
 await page.locator('.seam-code').first().click();
 await expect(page.locator('.page-footer')).toContainText('Đang chọn:');
 await page.screenshot({path:'../test-results/christmas-house-workspace.png',fullPage:true});
 const [printPage]=await Promise.all([page.waitForEvent('popup'),page.getByRole('link',{name:'⎙ Print',exact:true}).click()]);
 await expect(printPage.locator('html')).toHaveAttribute('data-print-requested','yes');
 await expect(printPage.locator('.sheet')).toHaveCount(5);
 await printPage.pdf({path:'../test-results/browser-printed-house.pdf',preferCSSPageSize:true,printBackground:true});
 await printPage.close();
 const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('link',{name:'↓ Export All'}).click()]);
 expect(download.suggestedFilename()).toBe('project.zip');
 const after=await(await request.get('/api/projects')).json();
 for(const p of before){const unchanged=after.find((q:{id:string})=>q.id===p.id);expect(unchanged).toEqual(p);}
 expect(errors).toEqual([]);
});

test('refresh existing Christmas projects into new immutable revisions',async({request})=>{
 test.setTimeout(180000);
 const projects=await(await request.get('/api/projects')).json();
 for(const p of projects.filter((p:{preset:string})=>p.preset.startsWith('gb_'))){
  const job=await(await request.post(`/api/projects/${p.id}/generate`)).json();
  await expect.poll(async()=> (await(await request.get(`/api/jobs/${job.id}`)).json()).status,{timeout:45000}).toBe('SUCCEEDED');
 }
});
