# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) Semi-ATE
#
# Licensed under the terms of the MIT License
# (see LICENSE.txt for details)
# -----------------------------------------------------------------------------

"""Setup script for ate-dispatcher."""

# Standard library imports
import ast
import os
import os.path as osp
import sys

# Third party imports
from setuptools import find_packages, setup

HERE = osp.dirname(osp.abspath(__file__))


def get_version(module='ate_dispatcher'):
    """Get version."""
    with open(os.path.join(HERE, module, '__init__.py'), 'r') as f:
        data = f.read()
    lines = data.split('\n')
    for line in lines:
        if line.startswith('VERSION_STR'):
            version_tuple = ast.literal_eval(line.split('=')[-1].strip())
            version = '.'.join(map(str, version_tuple))
            break
    return version


def get_description():
    """Get long description."""
    with open(os.path.join(HERE, 'README.md'), 'r') as f:
        data = f.read()
    return data


REQUIREMENTS = [
    'typing-extensions'
]

EXTRAS_REQUIRE = {
    'test': [
        'pytest',
        'pytest-cov',
    ]
}


setup(
    name='ate-dispatcher',
    version=get_version(),
    keywords=['ATE', 'dispatcher', 'async'],
    url='https://github.com/Semi-ATE/ate-dispatcher',
    license='MIT',
    author='Semi-ATE',
    author_email='info@Semi-ATE.com',
    description='Thread-based, asynchronous dispatcher used to gather '
                'results from distributed agents.',
    long_description=get_description(),
    long_description_content_type='text/markdown',
    packages=find_packages(exclude=['contrib', 'docs']),
    install_requires=REQUIREMENTS,
    include_package_data=True,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python'
        ])
