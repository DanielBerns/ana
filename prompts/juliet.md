docker logs -f ana_core_interface
Installed 2 packages in 983ms
INFO:     Started server process [20]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Shutting down
INFO:     Waiting for application shutdown.
ERROR:    Traceback (most recent call last):
  File "/app/.venv/lib/python3.14/site-packages/starlette/routing.py", line 638, in lifespan
    async with self.lifespan_context(app) as maybe_state:
               ~~~~~~~~~~~~~~~~~~~~~^^^^^
  File "/usr/local/lib/python3.14/contextlib.py", line 221, in __aexit__
    await anext(self.gen)
  File "/app/apps/core/interface/src/interface/main.py", line 124, in lifespan
    await adapter.broker.disconnect()
          ^^^^^^^^^^^^^^^^^^^^^^^^^
AttributeError: 'RabbitBroker' object has no attribute 'disconnect'. Did you mean: 'connect'?

