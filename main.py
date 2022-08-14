import asyncio
import shutil
import aiofiles
import aiohttp
import os
import logging

# "rate limit". also need to read this: https://developers.eveonline.com/blog/article/error-limiting-imminent
semaphore = asyncio.Semaphore(20)


async def main() -> None:
    latest_existing_war = await get_latest_war()

    chunk = 20000
    current_war = latest_existing_war
    while current_war > latest_existing_war - chunk:
        asyncio.create_task(process_war(current_war))
        current_war -= 1


async def get_latest_war() -> int:
    url = 'https://esi.evetech.net/latest/wars/?datasource=tranquility&max_war_id=999999999'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            latest_existing_war = data[0]
    return latest_existing_war


async def process_war(war_id: int) -> None:
    # not existing range 472166 - 473146
    if 472166 < war_id < 473146:
        logging.debug(f'Skipping war_id {war_id}')
        pass

    attempts = 0
    retries = 5

    while True:
        if attempts >= retries:
            await log_failed_execution(war_id)
            break
        async with semaphore:
            async with aiohttp.ClientSession(conn_timeout=1) as session:
                try:
                    await process(war_id, session)
                    break
                except Exception as e:
                    # logging.debug('Some shit happens with connection', e)
                    attempts += 1
                    sleeping_time = 2 * attempts
                    logging.debug(f'Start Retry for {war_id}. Sleeping time: {sleeping_time} seconds')
                    await asyncio.sleep(sleeping_time)


async def log_failed_execution(war_id) -> None:
    log_message = f'Reached max retries for war_id: {war_id}'
    logging.debug(log_message)
    async with aiofiles.open('./failed.txt'.format(war_id), mode='a+') as file:
        await file.write(log_message + '\n')


async def process(war_id: int, session: aiohttp.ClientSession):
    # logging.debug('Getting data')
    async with session.get('https://esi.evetech.net/latest/wars/{0}/'.format(war_id)) as response:
        if response.status == 200:  # this check looks like shit - need to rework
            data = await response.text()
            async with aiofiles.open('./downloader_wars/{0}.json'.format(war_id), mode='w') as file:
                await file.write(data)
        else:
            logging.debug(response.status)


"""
I potentially reach anti-DDOS protection. At certain point ALL request become painfully slow. And its not only 
related to `esi.esitech.net`, but also for other sites. I hope that i NOT getting limited by my internet provider
"""
if __name__ == '__main__':
    logging.basicConfig(level='DEBUG')

    # clear data and logs from previous executions
    path = './downloader_wars'
    shutil.rmtree(path)
    os.remove('./failed.txt')

    if not os.path.isdir(path):
        os.mkdir(path)

    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())

        pending_tasks = asyncio.all_tasks(loop)
        loop.run_until_complete(asyncio.gather(*pending_tasks))
    except KeyboardInterrupt:
        print('\nProgram Stopped')
