import sys
import threading
from time import sleep
from datetime import date, datetime, timedelta

import requests
from fake_useragent import UserAgent

# parameters
timeout = 3  # seconds for proxy connection timeout
thread_num = 75  # thread count for filtering active proxies
round_time = 305  # seconds for each round of view count boosting
update_pbar_count = 10  # update view count progress bar for every xx proxies
bv = sys.argv[1]  # video BV id
target = int(sys.argv[2])  # target view count


def time(seconds: int) -> str:
    if seconds < 60:
        return f'{seconds}s'
    else:
        return f'{int(seconds / 60)}min {seconds % 60}s'


# progress bar
def pbar(n: int, total: int) -> str:
    progress = '━' * int(n / total * 50)
    blank = ' ' * (50 - len(progress))
    return f'\r{n}/{total} {progress}{blank}'


# 1.get proxy
yesterday = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
proxy_url = f'https://checkerproxy.net/api/archive/{yesterday}'
print(f'\ngetting proxies from {proxy_url} ...')
proxies_json = requests.get(proxy_url).json()
total_proxies = [proxy['addr'] for proxy in proxies_json]
print(f'successfully get {len(total_proxies)} proxies')


# 2.filter proxies by multi-threading
active_proxies = []
count = 0
def filter_proxys(proxies: 'list[str]') -> None:
    global count
    for proxy in proxies:
        count = count + 1
        try:
            requests.post('http://httpbin.org/post',
                          proxies={'http': 'http://'+proxy},
                          timeout=timeout)
            active_proxies.append(proxy)
        except:  # proxy connect timeout
            pass
        print(f'{pbar(count, len(total_proxies))} {100*count/len(total_proxies):.1f}%   ', end='')


start_filter_time = datetime.now()
print('\nfiltering active proxies using http://httpbin.org/post ...')
thread_proxy_num = len(total_proxies) // thread_num
threads = []
for i in range(thread_num):
    # calculate the start and end index of the proxies that this thread needs to process
    start = i * thread_proxy_num
    end = start + thread_proxy_num if i < (thread_num - 1) else None  # the last thread processes the remaining proxies
    thread = threading.Thread(target=filter_proxys, args=(total_proxies[start:end],))
    thread.start()
    threads.append(thread)
for thread in threads:
    thread.join()  # wait for all threads to finish
filter_cost_seconds = int((datetime.now()-start_filter_time).total_seconds())
print(f'\nsuccessfully filter {len(active_proxies)} active proxies using {time(filter_cost_seconds)}')


# 3.boost view count
print(f'\nstart boosting {bv} at {datetime.now().strftime("%H:%M:%S")}')
current = 0
while True:
    reach_target = False
    start_time = datetime.now()
    info = {}  # video information JSON
    # send POST click request for each proxy
    for i, proxy in enumerate(active_proxies):
        try:
            if i % update_pbar_count == 0:  # update progress bar for every {update_pbar_count} proxies
                print(f'{pbar(current, target)} updating view count...', end='')
                info = (requests.get(f'https://api.bilibili.com/x/web-interface/view?bvid={bv}',
                                     headers={'User-Agent': UserAgent().random})
                        .json()['data'])
                current = info['stat']['view']
                if current >= target:
                    reach_target = True
                    print(f'{pbar(current, target)} done                 ', end='')
                    break

            requests.post('http://api.bilibili.com/x/click-interface/click/web/h5',
                          proxies={'http': 'http://'+proxy},
                          headers={'User-Agent': UserAgent().random},
                          timeout=timeout,
                          data={
                              'aid': info['aid'],
                              'cid': info['cid'],
                              'bvid': bv,
                              'part': '1',
                              'mid': info['owner']['mid'],
                              'jsonp': 'jsonp',
                              'type': info['desc_v2'][0]['type'] if info['desc_v2'] else '1',
                              'sub_type': '0'
                          })
            print(f'{pbar(current, target)} proxy({i+1}/{len(active_proxies)}) success   ', end='')
        except:  # proxy connect timeout
            print(f'{pbar(current, target)} proxy({i+1}/{len(active_proxies)}) fail      ', end='')

    if reach_target:  # reach target view count
        break
    remain_seconds = int(round_time-(datetime.now()-start_time).total_seconds())
    if remain_seconds > 0:
        for second in reversed(range(remain_seconds)):
            print(f'{pbar(current, target)} next round: {time(second)}          ', end='')
            sleep(1)
print(f'\nfinish at {datetime.now().strftime("%H:%M:%S")}\n')
