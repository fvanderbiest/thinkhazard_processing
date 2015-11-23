ThinkHazard: Overcome Risk - Processing module
##############################################

.. image:: https://api.travis-ci.org/GFDRR/thinkhazard_processing.svg?branch=master
    :target: https://travis-ci.org/GFDRR/thinkhazard_processing
    :alt: Travis CI Status

This module is intended to work together with the ThinkHazard module.

Getting Started
===============

Create a Python virtual environment and install the project into it::

    $ make install

Configure the project

Use ``local_settings.yaml``
===========================

The settings defined in the ``thinkhazard_processing.yaml`` file can be
overriden by creating a ``local_settings.yaml`` file at the root of the
project.

For example, you can define a specific database connection with a
``local_settings.yaml`` file that looks like this::

    sqlalchemy.url = postgresql://www-data:www-data@localhost:9999/thinkhazard

Run tests
=========

Run the tests with the following command::

    $ make test
