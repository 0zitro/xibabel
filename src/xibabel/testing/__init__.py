""" Testing utilties and data

We currently only have one data source — `https://www.datalad.org`_.

The datasets we are using come from the `OpenNeuro collection
<https://docs.openneuro.org/git>`_.

To add a file to the data collection:

* ``git submodule add`` the relevant Datalad repository.  For example::

    datalad install https://datasets.datalad.org/openneuro/ds000466

* Add the test files to `test_files.yml`, and maybe `test_sets.yml`, if you
  want to include them in a testing set.
"""

import os
from pathlib import Path
from subprocess import check_call

import yaml

MOD_DIR = Path(__file__).parent

with open(MOD_DIR / 'test_files.yml') as fobj:
    _DEF_FILES_CONFIG = yaml.load(fobj, Loader=yaml.SafeLoader)
with open(MOD_DIR / 'test_sets.yml') as fobj:
    _DEF_SETS_CONFIG = yaml.load(fobj, Loader=yaml.SafeLoader)


class TestFileError(Exception):
    """ Error for missing or damaged test file """


class Fetcher:

    def __init__(self,
                 data_path=None,
                 files_config=None,
                 sets_config=None
                ):
        data_path = data_path if data_path else self.get_data_path()
        self.data_path = Path(data_path).resolve()
        self._files_config = files_config if files_config else _DEF_FILES_CONFIG
        self._sets_config = sets_config if sets_config else _DEF_SETS_CONFIG
        self._file_sources = self._parse_configs()

    def _parse_configs(self):
        out = {}
        for source, info in self._files_config.items():
            if source == 'datalad':
                for repo in info:
                    url = repo['repo']
                    root = url.split('/')[-1]
                    for filename in repo['files']:
                        out[f'{root}/{filename}'] = {'type': 'datalad',
                                                    'repo': url}
            else:
                raise TestFileError(f'Do not recognize source "{source}"')
        return out

    def get_data_path(self):
        return os.environ.get('XIB_DATA_PATH', MOD_DIR)

    def _get_datalad_file(self, path_str, repo_url):
        path_str = self._source2path_str(path_str)
        file_path = (self.data_path / path_str).resolve()
        repo_path = self.data_path / path_str.split('/')[0]
        if not repo_path.is_dir():
            check_call(['datalad', 'install', repo_url],
                       cwd=self.data_path)
        if not file_path.is_file():
            check_call(['datalad', 'get', path_str],
                       cwd=self.data_path)
        assert file_path.is_file()
        return file_path

    def _source2path_str(self, path_or_str):
        if isinstance(path_or_str, str):
            path_or_str = Path(path_or_str)
        if path_or_str.is_absolute():
            path_or_str = path_or_str.relative_to(self.data_path)
        return '/'.join(path_or_str.parts)

    def get_file(self, path_str):
        path_str = self._source2path_str(path_str)
        source = self._file_sources.get(path_str)
        if source is None:
            raise TestFileError(
                f'No record of "{path_str}" as test file')
        if source['type'] == 'datalad':
            return self._get_datalad_file(path_str, source['repo'])
        raise TestFileError(f'Unexpected source "{source}"')

    def get_set(self, set_name):
        out_paths = set()
        set_dict = self._sets_config.get(set_name)
        if set_dict is None:
            raise TestFileError(f'No set called "{set_name}"')
        for subset in set_dict.get('superset_of', []):
            out_paths = out_paths.union(self.get_set(subset))
        for path_str in set_dict.get('files', []):
            out_paths.add(self.get_file(path_str))
        return out_paths


fetcher = Fetcher()
DATA_PATH = fetcher.data_path
