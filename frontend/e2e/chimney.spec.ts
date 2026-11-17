import {test,expect} from '@playwright/test';
test('classic chimney is included in 3D and both printable variants',async({page,request,context})=>{
 await context.addInitScript(()=>{window.print=()=>{};});
 const p=await(await request.post('/api/projects',{data:{name:'Chimney QA '+Date.now(),preset:'gb_classic',paper:'A4'}})).json();
 try{
  const job=await(await request.post(`/api/projects/${p.id}/generate`)).json();
  await expect.poll(async()=> (await(await request.get(`/api/jobs/${job.id}`)).json()).status,{timeout:45000}).toBe('SUCCEEDED');
  const spec=await(await request.get(`/api/projects/${p.id}/geometry`)).json();
  expect(spec.scene_accessories.panels.filter((p:any)=>p.id.startsWith('CHIMNEY_'))).toHaveLength(4);
  await page.goto('/');
  await page.locator('.project-list button').filter({hasText:p.name}).click();
  await expect(page.locator('.model-view canvas')).toBeVisible();
  await expect(page.locator('.svg-sheet svg')).toHaveCount(spec.sheet_count);
  await expect(page.locator('.svg-sheet').last()).toContainText('ỐNG KHÓI 3D');
  await page.getByRole('combobox',{name:'Kiểu bản in'}).selectOption('coloring');
  await expect(page.locator('.svg-sheet svg').last()).toHaveAttribute('data-print-style','coloring');
  const [popup]=await Promise.all([page.waitForEvent('popup'),page.getByRole('link',{name:'⎙ Print',exact:true}).click()]);
  await expect(popup.locator('.sheet').last()).toContainText('ỐNG KHÓI 3D');
  await expect(popup.locator('.sheet')).toHaveCount(spec.sheet_count);
  await popup.close();
 }finally{await request.delete(`/api/projects/${p.id}`);}
});
