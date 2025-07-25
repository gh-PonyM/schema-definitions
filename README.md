# schemi

A cli tool that acts like an application for your database schemas management using SQLModel orm.

## Usage

Create a new project inside the projects folder:

    schemi init news_agg -o projects -c postgres://user:pw@localhost:5432/db_name --env lab

This will create a config file for local and prod databases using sqlite for local and postgres for prod. 
Creating a **new revision** is done like so:

## Features

## How it works under the hood

Alembic uses different config files and folders. The first entrypoint is the `alembic.ini` file and the top of the config 
template we use is this:

```ini
[alembic]
script_location = {script_dir}
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url = sqlite:///:memory:
version_locations = {versions_dir}
```

As you can see, the folder containing the version python files can be specified as well as the script location 
where `env.py` and `script.py.mako` is expected to be found. For migrations and revisions, the tool auto-generates all these files 
the three files mentioned, injecting the database dsn for usage in `env.py`.
