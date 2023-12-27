""" Test loaders
"""

import os

import numpy as np

import nibabel as nib

from xibabel import loaders
from xibabel.loaders import FDataObj, load_nibabel
from xibabel.testing import DATA_PATH

import pytest

rng = np.random.default_rng()


class FakeProxy:

    def __init__(self, array, order=None):
        self._array = array
        self.order = order
        self.ndim = array.ndim
        self.shape = array.shape

    def __getitem__(self, slicer):
        return self._array[slicer]

    def __array__(self):
        return self[:]


def test_fdataobj_basic():
    arr = np.arange(24).reshape((2, 3, 4))
    proxy = FakeProxy(arr)
    fproxy = FDataObj(proxy)
    assert fproxy.ndim == arr.ndim
    assert fproxy.shape == arr.shape
    assert fproxy.order is None
    assert np.all(fproxy[1, 2, :] == arr[1, 2, :])
    assert arr[1, 2, :].dtype == np.arange(2).dtype
    assert fproxy.dtype == np.dtype(np.float64)
    assert fproxy[1, 2, :].dtype == np.dtype(np.float64)


def test_chunking(monkeypatch):
    arr_shape = 10, 20, 30
    arr = rng.normal(size=arr_shape)
    fproxy = FDataObj(FakeProxy(arr))
    f64s = np.dtype(float).itemsize
    monkeypatch.setattr(loaders, "MAXCHUNK_STRATEGY", lambda : arr.size * f64s)
    assert fproxy.chunk_sizes() == [None, None, None]
    monkeypatch.setattr(loaders, "MAXCHUNK_STRATEGY",
                        lambda : arr.size * f64s - 1)
    assert fproxy.chunk_sizes() == [9, None, None]
    c_fproxy = FDataObj(FakeProxy(arr, order='C'))
    assert c_fproxy.chunk_sizes() == [9, None, None]
    f_fproxy = FDataObj(FakeProxy(arr, order='F'))
    assert f_fproxy.chunk_sizes() == [None, None, 29]
    monkeypatch.setattr(loaders, "MAXCHUNK_STRATEGY",
                        lambda : arr.size * f64s / 2 - 1)
    assert fproxy.chunk_sizes() == [4, None, None]
    assert c_fproxy.chunk_sizes() == [4, None, None]
    assert f_fproxy.chunk_sizes() == [None, None, 14]
    monkeypatch.setattr(loaders, "MAXCHUNK_STRATEGY",
                        lambda : arr.size * f64s / 10 - 1)
    assert fproxy.chunk_sizes() == [1, 19, None]
    assert c_fproxy.chunk_sizes() == [1, 19, None]
    assert f_fproxy.chunk_sizes() == [None, None, 2]
    monkeypatch.setattr(loaders, "MAXCHUNK_STRATEGY",
                        lambda : arr.size * f64s / 30 - 1)
    assert fproxy.chunk_sizes() == [1, 6, None]
    assert c_fproxy.chunk_sizes() == [1, 6, None]
    assert f_fproxy.chunk_sizes() == [None, 19, 1]


def out_back(img, out_path):
    if out_path.is_file():
        os.unlink(out_path)
    nib.save(img, out_path)
    return load_nibabel(out_path)


def test_nibabel_tr(tmp_path):
    # Default image.
    arr = np.zeros((2, 3, 4))
    img = nib.Nifti1Image(arr, np.eye(4), None)
    out_path = tmp_path / 'test.nii'
    back_img, meta = out_back(img, out_path)
    assert meta == {}
    arr = np.zeros((2, 3, 4, 6))
    img = nib.Nifti1Image(arr, np.eye(4), None)
    back_img, meta = out_back(img, out_path)
    assert meta == {}
    img.header.set_xyzt_units('mm', 'sec')
    back_img, meta = out_back(img, out_path)
    assert meta == {'RepetitionTime': 1.0}
    img.header.set_xyzt_units('mm', 'msec')
    back_img, meta = out_back(img, out_path)
    assert meta == {'RepetitionTime': 1 / 1000}
    img.header.set_xyzt_units('mm', 'usec')
    back_img, meta = out_back(img, out_path)
    assert meta == {'RepetitionTime': 1 / 1_000_000}


def test_nibabel_slice_timing(tmp_path):
    # Default image.
    arr = np.zeros((2, 3, 4, 5))
    img = nib.Nifti1Image(arr, np.eye(4), None)
    out_path = tmp_path / 'test.nii'
    back_img, meta = out_back(img, out_path)
    assert meta == {}
    img.header.set_dim_info(None, None, 1)
    back_img, meta = out_back(img, out_path)
    assert meta == {'SliceEncodingDirection': 'j'}
    img.header.set_dim_info(1, 0, 2)
    back_img, meta = out_back(img, out_path)
    exp_dim = {'PhaseEncodingDirection': 'i',
               'FrequencyEncodingDirection': 'j',
               'SliceEncodingDirection': 'k'}
    assert meta == exp_dim
    img.header.set_slice_duration(1 / 4)
    back_img, meta = out_back(img, out_path)
    assert meta == exp_dim
    img.header['slice_start'] = 0
    back_img, meta = out_back(img, out_path)
    assert meta == exp_dim
    img.header['slice_end'] = 3
    back_img, meta = out_back(img, out_path)
    assert meta == exp_dim
    img.header['slice_code'] = 4  # NIFTI_SLICE_ALT_DEC
    back_img, meta = out_back(img, out_path)
    exp_timed = exp_dim.copy()
    exp_timed['SliceTiming'] = [0.75, 0.25, 0.5, 0]
    assert meta == exp_timed


JC_EG = (DATA_PATH / 'ds000009' / 'sub-07' / 'func' /
         'sub-07_task-balloonanalogrisktask_bold.nii.gz')


@pytest.mark.skipif(not JC_EG.is_file(), reason=f'Missing "{JC_EG}"')
def test_nib_loader_jc():
    img, meta = load_nibabel(JC_EG)
    assert meta == {'FrequencyEncodingDirection': 'i',
                    'PhaseEncodingDirection': 'j',
                    'SliceEncodingDirection': 'k',
                    'RepetitionTime': 2.0}


JH_EG = (DATA_PATH / 'ds000105' / 'sub-1' / 'func' /
         'sub-1_task-objectviewing_run-01_bold.nii.gz')


@pytest.mark.skipif(not JH_EG.is_file(), reason=f'Missing "{JH_EG}"')
def test_nib_loader_jh():
    img, meta = load_nibabel(JH_EG)
    assert meta == {'RepetitionTime': 2.5}