Yahoo Fantasy Hockey Draft Order Importer
=========================================

Selenium-based tool to import externally-generated pre-draft rankings into
Yahoo Fantasy Hockey. It's ridiculous that they don't support this feature yet,
but if you have an existing league that refuses to move to a better service,
this is probably your best option to avoid setting your rankings manually.


Prerequisites
-------------

- The appropriate [selenium driver](https://selenium-python.readthedocs.io/installation.html#drivers)
- [`pipenv`](https://docs.pipenv.org/en/latest/)
- Python 3.7 or greater


Setup
-----

```bash
$ pipenv install
```


Usage
-----

```bash
$ pipenv run python yahoo.py --help
usage: yahoo.py [-h] [-s <N>] [-r] <path>

positional arguments:
  <path>                Path to rankings file

optional arguments:
  -h, --help            show this help message and exit
  -s <N>, --save-every <N>
                        Save after every N players
  -r, --reset           Reset draft order
```

The script needs a plaintext file with player names in order of rank, e.g.

```
Connor McDavid
Nikita Kucherov
Sidney Crosby
```

Punctuation and capitalization shouldn't matter. To reset your current rankins
and run with a file `players.txt`:

```bash
$ pipenv run python yahoo.py --reset players.txt
```
