#! /usr/bin/env python3

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


class ConfigError(RuntimeError):
    pass


class BorgHelper:
    def __init__(self):
        self.config_paths = [
            "/etc/borg-helper.json",
            "~/.config/borg-helper.json",
            "borg-helper.json"
        ]

        self.ask_before_execute = False
        self.borg_binary = "borg"
        self.repositories = {}
        self.command_aliases = {}

    def load_configs(self) -> None:
        for path in self.config_paths:
            self.load_config(Path(path).expanduser())

    def load_config(self, path: Path) -> bool:
        logging.debug(f"Trying to load config from {path}")

        try:
            with path.open("r") as config_file:
                config = json.load(config_file)

                if "borg_binary" in config:
                    self.borg_binary = config["borg_binary"]
                    logging.debug(f"Using '{self.borg_binary}' as borg binary")

                aliases = config.get("aliases", {})
                logging.debug(f"Config contains {len(aliases)} aliases")

                for alias_name, alias_value in aliases.items():
                    self.add_alias(alias_name, alias_value)

                repositories = config.get("repositories", {})
                logging.debug(f"Config contains {len(repositories)} repositories")

                for repository_name, repository_config in repositories.items():
                    self.add_repository(repository_name, repository_config)
        except FileNotFoundError as error:
            logging.debug(error)  # Log as 'debug' as a non-existing file is OK (we always check all possible paths)

        return True

    def add_alias(self, name: str, value: str) -> None:
        logging.debug(f"Adding alias '{name}'")

        self.command_aliases[name] = value

    def add_repository(self, name: str, config: dict) -> None:
        logging.debug(f"Adding repository '{name}'")

        if name not in self.repositories:
            self.repositories[name] = {}

        self.repositories[name].update(config)

    def get_repositories(self) -> dict:
        return self.repositories

    def get_repository(self, name: str) -> Optional[dict]:
        return self.repositories.get(name)

    def execute_borg(self, repository_name: str, arguments: list, **kwargs) -> Optional[subprocess.CompletedProcess]:
        borg_env = os.environ.copy()
        repository_config = self.get_repository(repository_name)

        if repository_config is None:
            raise ConfigError(f"Unknown repository: {repository_name}")

        if "repository" in repository_config:
            borg_env["BORG_REPO"] = repository_config["repository"]

        if "passphrase" in repository_config:
            borg_env["BORG_PASSPHRASE"] = repository_config["passphrase"]

        if "ssh_key" in repository_config:
            borg_env["BORG_RSH"] = f"ssh -i '{repository_config['ssh_key']}'"

        command_aliases = repository_config.get("aliases", {})

        if len(arguments):
            arguments = self.resolve_alias(arguments, command_aliases)
            arguments = self.resolve_alias(arguments, self.command_aliases)

        command_line = [self.borg_binary] + arguments
        command_line = " ".join(command_line)

        print(f"> \033[0;32m{command_line}\033[0m", file=sys.stderr)

        if self.ask_before_execute:
            if input("Are you sure to execute the command above? [Y/n] ").lower().startswith("n"):
                return None

        return subprocess.run(command_line, env=borg_env, shell=True, **kwargs)

    def execute_custom_borg_command(self, repository_name: str, arguments: list) -> Optional[int]:
        if len(arguments) and arguments[0] == "list-archives":
            borg_process = self.execute_borg(repository_name, ["list", "--short"], stdout=subprocess.PIPE, check=True)
            if not borg_process:
                return 1

            highest_exit_code = 0

            for archive in borg_process.stdout.decode("utf-8").splitlines():
                borg_process = self.execute_borg(repository_name, ["list", f"::{archive}"] + arguments[1:])
                if not borg_process:
                    continue

                highest_exit_code = max(highest_exit_code, borg_process.returncode)

            return highest_exit_code

        return None

    def execute_command(self, repository_name: str, arguments: list) -> int:
        exit_code = self.execute_custom_borg_command(repository_name, arguments)
        if exit_code is not None:
            return exit_code

        borg_process = self.execute_borg(repository_name, arguments)
        if not borg_process:
            return 1

        return borg_process.returncode

    @staticmethod
    def resolve_alias(arguments: list, aliases: dict) -> list:
        if not len(arguments):
            return []

        command = arguments[0]
        if command not in aliases:
            return arguments

        return aliases[command].split(" ") + arguments[1:]


def parse_arguments():
    options = set()
    arguments = []

    for index, argument in enumerate(sys.argv[1:]):
        # Options start with "-" (i.e. "-d", "-i" or a combination like "-di")
        if argument.startswith("-") and len(argument) > 1:
            for character in argument.strip("-"):
                options.add(character)
        else:
            # The first non-option argument starts the argument list
            # Any options after the first non-option argument are added as normal arguments (i.e. to pass them to borg)
            arguments = sys.argv[index + 1:]
            break

    return options, arguments


def main():
    options, arguments = parse_arguments()

    if not arguments or "h" in options:
        print("Usage: {} [-d] [-i] <repository> [borg arguments]".format(sys.argv[0]), file=sys.stderr)
        print("       {} list".format(sys.argv[0]), file=sys.stderr)
        print("       {} <repository> list-archives <borg list arguments>".format(sys.argv[0]), file=sys.stderr)
        print("")
        print("Options:")
        print(" -d    Enable debug logging")
        print(" -h    Display this help message")
        print(" -i    Ask before executing borg command")
        return 1

    if "d" in options:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logging.basicConfig(level=log_level, format="%(levelname)s %(message)s")

    borg_helper = BorgHelper()
    borg_helper.load_configs()

    repositories = borg_helper.get_repositories()

    if not repositories:
        logging.error("No repositories configured!")
        return 1

    if arguments[0] == "list":
        print("Available repositories:")

        for repository_name in sorted(repositories.keys()):
            print("  {} ({})".format(repository_name, repositories[repository_name]["repository"]))

        return 0
    else:
        if "i" in options:
            borg_helper.ask_before_execute = True

        try:
            return borg_helper.execute_command(arguments[0], arguments[1:])
        except ConfigError as error:
            logging.error(error)


if __name__ == "__main__":
    exit(main())
