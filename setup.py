from setuptools import setup, find_packages

with open('plusmoin/version.py') as f:
    exec(f.read())

setup(
    name='plusmoin',
    version=__version__,
    description='daemon to help manage clusters of PostgreSQL servers setup in master/slave replication',
    url='http://github.com/NaturalHistoryMuseum/plusmoin',
    author='Alice Heaton',
    author_email='aliceheaton75@gmail.com',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'plusmoin = plusmoin.cli:run'
        ]
    }
)