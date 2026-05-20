# Privacy

This package sends the parameters you (or your agent) pass to its tools and middleware — `content`, `query`, `bucket`, `memory_id` — to the Engram REST API at `https://api.lumetra.io` (or the self-hosted `base_url` you configured). Memories are stored under your Engram tenant, scoped by the API key you supplied via `ENGRAM_API_KEY` or the constructor argument.

The package does not collect, log, or transmit data to any third party other than the Engram service you've explicitly authorized. It does not read other Agent Framework resources (threads, files, tool outputs from other tools) — only the parameters supplied to each Engram tool call, plus, when `EngramMiddleware` is enabled with `auto_store=True` or `auto_recall=True`, the most recent user message in the agent's chat context.

For Engram's own data-handling and retention policy, see <https://lumetra.io/privacy>.
