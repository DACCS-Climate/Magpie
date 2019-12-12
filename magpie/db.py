#!/usr/bin/env python
# -*- coding: utf-8 -*-
from magpie.constants import get_constant
from magpie.definitions.alembic_definitions import alembic
from magpie.definitions.sqlalchemy_definitions import (
    register, sessionmaker, engine_from_config,
    configure_mappers, Inspector, Session, sa_exc
)
from magpie.definitions.pyramid_definitions import asbool
from magpie.utils import get_settings_from_config_ini, get_settings, print_log, raise_log, get_logger
from typing import TYPE_CHECKING
import transaction
import inspect
import warnings
import logging
import time
import six

# import or define all models here to ensure they are attached to the
# Base.metadata prior to any initialization routines
from magpie import models

if TYPE_CHECKING:
    from magpie.definitions.typedefs import Any, AnySettingsContainer, SettingsType, Str, Optional, Union  # noqa: F401
    from magpie.definitions.sqlalchemy_definitions import Engine  # noqa: F401


LOGGER = get_logger(__name__)

# run configure_mappers after defining all of the models to ensure
# all relationships can be setup
configure_mappers()


def get_db_url(username=None,   # type: Optional[Str]
               password=None,   # type: Optional[Str]
               db_host=None,    # type: Optional[Str]
               db_port=None,    # type: Optional[Union[Str,int]]
               db_name=None,    # type: Optional[Str]
               settings=None,   # type: AnySettingsContainer
               ):               # type: (...) -> Str
    """Retrieve the database connection URL with provided settings."""
    db_url = get_constant("MAGPIE_DB_URL", settings, raise_missing=False, print_missing=True, raise_not_set=False)
    if db_url:
        LOGGER.info("Using setting 'MAGPIE_DB_URL' for database connection.")
    else:
        def _get(param, kw):
            kw_envvar = "MAGPIE_POSTGRES_{}".format(kw.upper())
            kw_setting = "postgres.{}".format(kw.lower())
            return param if param is not None else get_constant(kw_envvar, settings, kw_setting)

        db_url = "postgresql://%s:%s@%s:%s/%s" % (
            _get(username, "user"),
            _get(password, "password"),
            _get(db_host, "host"),
            _get(db_port, "port"),
            _get(db_name, "db"),
        )
        LOGGER.info("Using composed settings 'MAGPIE_POSTGRES_<>' for database connection.")
    LOGGER.debug("Resolved database connection URL: [%s]", db_url)
    return db_url


def get_engine(container=None, prefix="sqlalchemy.", **kwargs):
    # type: (Optional[AnySettingsContainer], Str, Any) -> Engine
    settings = get_settings(container or {})
    settings[prefix + "url"] = get_db_url()
    settings.setdefault(prefix + "pool_pre_ping", True)
    kwargs = kwargs or {}
    kwargs["convert_unicode"] = True
    return engine_from_config(settings, prefix, **kwargs)


def get_session_factory(engine):
    return sessionmaker(bind=engine)


def get_tm_session(session_factory, transaction_manager):
    """
    Get a ``sqlalchemy.orm.Session`` instance backed by a transaction.

    This function will hook the session to the transaction manager which
    will take care of committing any changes.

    - When using pyramid_tm it will automatically be committed or aborted
      depending on whether an exception is raised.

    - When using scripts you should wrap the session in a manager yourself.
      For example::

          import transaction

          engine = get_engine(settings)
          session_factory = get_session_factory(engine)
          with transaction.manager:
              db_session = get_tm_session(session_factory, transaction.manager)
    """
    db_session = session_factory()
    register(db_session, transaction_manager=transaction_manager)
    return db_session


def get_db_session_from_settings(settings=None, **kwargs):
    # type: (Optional[AnySettingsContainer], Any) -> Session
    session_factory = get_session_factory(get_engine(settings, **kwargs))
    db_session = get_tm_session(session_factory, transaction.manager)
    return db_session


def get_db_session_from_config_ini(config_ini_path, ini_main_section_name="app:magpie_app", settings_override=None):
    settings = get_settings_from_config_ini(config_ini_path, ini_main_section_name)
    if isinstance(settings_override, dict):
        settings.update(settings_override)
    return get_db_session_from_settings(settings)


def run_database_migration(db_session=None):
    # type: (Optional[Session]) -> None
    """
    Runs db migration operations with alembic, using db session or a new engine connection.
    """
    ini_file = get_constant("MAGPIE_ALEMBIC_INI_FILE_PATH")
    LOGGER.info("Using file '{}' for migration.".format(ini_file))
    alembic_args = ["-c", ini_file, "upgrade", "heads"]
    if not isinstance(db_session, Session):
        alembic.config.main(argv=alembic_args)
    else:
        engine = db_session.bind
        with engine.begin() as connection:
            alembic_cfg = alembic.config.Config(file_=ini_file)
            alembic_cfg.attributes['connection'] = connection
            alembic.command.upgrade(alembic_cfg, "head")


def get_database_revision(db_session):
    # type: (Session) -> Str
    query = "SELECT version_num FROM alembic_version"
    result = db_session.execute(query).fetchone()
    return result["version_num"]


def is_database_ready(db_session=None):
    # type: (Optional[Session]) -> bool
    if isinstance(db_session, Session):
        engine = db_session.bind
    else:
        engine = get_engine(dict())
    inspector = Inspector.from_engine(engine)
    table_names = inspector.get_table_names()

    for _, obj in inspect.getmembers(models):
        if inspect.isclass(obj) and hasattr(obj, "__tablename__"):
            if obj.__tablename__ not in table_names:
                LOGGER.error("Database table (or its associated parent) is missing for '{!s}' object".format(obj))
                return False
    return True


def run_database_migration_when_ready(settings, db_session=None):
    # type: (SettingsType, Optional[Session]) -> None
    """
    Runs db migration if requested by config and need from revisions.
    """

    db_ready = False
    if asbool(get_constant("MAGPIE_DB_MIGRATION", settings, "magpie.db_migration",
                           default_value=True, raise_missing=False, raise_not_set=False, print_missing=True)):
        attempts = int(get_constant("MAGPIE_DB_MIGRATION_ATTEMPTS", settings, "magpie.db_migration_attempts",
                                    default_value=5, raise_missing=False, raise_not_set=False, print_missing=True))

        print_log("Running database migration (as required)...")
        attempts = max(attempts, 2)     # enforce at least 2 attempts, 1 for db creation and one for actual migration
        for i in range(1, attempts + 1):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=sa_exc.SAWarning)
                    run_database_migration(db_session)
            except ImportError as ex:
                print_log("Database migration produced [{!r}] (ignored).".format(ex), level=logging.WARNING)
                pass
            except Exception as ex:
                if i <= attempts:
                    print_log("Database migration failed [{!r}]. Retrying... ({}/{})".format(ex, i, attempts))
                    time.sleep(2)
                    continue
                else:
                    raise_log("Database migration failed [{!r}]".format(ex), exception=RuntimeError)

            db_ready = is_database_ready(db_session)
            if not db_ready:
                print_log("Database not ready. Retrying... ({}/{})".format(i, attempts))
                time.sleep(2)
                continue
            break
    else:
        db_ready = is_database_ready(db_session)
    if not db_ready:
        time.sleep(2)
        raise_log("Database not ready", exception=RuntimeError)


def set_sqlalchemy_log_level(magpie_log_level):
    # type: (Union[Str, int]) -> SettingsType
    """
    Suppresses :py:mod:`sqlalchemy` verbose logging if not in ``logging.DEBUG`` for Magpie.
    """
    if isinstance(magpie_log_level, six.string_types):
        magpie_log_level = logging.getLevelName(magpie_log_level)
    sa_settings = {"sqlalchemy.echo": True}
    if magpie_log_level > logging.DEBUG:
        sa_settings["sqlalchemy.echo"] = False
        sa_loggers = "sqlalchemy.engine.base.Engine".split(".")
        sa_log = logging.getLogger(sa_loggers[0])
        sa_log.setLevel(logging.WARN)   # WARN to avoid INFO logs which are too verbose
        for h in sa_log.handlers:
            sa_log.removeHandler(h)
        for sa_mod in sa_loggers[1:]:
            sa_log = sa_log.getChild(sa_mod)
            sa_log.setLevel(logging.WARN)
    return sa_settings


def includeme(config):
    # use pyramid_tm to hook the transaction lifecycle to the request
    config.include("pyramid_tm")
    session_factory = get_session_factory(get_engine(config))
    config.registry["db_session_factory"] = session_factory

    # make `request.db` available for use in Pyramid
    config.add_request_method(
        # r.tm is the transaction manager used by pyramid_tm
        lambda r: get_tm_session(session_factory, r.tm),
        "db",
        reify=True
    )
