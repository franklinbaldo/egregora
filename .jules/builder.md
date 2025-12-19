# Builder's Journal

## 2025-05-18 - [Refactor] Extract `write_pipeline.py` to `PipelineRunner`
**Obstacle:** Mocking the frozen dataclass `Window` using `Mock(spec=Window)` failed because `Mock` by default doesn't allow setting attributes that don't exist on the spec if they are not standard, and more importantly, my test setup tried to set attributes on the mock instance which failed because I likely didn't configure the spec correctly for a dataclass or encountered an issue with how `Mock` handles `spec` for frozen dataclasses (which don't allow setting attributes on instances).
**Solution:** I switched to using a plain `Mock()` without a strict spec, manually configuring the necessary attributes (`size`, `start_time`, `end_time`, etc.) and ensuring dunder methods like `__gt__` were defined for timestamp comparisons. This provided the necessary behavior for the test without the rigidity of the frozen dataclass spec during the mocking phase.
