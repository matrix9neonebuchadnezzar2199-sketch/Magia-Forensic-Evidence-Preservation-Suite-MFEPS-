"""ImagingEngineProtocol (Phase 2-4)"""


class TestEngineProtocol:
    def test_imaging_engine_satisfies_protocol(self):
        from src.core.engine_protocol import ImagingEngineProtocol
        from src.core.imaging_engine import ImagingEngine

        assert isinstance(ImagingEngine(), ImagingEngineProtocol)

    def test_optical_engine_satisfies_protocol(self):
        from src.core.engine_protocol import ImagingEngineProtocol
        from src.core.optical_engine import OpticalImagingEngine

        assert isinstance(OpticalImagingEngine(), ImagingEngineProtocol)
