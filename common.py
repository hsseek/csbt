import random
import time
import os


def pause_briefly(min_pause: float = 0.4, max_pause: float = 2.4):
    time.sleep(random.uniform(min_pause, max_pause))


def get_random_bool(threshold: float = 0.5) -> bool:
    return True if random.uniform(0, 1) <= threshold else False


def check_dir_exists(dir_path: str):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        return False  # Didn't exist, but created one.
    else:
        return True  # Already exists.


def read_from_file(path: str):
    with open(path) as f:
        return f.read().strip('\n')


def build_tuple(path: str):
    content = read_from_file(path)
    return tuple(content.split('\n'))


def build_tuple_of_tuples(path: str):
    lines = build_tuple(path)
    info = []
    for line in lines:
        info.append(tuple(line.split(',')))
    return tuple(info)
