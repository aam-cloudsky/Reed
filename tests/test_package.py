import reed


def test_public_api_exports_core_symbols():
    assert reed.Parcel is not None
    assert reed.flow is not None
    assert reed.node is not None
    assert reed.output is not None
    assert reed.input is not None
