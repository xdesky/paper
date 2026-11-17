import {test,expect} from '@playwright/test';
test('two-bay collection creates a personalized house with two roofs and printable exports',async({page,request,context})=>{
 await context.addInitScript(()=>{window.print=()=>{};});
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 let pid='';const name='Hai gian '+String(Date.now()).slice(-4);
 try{
  await page.goto('/');
  await page.getByRole('button',{name:'⌂ Kho template Noel',exact:true}).click();
  await page.getByRole('button',{name:'Nhà 2 gian',exact:true}).click();
  await expect(page.locator('.template-card')).toHaveCount(6);
  await expect(page.locator('.template-card img').first()).toBeVisible();
  await page.screenshot({path:'../test-results/two-bay-library.png',fullPage:true});
  await page.locator('.template-card').first().getByRole('button',{name:'✦ Viết tên',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Tạo nhà bánh gừng cá nhân hoá'});
  await expect(dialog.getByRole('combobox',{name:'Chọn mẫu nhà',exact:true})).toHaveValue('gb_two_twins_heritage');
  await dialog.getByLabel('Tên trên ngôi nhà',{exact:true}).fill(name);
  await expect(dialog.getByRole('status')).toHaveText('Bảng tên nằm trên mặt trước ngôi nhà',{timeout:15000});
  await dialog.screenshot({path:'../test-results/two-bay-personalize.png'});
  await dialog.getByRole('button',{name:'Tạo nhà & bản in',exact:true}).click();
  await expect(page.locator('.svg-sheet [data-personal-name]').first()).toBeVisible({timeout:45000});
  const projects=await(await request.get('/api/projects')).json();pid=projects.find((p:any)=>p.personal_name===name).id;
  const spec=await(await request.get(`/api/projects/${pid}/geometry`)).json();
  expect(spec.geometry.panels.filter((p:any)=>p.id.startsWith('ROOF'))).toHaveLength(4);
  expect(spec.geometry.seams.filter((s:any)=>s.fold_direction==='VALLEY_FROM_PRINTED_OUTSIDE')).toHaveLength(1);
  await expect(page.locator('.model-view canvas')).toBeVisible();
  const [printPage]=await Promise.all([page.waitForEvent('popup'),page.getByRole('link',{name:'⎙ Print',exact:true}).click()]);
  await expect(printPage.locator('.sheet')).toHaveCount(spec.sheet_count);
  await expect(printPage.locator('[data-personal-name]').first()).toBeVisible();
  await printPage.pdf({path:'../test-results/two-bay-browser-print.pdf',preferCSSPageSize:true,printBackground:true});
  await printPage.close();
  expect((await request.get(`/api/projects/${pid}/artifacts/project.zip?download=true`)).ok()).toBeTruthy();
  expect(errors).toEqual([]);
 }finally{if(pid)await request.delete(`/api/projects/${pid}`);}
});
