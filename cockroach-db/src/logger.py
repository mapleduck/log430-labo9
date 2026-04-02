"""
Logger
SPDX-License-Identifier: LGPL-3.0-or-later
Auteurs: Gabriel C. Ullmann, Fabio Petrillo, 2025
"""
import logging
import sys

class Logger:
    @staticmethod
    def get_instance(name: str, level=logging.DEBUG, log_to_file=False):
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = False

        if logger.handlers:
            return logger

        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        if log_to_file:
            fileHandler = logging.FileHandler("store_manager.log")
            fileHandler.setFormatter(formatter)
            logger.addHandler(fileHandler)

        logging.root.setLevel(logging.WARNING)
        return logger
