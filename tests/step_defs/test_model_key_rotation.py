import pytest
from pytest_bdd import given, scenario, then, when

from egregora.llm.exceptions import AllModelsExhaustedError
from egregora.llm.providers.model_key_rotator import ModelKeyRotator


@scenario("../features/model_key_rotation.feature", "Exhaust keys per model before switching models")
def test_exhaust_keys():
    pass


@scenario("../features/model_key_rotation.feature", "Fail when all models and keys are exhausted")
def test_fail_all_exhausted():
    pass


@scenario("../features/model_key_rotation.feature", "Succeed on first try")
def test_succeed_first_try():
    pass


@pytest.fixture
def context():
    return {"call_log": [], "call_count": 0, "result": None, "exception": None}


@given('I have models "model-1,model-2,model-3"')
def models_123(context):
    context["models"] = ["model-1", "model-2", "model-3"]


@given('I have models "model-1,model-2"')
def models_12(context):
    context["models"] = ["model-1", "model-2"]


@given('I have API keys "key-a,key-b,key-c"')
def keys_abc(context):
    context["keys"] = ["key-a", "key-b", "key-c"]


@given('I have API keys "key-a,key-b"')
def keys_ab(context):
    context["keys"] = ["key-a", "key-b"]


@given("the first 8 API calls fail with 429 error")
def fail_first_8(context):
    def mock_api_call(model: str, api_key: str) -> str:
        context["call_count"] += 1
        context["call_log"].append((model, api_key))

        if context["call_count"] <= 8:
            msg = "429 Too Many Requests"
            raise Exception(msg)

        return f"Success with {model} and {api_key}"

    context["operation"] = mock_api_call


@given("all API calls fail")
def fail_all(context):
    def mock_api_call(model: str, api_key: str) -> str:
        msg = "429 Too Many Requests"
        raise RuntimeError(msg)

    context["operation"] = mock_api_call


@given("the API call succeeds immediately")
def succeed_immediately(context):
    def mock_api_call(model: str, api_key: str) -> str:
        context["call_log"].append((model, api_key))
        return "Success"

    context["operation"] = mock_api_call


@when("I execute the operation with rotation")
def execute_rotation(context):
    rotator = ModelKeyRotator(models=context["models"], api_keys=context["keys"])
    try:
        context["result"] = rotator.call_with_rotation(context["operation"])
    except Exception as e:  # noqa: BLE001
        context["exception"] = e


@then("the call log should show 9 attempts")
def check_9_attempts(context):
    assert len(context["call_log"]) == 9


@then("the call log should show 1 attempt")
def check_1_attempt(context):
    assert len(context["call_log"]) == 1


@then("the rotation order should be correct")
def check_rotation_order(context):
    expected_order = [
        ("model-1", "key-a"),
        ("model-1", "key-b"),
        ("model-1", "key-c"),
        ("model-2", "key-a"),
        ("model-2", "key-b"),
        ("model-2", "key-c"),
        ("model-3", "key-a"),
        ("model-3", "key-b"),
        ("model-3", "key-c"),
    ]
    assert context["call_log"] == expected_order


@then('the result should be "Success with model-3 and key-c"')
def check_success_result(context):
    assert context["result"] == "Success with model-3 and key-c"


@then("it should raise AllModelsExhaustedError")
def check_raise_error(context):
    assert isinstance(context["exception"], AllModelsExhaustedError)


@then('the attempt should be with "model-1" and "key-a"')
def check_first_attempt(context):
    assert context["call_log"][0] == ("model-1", "key-a")
