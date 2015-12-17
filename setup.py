from setuptools import setup

version = '0.1'

install_requires = [
    ]

setup_requires = [
    ]

tests_require = [
    'nose',
    ]

setup(name='thinkhazard_processing',
      version=version,
      description='ThinkHazard: Overcome Risk - Processing module',
      long_description=open('README.rst').read(),
      url='https://github.com/GFDRR/thinkhazard_processing',
      author='Camptocamp',
      author_email='info@camptocamp.com',
      packages=['thinkhazard_processing', 'thinkhazard_processing.scripts'],
      zip_safe=False,
      install_requires=install_requires,
      setup_requires=setup_requires,
      tests_require=tests_require,
      test_suite='thinkhazard_processing.tests',
      entry_points="""\
      [console_scripts]
      initialize_db = thinkhazard_processing.scripts.initializedb:main
      harvest = thinkhazard_processing.scripts.harvest:main
      download = thinkhazard_processing.scripts.download:main
      complete = thinkhazard_processing.scripts.complete:main
      process = thinkhazard_processing.scripts.process:main
      decision_tree = thinkhazard_processing.scripts.decision_tree:main
      """,
      )
