# Task: Disable Google Batching and Verify Stability

## Background
The user noticed `batchGenerateContent` calls in the logs and requested to disable batching, citing a previous agreement. This batching was introduced as a workaround for "bound to a different event loop" errors in the Writer agent.

## Objective
1.  Disable `use_google_batch` in `src/egregora/agents/writer.py`.
2.  Verify if the "bound to a different event loop" error re-appears.
3.  If the error re-appears, fix the root cause of the asyncio event loop mismatch instead of using the batching workaround.
4.  Ensure the pipeline still runs successfully and generates posts.

## Plan
1.  **Modify `src/egregora/agents/writer.py`**:
    - Set `use_google_batch=False` in `WriterAgent.__init__`.
    - Remove the fallback logic that switches to batching on loop errors (or keep it as a last resort if the user permits, but for now assume we want it gone).

2.  **Run Generation Test**:
    - Execute `egregora write` and monitor for `RuntimeError: Task <...> got Future <...> attached to a different loop`.

3.  **Fix Event Loop Issue (if needed)**:
    - If the error occurs, it means the `pydantic-ai` agent is reusing a client across loops.
    - Solution: Ensure the Agent (and its model) is re-instantiated or the client is reset for each worker execution, or run the agent in a way that respects the current loop.

4.  **Verify Output**:
    - Confirm posts are generated in `blog-test/docs/posts`.
