from setuptools import setup
import os
import re

setup(
        packages=['tdrconvert',],
        entry_points = {
            'console_scripts' : [
                'tdr_convert = tdrconvert.tdr_convert:run',
            ],
        },
        install_requires = [
            'numpy',
            'h5py',
            'netCDF4',
            'devsim',
        ],
    )
