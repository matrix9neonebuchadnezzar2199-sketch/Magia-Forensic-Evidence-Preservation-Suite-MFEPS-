# Third-Party Licenses

MFEPS depends on or optionally integrates the following third-party components.
Users are responsible for complying with each component's license terms.

## Optional Components (not bundled — user-installed)

### pydvdcss
- **Description**: Python wrapper for VideoLAN's libdvdcss
- **License**: GPL-3.0-only
- **Source**: https://github.com/rlaphoenix/pydvdcss
- **Usage in MFEPS**: Optional dependency for CSS decryption.
  Imported only in `src/core/dvdcss_reader.py`.
  If not installed, CSS decryption is disabled and MFEPS falls back to
  RAW (encrypted) imaging. MFEPS functions fully without this package.
- **GPL-3.0 Note**: When pydvdcss is installed and used, the combined
  execution may be subject to GPL-3.0 terms. Users who distribute MFEPS
  together with pydvdcss must comply with GPL-3.0.

### libdvdcss (libdvdcss-2.dll)
- **Description**: DVD CSS decryption library by VideoLAN
- **License**: GPL-2.0-or-later
- **Source**: https://www.videolan.org/developers/libdvdcss.html
- **Usage in MFEPS**: Loaded at runtime by pydvdcss via ctypes/cdll.
  User must manually place the DLL in `./libs/` directory.
  Not bundled with MFEPS.

### libaacs (libaacs.dll)
- **Description**: AACS decryption library
- **License**: LGPL-2.1-or-later
- **Source**: https://www.videolan.org/developers/libaacs.html
- **Usage in MFEPS**: Optional. Loaded at runtime via ctypes in
  `src/core/aacs_reader.py`. User must provide the DLL and `keydb.cfg`.
  LGPL-2.1 permits dynamic linking from non-GPL software.

### libewf (ewfacquire, ewfverify)
- **License**: LGPL-3.0-or-later
- **URL**: https://github.com/libyal/libewf
- **Usage**: Optional external tool for E01 (Expert Witness Format) output.
  Not bundled with MFEPS. Users must provide their own copy.
- **Integration**: Subprocess execution only (`src/core/e01_writer.py`).
  No linking or embedding.

## Bundled Python Dependencies (via pip / requirements.txt)

| Package | License | Usage |
|---------|---------|-------|
| nicegui | MIT | WebUI framework |
| sqlalchemy | MIT | ORM / database |
| aiofiles | Apache-2.0 | Async file I/O |
| python-dotenv | BSD-3-Clause | .env loading |
| pydantic | MIT | Data validation |
| pydantic-settings | MIT | Settings management |
| psutil | BSD-3-Clause | System monitoring |
| reportlab | BSD-3-Clause | PDF generation |
| Jinja2 | BSD-3-Clause | Template engine |
| rfc3161ng | MIT | RFC 3161 timestamps |
| wmi | MIT | Windows device enumeration |
| pywin32 | PSF-2.0 | Win32 API access |
| bcrypt | Apache-2.0 | Password hashing |
| pytest | MIT | Testing (dev only) |

## License Compatibility Summary

MFEPS core is licensed under the MIT License, which is compatible with all
the above licenses. The GPL-3.0 obligation from pydvdcss is isolated through
an optional-dependency architecture: `dvdcss_reader.py` catches `ImportError`
and disables CSS decryption when pydvdcss is absent. This ensures MFEPS can
be distributed under MIT without pydvdcss.

When users choose to install pydvdcss, they accept GPL-3.0 terms for that
component. MFEPS itself does not bundle, redistribute, or modify pydvdcss.
