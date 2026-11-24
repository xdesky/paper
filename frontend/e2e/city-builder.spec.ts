import {test,expect} from '@playwright/test';

test.beforeEach(async({context})=>{
 const r=await context.request.post('/api/auth/register',{data:{email:`city-${Date.now()}@example.com`,password:'city-builder-test-password',display_name:'City builder test'}});
 expect(r.status()).toBe(201);
});

test('builds, saves, edits history, and exports an actual-template village PDF',async({page,context})=>{
 const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto('/studio#city-builder');
 await expect(page.getByRole('heading',{name:'Make a little room for a whole city.'})).toBeVisible();
 await page.getByRole('button',{name:'Start a new village'}).click();
 await expect(page.locator('.city-canvas canvas')).toBeVisible();
 await expect(page.locator('.city-asset-card').first()).toBeVisible();
 const first=page.locator('.city-asset-card').first();await first.click();
 const canvas=page.locator('.city-canvas canvas'),box=await canvas.boundingBox();expect(box).not.toBeNull();
 await page.mouse.click(box!.x+box!.width/2,box!.y+box!.height/2);
 await expect(page.locator('.city-status-bar')).toContainText('1 / 100 models',{timeout:10000});
 await expect(page.getByRole('button',{name:'Undo'})).toBeEnabled();await page.getByRole('button',{name:'Undo'}).click();
 await expect(page.locator('.city-status-bar')).toContainText('0 / 100 models');
 await page.getByRole('button',{name:'Redo'}).click();await expect(page.locator('.city-status-bar')).toContainText('1 / 100 models');
 await expect.poll(async()=>{const res=await context.request.get('/api/city/projects');const list=await res.json();return list[0]?.objects?.length;}).toBe(1);
 await page.getByRole('button',{name:'Print & Export'}).click();
 await page.getByRole('button',{name:'Check print files & page count'}).click();
 await expect(page.locator('.city-print-summary')).toContainText('total pages',{timeout:45000});
 await expect(page.locator('.city-print-warnings')).toContainText('not a printable base');
 const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:/Download combined PDF/}).click()]);
 expect(download.suggestedFilename()).toMatch(/\.pdf$/);
 await expect(page.getByRole('dialog')).toHaveCount(0);
 await page.getByRole('button',{name:'Backup JSON'}).click();
 expect(errors).toEqual([]);
});
