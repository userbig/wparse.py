import asyncio
import shutil
import aiofiles
import aiohttp
import os
import logging
import requests

# "rate limit". also need to read this: https://developers.eveonline.com/blog/article/error-limiting-imminent
semaphore = asyncio.Semaphore(5)


async def main() -> None:
    latest_existing_war = await get_latest_war()

    chunk = 500
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

    # logging.debug(f'Processing war {war_id}')
    specific_war_url_format = 'https://esi.evetech.net/latest/wars/{0}/'

    async with semaphore:
        async with aiohttp.ClientSession(conn_timeout=25) as session:
            try:
                logging.debug('Getting data')

                async with session.get(specific_war_url_format.format(war_id)) as response:
                    if response.status == 200:
                        data = await response.text()
                        async with aiofiles.open('./downloader_wars/{0}.json'.format(war_id), mode='w') as file:
                            await file.write(data)
                    else:
                        logging.debug(response.status)
            except aiohttp.ServerTimeoutError:
                logging.debug(f'Failed with timeout')
            except Exception as e:
                logging.debug(f'Some shit happens with connection', e)


async def sync_process_war(war_id: int) -> None:
    if 472166 < war_id < 473146:
        logging.debug(f'Skipping war_id {war_id}')
        pass

    logging.debug(f'Processing war {war_id}')
    specific_war_url_format = 'https://esi.evetech.net/latest/wars/{0}/'

    response = requests.get(specific_war_url_format.format(war_id))
    data = response.text
    with open('./downloader_wars/{0}.json'.format(war_id), mode='w') as file:
        file.write(data)


if __name__ == '__main__':
    logging.basicConfig(level='DEBUG')
    path = './downloader_wars'

    shutil.rmtree(path)

    if not os.path.isdir(path):
        os.mkdir(path)

    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())

        pending_tasks = asyncio.all_tasks(loop)
        loop.run_until_complete(asyncio.gather(*pending_tasks))
    except KeyboardInterrupt:
        print('\nProgram Stopped')
