import pytest

import _oneoff_cleanup_publication_pending_qa as cleanup


def test_live_apply_path_is_retired():
    with pytest.raises(TypeError):
        cleanup.run(apply_changes=True)