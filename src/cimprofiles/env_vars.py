"""
Environment variables read by the CIM object model.

These are the only settings ``Identity`` needs: the log level for invalid
identifiers and the model scope mixed into seeded UUIDs. cim-graph imports
these functions rather than keeping its own copies, so that
``cimgraph.core.set_model_scope()`` clears the one cache ``Identity`` reads.
"""
import logging
import os
from functools import cache

DEFAULT_VALIDATION_LOG_LEVEL = 'WARNING'
# A URI, like md:Model.modelingAuthoritySet in IEC 61970-552 headers. Seeded UUIDs are
# scoped to the authority, so changing this default changes every default-scoped UUID.
DEFAULT_MODEL_AUTHORITY = 'https://github.com/PNNL-CIM-Tools/CIM-Graph'
DEFAULT_MODEL_NAME = ''


@cache
def get_validation_log_level() -> int:
    '''
    Returns the log level used for validation warnings
    Returns:
        log_level: int
    '''
    log_level = getattr(logging, os.environ.get('CIMG_VALIDATION_LOG_LEVEL',
                        DEFAULT_VALIDATION_LOG_LEVEL).upper(), logging.WARNING)
    return log_level

@cache
def get_model_authority() -> str:
    """
    Returns the model authority (e.g. a utility), a URI such as
    'https://utility.example.com/models'. Seeded UUIDs are scoped to it, so
    identical names under different authorities get different deterministic UUIDs.
    Defaults to the CIM-Graph repository URI if CIMG_MODEL_AUTHORITY is not set,
    so seeded UUIDs are the same on every machine.
    """
    return os.getenv('CIMG_MODEL_AUTHORITY', DEFAULT_MODEL_AUTHORITY)

@cache
def get_model_name() -> str:
    """
    Returns the stable model identifier (e.g. a feeder) within the model authority
    that is mixed into seeded UUIDs. Defaults to an empty string.
    """
    return os.getenv('CIMG_MODEL_NAME', DEFAULT_MODEL_NAME)
