#!/usr/bin/env python3
import os


if __name__ == '__main__':
    pdir = 'plugins'
    plugins = sorted(os.listdir(pdir))
    pcount = len(plugins)

    for i, p in enumerate(plugins):
        print('{}. {}'.format(i+1, p))
    print('{}. INSTALL ALL'.format(pcount+1))
    i = int(input('* Select plugin: ')) - 1

    if i != pcount:
        plugins = [plugins[i]]

    cmd = 'pip install -U "{}"'
    for p in plugins:
        os.system(cmd.format(os.path.join(pdir, p)))
