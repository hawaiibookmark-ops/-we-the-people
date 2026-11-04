import sys,asyncio
from playwright.async_api import async_playwright
# usage: pwnav.py out_prefix url [url...]  -> navigates to each url, saves page HTML to raw/<prefix>_<i>.html
async def main(pref,urls):
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox','--headless=new'])
        ctx=await b.new_context(user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36')
        for i,u in enumerate(urls):
            pg=await ctx.new_page()
            try:
                await pg.goto(u,wait_until='domcontentloaded',timeout=60000); await pg.wait_for_timeout(7000)
                h=await pg.content(); open(f'raw/{pref}_{i}.html','w').write(h); print(u,len(h),await pg.title())
            except Exception as e: print(u,'ERR',str(e)[:100])
            await pg.close()
        await b.close()
asyncio.run(main(sys.argv[1],sys.argv[2:]))
