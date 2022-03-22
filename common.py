from datetime import datetime
import os


def log(message: str, path: str, has_tst: bool = True):
    dir_path = split_on_last_pattern(path, '/')[0]
    check_dir_exists(dir_path)

    with open(path, 'a') as f:
        if has_tst:
            message += '\t(%s)' % get_str_time()
        f.write(message + '\n')
    print(message)


def get_str_time() -> str:
    return str(datetime.now()).split('.')[0]


def format_quiet_chat(content: str) -> str:
    return '(%s)' % content


def check_dir_exists(dir_path: str):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        return False  # Didn't exist, but created one.
    else:
        return True  # Already exists.


def read_from_file(path: str):
    with open(path) as f:
        return f.read().strip('\n')


def get_date_difference(tst_str: str) -> int:
    try:
        date = datetime.strptime(tst_str, '%Y.%m.%d')  # 2021.11.07
        now = datetime.now()
        return (now - date).days
    except Exception as e:
        print('(%s) The timestamp did not match the format: %s.' % (e, tst_str))


def build_tuple(path: str):
    content = read_from_file(path)
    return tuple(content.split('\n'))


def build_tuple_of_tuples(path: str):
    lines = build_tuple(path)
    info = []
    for line in lines:
        info.append(tuple(line.split(',')))
    return tuple(info)


def get_elapsed_sec(start_time) -> float:
    end_time = datetime.now()
    return (end_time - start_time).total_seconds()


# Split on the pattern, but always returning a list with length of 2.
def split_on_last_pattern(string: str, pattern: str) -> ():
    last_piece = string.split(pattern)[-1]  # domain.com/image.jpg -> jpg
    leading_chunks = string.split(pattern)[:-1]  # [domain, com/image]
    leading_piece = pattern.join(leading_chunks)  # domain.com/image
    return leading_piece, last_piece  # (domain.com/image, jpg)
