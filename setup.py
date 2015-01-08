from setuptools import setup, find_packages

setup(
    name='plusmoin',
    version='0.1',
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