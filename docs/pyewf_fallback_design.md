# pyewf Fallback Design — MFEPS Phase 3

## 1. Motivation

- Eliminate external binary dependency for E01 output.
- Enable E01 on systems where `ewfacquire` cannot be installed or executed.
- Provide tighter integration (no stdout parsing, direct API to libewf).

## 2. Current Architecture

- `E01Writer` wraps `ewfacquire.exe` via subprocess.
- Progress is parsed from stdout using regex patterns.
- Hashes are extracted from `ewfacquire` output.
- Verification uses `ewfverify` subprocess.
- After acquisition, `ewfinfo` is run optionally for metadata (same external-tool model).

## 3. Proposed PyEwfWriter Class

```python
class PyEwfWriter:
    """Pure-Python E01 writer using pyewf bindings."""

    async def acquire(self, params: E01Params,
                      progress_callback=None) -> E01Result:
        """
        1. Open source device via ctypes (reuse ImagingEngine handle)
        2. Create EWF handle via pyewf.handle()
        3. Set media values, compression, header values
        4. Write sectors in chunks, hash with TripleHashEngine
        5. Close handle, return result
        """

    async def verify(self, e01_path: str) -> E01VerifyResult:
        """
        1. Open EWF handle in read mode
        2. Read all sectors, compute hashes
        3. Compare with stored hash
        """
```

## 4. Strategy Pattern in imaging_service.py

```python
def _select_e01_backend(self) -> Union[E01Writer, PyEwfWriter]:
    if E01Writer.check_available()["available"]:
        return E01Writer()  # Preferred: battle-tested
    if PyEwfWriter.check_available():
        return PyEwfWriter()  # Fallback
    raise E01NotAvailableError("No E01 backend found")
```

## 5. Windows Build Considerations

- `pyewf` requires C compilation (MSVC or MinGW).
- Pre-built wheels are not reliably available for all Python versions (e.g. 3.13).
- Consider bundling a pre-compiled `.pyd` under `libs/`.
- Alternative: use `libewf.dll` via ctypes (avoid `pyewf` entirely).

## 6. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| pyewf won't compile on Python 3.13 | HIGH | ctypes fallback to libewf |
| Hash computation differs from ewfacquire | MEDIUM | Cross-verify with ewfverify |
| Segment size handling bugs | MEDIUM | Extensive test suite |
| Performance regression | LOW | Double-buffer reuse |

## 7. Implementation Plan (Phase 3)

1. Attempt pyewf wheel build on Python 3.13 / Windows.
2. If successful, implement `PyEwfWriter`.
3. If not, implement ctypes wrapper for `libewf.dll`.
4. Add strategy selector to `imaging_service`.
5. Run full regression plus real-device tests.

## 8. Decision Gate

Before implementation, confirm:

- [ ] pyewf compiles on target Python version
- [ ] libewf.dll exports are documented for ctypes path
- [ ] Performance benchmark vs ewfacquire subprocess
