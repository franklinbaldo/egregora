from jules.scheduler_managers import PRManager

def test_is_green_mergeable_false():
    pr_mgr = PRManager()
    pr_details = {
        "mergeable": False,
        "statusCheckRollup": [{"conclusion": "SUCCESS"}]
    }
    assert pr_mgr.is_green(pr_details) is False

def test_is_green_mergeable_none():
    pr_mgr = PRManager()
    pr_details = {
        "mergeable": None,
        "statusCheckRollup": [{"conclusion": "SUCCESS"}]
    }
    assert pr_mgr.is_green(pr_details) is False

def test_is_green_no_checks():
    pr_mgr = PRManager()
    pr_details = {
        "mergeable": True,
        "statusCheckRollup": []
    }
    # Currently it returns True in the existing code, but we want it to return False
    # to avoid merging before CI starts.
    assert pr_mgr.is_green(pr_details) is False

def test_is_green_failure():
    pr_mgr = PRManager()
    pr_details = {
        "mergeable": True,
        "statusCheckRollup": [{"conclusion": "FAILURE"}]
    }
    assert pr_mgr.is_green(pr_details) is False

def test_is_green_running():
    pr_mgr = PRManager()
    pr_details = {
        "mergeable": True,
        "statusCheckRollup": [{"status": "IN_PROGRESS"}]
    }
    assert pr_mgr.is_green(pr_details) is False

def test_is_green_success():
    pr_mgr = PRManager()
    pr_details = {
        "mergeable": True,
        "statusCheckRollup": [{"conclusion": "SUCCESS"}, {"conclusion": "NEUTRAL"}, {"status": "COMPLETED"}]
    }
    assert pr_mgr.is_green(pr_details) is True
