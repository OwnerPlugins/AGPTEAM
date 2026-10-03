#!/usr/bin/python
# -*- coding: utf-8 -*-
###################################
## AGP Logger Module              ##
## Standalone logger to break the ##
## circular dependency between    ##
## Agp_lib.py and Agp_Utils.py    ##
###################################
from __future__ import absolute_import, print_function

# ========================
# LOGGING IMPORTS
# ========================
from logging.handlers import RotatingFileHandler
import logging
from logging import (
    getLogger,
    DEBUG,
    INFO,
    Formatter,
    StreamHandler,
)

# ========================
# STANDARD IMPORTS
# ========================
from os import remove, makedirs, stat
from os.path import dirname, isfile
from glob import glob
from sys import stdout, stderr
from datetime import datetime, timedelta
from time import mktime
from threading import Timer


class AdvancedColorFormatter(Formatter):
    """Advanced formatter with ANSI colors and timestamp management"""
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[41m',  # Red on background
        'RESET': '\033[0m'
    }

    def format(self, record):
        level_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return f"{timestamp} {level_color}[{record.levelname}]{self.COLORS['RESET']} {record.getMessage()}"


def setup_logging(
        log_file='/tmp/agplog/agp_full.log',
        max_log_size=2,
        backup_count=3):
    """
    Advanced logging configuration with:
    - Colored console output
    - File rotation
    - Robust error handling
    """
    log_dir = dirname(log_file)
    makedirs(log_dir, exist_ok=True)

    logger = getLogger('AGP')
    logger.setLevel(DEBUG)
    logger.propagate = False

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    try:
        console_handler = StreamHandler(stdout)
        console_handler.setFormatter(AdvancedColorFormatter())
        console_handler.setLevel(INFO)

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_log_size * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_formatter = Formatter(
            '%(asctime)s [%(process)d] %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(DEBUG)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

        logger.info("=" * 50)
        logger.info("AGP Logger initialized")
        logger.info(f"Log file: {log_file}")
        logger.info("=" * 50)

    except Exception as e:
        stderr.write(f"CRITICAL LOGGING ERROR: {str(e)}\n")
        raise

    return logger


def cleanup_old_logs(log_file, max_days=7):
    """Pulizia log obsoleti con controllo errori"""
    try:
        cutoff = datetime.now() - timedelta(days=max_days)
        cutoff_timestamp = mktime(cutoff.timetuple())

        for f in glob(f"{log_file}*"):
            if isfile(f) and stat(f).st_mtime < cutoff_timestamp:
                try:
                    remove(f)
                except Exception as e:
                    logging.error(f"Errore cancellazione {f}: {str(e)}")

    except Exception as e:
        logging.error(f"Log cleanup failed: {str(e)}")


def schedule_log_cleanup(interval_hours=12):
    """Scheduler affidabile per pulizia log"""
    def _wrapper():
        try:
            cleanup_old_logs('/tmp/agplog/agp_full.log')
        finally:
            Timer(interval_hours * 3600, _wrapper).start()

    _wrapper()


# ================ SINGLETON LOGGER INSTANCE ================
logger = setup_logging()
schedule_log_cleanup()
