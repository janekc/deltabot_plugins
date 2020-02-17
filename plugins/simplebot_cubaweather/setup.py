# -*- coding: utf-8 -*-
import re
import os

from setuptools import setup


MODULE_NAME = 'simplebot_cubaweather'
CLASS_NAME = 'CubaWeather'
with open(os.path.join(MODULE_NAME, '__init__.py'), 'rt', encoding='utf8') as fh:
    source = fh.read()
PLUGIN_NAME = re.search(r'name = \'(.*?)\'', source, re.M).group(1)
VERSION = re.search(r'version = \'(.*?)\'', source, re.M).group(1)

setup(
    name=MODULE_NAME,
    version=VERSION,
    author='The SimpleBot Contributors',
    author_email='adbenitez@nauta.cu',
    description='A plugin for SimpleBot, a Delta Chat bot (http://delta.chat/)',
    long_description='For more info visit https://github.com/SimpleBot-Inc/simplebot and https://github.com/cuba-weather',
    long_description_content_type='text/x-rst',
    url='https://github.com/cuba-weather/cuba-weather-simplebot-plugin',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Plugins',
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
        'Topic :: Utilities'
    ],
    keywords='deltachat simplebot plugin cuba-weather',
    packages=[MODULE_NAME],
    install_requires=['simplebot', 'cuba-weather'],
    python_requires='>=3.6',
    entry_points={
        'simplebot.plugins': '{} = {}:{}'.format(PLUGIN_NAME, MODULE_NAME, CLASS_NAME)
    },
    include_package_data=True,
    zip_safe=False,
)
