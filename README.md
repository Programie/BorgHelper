# Borg Helper

Borg Helper is a script which allows you to define a list of repositories for [BorgBackup](https://www.borgbackup.org) and execute borg commands on those repositories.

The script looks for configs at the following locations (merged in that order):

* `borg-helper.json` in the directory containing the `borg-helper.py`
* `/etc/borg-helper.json`
* `~/.config/borg-helper.json`
* `borg-helper.json` in the current directory

Additional paths can be specified using the `BORG_HELPER_CONFIGS` environment variable (separated by `:` just like the `PATH` environment variable).

The configuration is in JSON and expects at least a `repositories` property containing a map with all of your repositories. Each entry consists of a key (the repository name) and the configuration for this repository.

The repository configuration should have at least a `repository` property specifying the location of that repository. But you might also specify `passphrase` to define the passphrase of that repository as well as `ssh_key` to define the location of your SSH key if using SSH for the repository.

If your borg binary is not in the default search paths, you might specify the path to it using the `borg_binary` property.

## Requirements

* Python 3.10+
* [BorgBackup](https://www.borgbackup.org) (tested with version 1.2 but any version of it should work)

## Installation

Simply download the [borg-helper.py](borg-helper.py) from this repository, store it somewhere and make it executable.

## Aliases

Borg Helper also allows you to define a list of aliases as known from your command line shell or git.

There are global and repository specific aliases. Each alias has a name which will be selected based on the first argument specified after the repository name.

Repository specific aliases are resolved first. After that, the global aliases will be resolved and may also extend an alias which was already resolved by the repository specific aliases.

Aliases can be specified using the `aliases` property inside the repository configuration or at the root level (next to the `repositories` property). Each alias must contain the arguments which should be used instead of that alias.

For example, you might define an alias `create` which will resolve to `create --progress --stats --verbose`. Passing `create /path/to/source` will then resolve to `create --progress --stats --verbose /path/to/source`.

It is possible to use shell syntax like `$()` in aliases (as done with `$(date +%Y-%m-%d_%H:%M)` in the example configuration bellow). The full borg command is passed to your shell.

## Additional commands

Borg Helper has some additional commands which wrap around Borg.

### list-archives

The `list-archives` command can be used to search for specific paths or pattern in all archives of a specific repository.

The usage of the command is quite simple: `borg-helper.py my-repository list-archives`

The command will list all files in all archives of the specified repository. You might specify any arguments also available in `borg list`, like the path to see which archives contain a specific path.

Example: `borg-helper.py my-repository list-archives some/path/inside/the/backup`

## Example configuration

```json
{
  "borg_binary": "/path/to/borg",
  "aliases": {
    "create": "create --progress --stats --verbose",
    "prune": "prune --list --stats --verbose"
  },
  "repositories": {
    "my-repository": {
      "repository": "/path/to/your/repository",
      "aliases": {
        "create": "create ::$(date +%Y-%m-%d_%H:%M)"
      }
    },
    "another-repository": {
      "repository": "ssh://user@example.com/path/to/repository",
      "passphrase": "YourBorgPassphrase"
    }
  }
}
```

## Usage

To list your configured repositories, execute `borg-helper.py list`.

The example from above will show the following output:
```
Available repositories:
  another-repository (ssh://user@example.com/path/to/repository)
  my-repository (/path/to/your/repository)
```

To execute borg on a specific repository, execute `borg-helper.py <repository> <arguments>`.

By using the example configuration from above, you might execute the following commands:

```
borg-helper.py my-repository info
```

This command will execute `borg info` on the repository `my-repository` located at `/path/to/your/repository`. It is basically the same as executing `borg info /path/to/your/repository`.

```
borg-helper.py another-repository create ::my-backup /path/to/your/source
```

This command will execute `borg create --progress --stats --verbose ::my-backup /path/to/your/source` as the global alias `create` matches the first argument next to the repository name.

```
borg-helper.py my-repository create /path/to/some/source
```

This command will execute `borg create --progress --stats --verbose ::$(date +%Y-%m-%d_%H:%M) /path/to/some/source` as the repository specific alias `create` matches the first argument next to the repository name.

After resolving the repository specific alias, the arguments resolve to `create ::$(date +%Y-%m-%d_%H:%M) /path/to/some/source` in which case the global alias `create` matches the first argument resulting in also using the global alias.

This results in the arguments finally being resolved to `create --progress --stats --verbose ::$(date +%Y-%m-%d_%H:%M) /path/to/some/source` and passed to borg.

If you are unsure whether the fully resolved command is the correct one, you might add `-i` before the repository name to interactively ask whether to execute that command. This is especially useful if you want to execute a destructive command like `prune`.
