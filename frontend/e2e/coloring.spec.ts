import {test,expect} from '@playwright/test';
test('advanced house switches between color and coloring PDF without changing revision',async({page,request,context})=>{
 await context.addInitScript(()=>{window.print=()=>{};});
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));let pid='';
 const name='Tự tô '+String(Date.now()).slice(-4);
 try{
  await page.goto('/');
  await page.getByRole('button',{name:'⌂ Kho template Noel',exact:true}).click();
  await page.getByRole('button',{name:'Noel nâng cao',exact:true}).click();
  await expect(page.locator('.template-card')).toHaveCount(6);
  await page.locator('.template-card').nth(2).getByRole('button',{name:'✦ Viết tên',exact:true}).click();
  const dialog=page.getByRole('dialog');
  await dialog.getByLabel('Tên trên ngôi nhà',{exact:true}).fill(name);
  await expect(dialog.getByRole('status')).toContainText('Bảng tên nằm',{timeout:15000});
  await dialog.getByRole('button',{name:'Tạo nhà & bản in',exact:true}).click();
  await expect(page.getByRole('combobox',{name:'Kiểu bản in'})).toBeVisible({timeout:45000});
  const all=await(await request.get('/api/projects')).json();pid=all.find((p:any)=>p.personal_name===name).id;
  const before=await(await request.get(`/api/projects/${pid}`)).json();
  await page.getByRole('combobox',{name:'Kiểu bản in'}).selectOption('coloring');
  await expect(page.locator('.svg-sheet svg').first()).toHaveAttribute('data-print-style','coloring');
  await expect(page.locator('.svg-sheet [data-personal-name]').first()).toBeVisible();
  const [popup]=await Promise.all([page.waitForEvent('popup'),page.getByRole('link',{name:'⎙ Print',exact:true}).click()]);
  await expect(popup).toHaveURL(/style=coloring/);
  await expect(popup.locator('.sheet svg').first()).toHaveAttribute('data-print-style','coloring');
  await popup.close();
  await page.getByRole('button',{name:/Xuất file/}).click();
  const pdf=page.getByRole('link',{name:'↓ Tải PDF — bản tự tô',exact:true});
  await expect(pdf).toHaveAttribute('href',/printable_a4_coloring.pdf/);
  expect((await request.get(await pdf.getAttribute('href')||'')).headers()['content-type']).toBe('application/pdf');
  await page.screenshot({path:'../test-results/advanced-coloring-export.png',fullPage:true});
  await page.getByRole('combobox',{name:'Kiểu bản in'}).selectOption('color');
  await expect(page.getByRole('link',{name:'↓ Tải PDF — bản màu',exact:true})).toHaveAttribute('href',/printable_a4.pdf/);
  expect((await(await request.get(`/api/projects/${pid}`)).json()).revision).toBe(before.revision);
  expect(errors).toEqual([]);
 }finally{if(pid)await request.delete(`/api/projects/${pid}`);}
});
